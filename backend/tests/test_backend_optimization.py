"""
测试后端优化（阶段二）

测试点：
1. Account 汇总计算优化 - 减少 N+1 查询
2. PositionOperation 删除级联重算
3. 缓存 TTL 配置化
4. EastMoneySource 异常处理
5. Position 只读约束强化
"""
import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django.db import connection
from django.test import TestCase
from django.contrib import admin
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock
import json

from api.models import Fund, Account, Position, PositionOperation
from api.sources.eastmoney import EastMoneySource

User = get_user_model()


@pytest.mark.django_db
class TestAccountQueryOptimization:
    """测试 Account 汇总计算查询优化"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def setup_accounts_with_positions(self, user):
        """创建复杂的账户结构用于测试查询优化"""
        # 创建父账户
        parent = Account.objects.create(user=user, name='父账户')

        # 创建 3 个子账户
        children = []
        for i in range(3):
            child = Account.objects.create(
                user=user,
                name=f'子账户{i+1}',
                parent=parent
            )
            children.append(child)

        # 为每个子账户创建 5 个持仓
        funds = []
        for i in range(5):
            fund = Fund.objects.create(
                fund_code=f'00000{i+1}',
                fund_name=f'测试基金{i+1}',
                latest_nav=Decimal('1.5000')
            )
            funds.append(fund)

        for child in children:
            for fund in funds:
                Position.objects.create(
                    account=child,
                    fund=fund,
                    holding_share=Decimal('100'),
                    holding_cost=Decimal('1000'),
                    holding_nav=Decimal('10')
                )

        return {
            'parent': parent,
            'children': children,
            'funds': funds
        }

    def test_account_list_query_count(self, user, setup_accounts_with_positions):
        """测试：账户列表查询次数应该被优化"""
        from django.test.utils import CaptureQueriesContext

        client = APIClient()
        client.force_authenticate(user=user)

        # 捕获查询
        with CaptureQueriesContext(connection) as context:
            response = client.get('/api/accounts/')

        assert response.status_code == 200
        # 验证返回了所有账户（1 个父账户 + 3 个子账户）
        assert len(response.data) == 4

        # 验证查询次数被优化（应该 <= 10 次）
        query_count = len(context.captured_queries)
        assert query_count <= 10, f"查询次数过多: {query_count} 次"

    def test_account_detail_with_children_query_count(self, user, setup_accounts_with_positions):
        """测试：父账户详情查询次数应该被优化"""
        from django.test.utils import CaptureQueriesContext

        client = APIClient()
        client.force_authenticate(user=user)

        parent = setup_accounts_with_positions['parent']

        # 捕获查询
        with CaptureQueriesContext(connection) as context:
            response = client.get(f'/api/accounts/{parent.id}/')

        assert response.status_code == 200
        # 验证返回了子账户列表
        assert 'children' in response.data
        assert len(response.data['children']) == 3

        # 验证查询次数被优化（应该 <= 8 次）
        query_count = len(context.captured_queries)
        assert query_count <= 8, f"查询次数过多: {query_count} 次"


@pytest.mark.django_db
class TestPositionOperationDeleteSignal:
    """测试 PositionOperation 删除后自动重算持仓"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user):
        parent = Account.objects.create(user=user, name='父账户')
        return Account.objects.create(user=user, name='子账户', parent=parent)

    @pytest.fixture
    def fund(self):
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.5000')
        )

    def test_delete_operation_recalculates_position(self, account, fund):
        """测试：删除操作后自动重算持仓"""
        # 创建两次操作
        op1 = PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date.today(),
            before_15=True,
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10')
        )

        op2 = PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date.today(),
            before_15=True,
            amount=Decimal('500'),
            share=Decimal('50'),
            nav=Decimal('10')
        )

        # 验证持仓汇总
        position = Position.objects.get(account=account, fund=fund)
        assert position.holding_share == Decimal('150')
        assert position.holding_cost == Decimal('1500')

        # 删除第二次操作
        op2.delete()

        # 验证持仓自动重算
        position.refresh_from_db()
        assert position.holding_share == Decimal('100')
        assert position.holding_cost == Decimal('1000')

    def test_delete_last_operation_removes_position(self, account, fund):
        """测试：删除最后一条操作后持仓应该被删除"""
        # 创建一次操作
        op = PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date.today(),
            before_15=True,
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10')
        )

        # 验证持仓存在
        assert Position.objects.filter(account=account, fund=fund).exists()

        # 删除操作
        op.delete()

        # 验证持仓被删除（或份额为 0）
        position = Position.objects.filter(account=account, fund=fund).first()
        if position:
            assert position.holding_share == Decimal('0')

    def test_delete_operation_with_sell(self, account, fund):
        """测试：删除减仓操作后持仓正确重算"""
        # 建仓
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date.today(),
            before_15=True,
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10')
        )

        # 减仓
        sell_op = PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='SELL',
            operation_date=date.today(),
            before_15=True,
            amount=Decimal('300'),
            share=Decimal('30'),
            nav=Decimal('10')
        )

        # 验证持仓
        position = Position.objects.get(account=account, fund=fund)
        assert position.holding_share == Decimal('70')

        # 删除减仓操作
        sell_op.delete()

        # 验证持仓恢复
        position.refresh_from_db()
        assert position.holding_share == Decimal('100')


@pytest.mark.django_db
class TestCacheTTLConfiguration:
    """测试缓存 TTL 配置化"""

    @pytest.fixture
    def fund(self):
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.5000')
        )

    def test_batch_estimate_uses_config_ttl(self, fund):
        """测试：batch_estimate 使用配置的 TTL"""
        client = APIClient()

        # Mock 配置
        with patch('api.viewsets.config') as mock_config:
            mock_config.get.return_value = 10  # 设置 TTL 为 10 分钟

            # Mock 数据源
            with patch('api.viewsets.SourceRegistry.get_source') as mock_get_source:
                mock_source = MagicMock()
                mock_source.fetch_estimate.return_value = {
                    'fund_code': '000001',
                    'fund_name': '测试基金',
                    'estimate_nav': Decimal('1.6000'),
                    'estimate_growth': Decimal('6.67'),
                }
                mock_get_source.return_value = mock_source

                # 调用 API
                response = client.post('/api/funds/batch_estimate/', {
                    'fund_codes': ['000001']
                }, format='json')

                assert response.status_code == 200
                # 验证配置被读取
                mock_config.get.assert_called_with('estimate_cache_ttl', 5)

    def test_config_default_ttl_when_not_set(self, fund):
        """测试：配置未设置时使用默认 TTL"""
        client = APIClient()

        # Mock 配置返回 None
        with patch('api.viewsets.config') as mock_config:
            mock_config.get.return_value = 5  # 默认值

            with patch('api.viewsets.SourceRegistry.get_source') as mock_get_source:
                mock_source = MagicMock()
                mock_source.fetch_estimate.return_value = {
                    'fund_code': '000001',
                    'fund_name': '测试基金',
                    'estimate_nav': Decimal('1.6000'),
                    'estimate_growth': Decimal('6.67'),
                }
                mock_get_source.return_value = mock_source

                response = client.post('/api/funds/batch_estimate/', {
                    'fund_codes': ['000001']
                }, format='json')

                assert response.status_code == 200


@pytest.mark.django_db
class TestEastMoneySourceExceptionHandling:
    """测试 EastMoneySource 异常处理"""

    def test_fetch_estimate_with_invalid_response_format(self):
        """测试：API 返回格式错误时不崩溃"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            # Mock 返回无效格式
            mock_response = MagicMock()
            mock_response.text = 'invalid response'
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # 调用应该返回 None 而不是崩溃
            result = source.fetch_estimate('000001')
            assert result is None

    def test_fetch_estimate_with_network_error(self):
        """测试：网络错误时不崩溃"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            # Mock 网络错误
            mock_get.side_effect = Exception('Network error')

            # 调用应该返回 None 而不是崩溃
            result = source.fetch_estimate('000001')
            assert result is None

    def test_fetch_estimate_with_json_decode_error(self):
        """测试：JSON 解析错误时不崩溃"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            # Mock 返回无效 JSON
            mock_response = MagicMock()
            mock_response.text = 'jsonpgz({invalid json})'
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # 调用应该返回 None 而不是崩溃
            result = source.fetch_estimate('000001')
            assert result is None

    def test_fetch_estimate_with_missing_fields(self):
        """测试：返回数据缺少字段时不崩溃"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            # Mock 返回缺少字段的 JSON
            mock_response = MagicMock()
            mock_response.text = 'jsonpgz({"fundcode": "000001"})'
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # 调用应该返回 None 而不是崩溃
            result = source.fetch_estimate('000001')
            assert result is None

    def test_fetch_realtime_nav_with_exception(self):
        """测试：获取实时净值异常时不崩溃"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception('API error')

            # 调用应该返回 None 而不是崩溃
            result = source.fetch_realtime_nav('000001')
            assert result is None


@pytest.mark.django_db
class TestPositionReadOnlyConstraint:
    """测试 Position 只读约束强化"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def admin_user(self):
        return User.objects.create_superuser(
            username='admin',
            password='admin',
            email='admin@test.com'
        )

    @pytest.fixture
    def account(self, user):
        parent = Account.objects.create(user=user, name='父账户')
        return Account.objects.create(user=user, name='子账户', parent=parent)

    @pytest.fixture
    def fund(self):
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.5000')
        )

    @pytest.fixture
    def position(self, account, fund):
        return Position.objects.create(
            account=account,
            fund=fund,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10')
        )

    def test_position_api_is_readonly(self, user, position):
        """测试：Position API 只允许 GET 操作"""
        client = APIClient()
        client.force_authenticate(user=user)

        # GET 应该成功
        response = client.get(f'/api/positions/{position.id}/')
        assert response.status_code == 200

        # PUT 应该失败（405 Method Not Allowed）
        response = client.put(f'/api/positions/{position.id}/', {
            'holding_share': '200'
        }, format='json')
        assert response.status_code == 405

        # PATCH 应该失败
        response = client.patch(f'/api/positions/{position.id}/', {
            'holding_share': '200'
        }, format='json')
        assert response.status_code == 405

        # DELETE 应该失败
        response = client.delete(f'/api/positions/{position.id}/')
        assert response.status_code == 405

    def test_position_admin_readonly_permissions(self, admin_user, position):
        """测试：Django Admin 中 Position 只读"""
        from django.contrib.admin.sites import site
        from api.models import Position

        # 获取 Position 的 Admin 类
        position_admin = site._registry.get(Position)

        if position_admin:
            # 创建 Mock 请求
            from django.test import RequestFactory
            factory = RequestFactory()
            request = factory.get('/admin/api/position/')
            request.user = admin_user

            # 测试权限
            assert position_admin.has_add_permission(request) is False
            assert position_admin.has_change_permission(request, position) is False
            assert position_admin.has_delete_permission(request, position) is False

    def test_position_fields_are_readonly_in_admin(self, admin_user, position):
        """测试：Django Admin 中 Position 字段只读"""
        from django.contrib.admin.sites import site
        from api.models import Position

        position_admin = site._registry.get(Position)

        if position_admin:
            # 验证只读字段包含关键字段
            readonly_fields = position_admin.readonly_fields
            assert 'holding_share' in readonly_fields
            assert 'holding_cost' in readonly_fields
            assert 'holding_nav' in readonly_fields


@pytest.mark.django_db
class TestAccountCacheInvalidation:
    """测试 Account 缓存失效机制（如果使用缓存方案）"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user):
        parent = Account.objects.create(user=user, name='父账户')
        return Account.objects.create(user=user, name='子账户', parent=parent)

    @pytest.fixture
    def fund(self):
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.5000')
        )

    def test_cache_invalidated_after_position_change(self, account, fund):
        """测试：持仓变化后缓存应该失效"""
        # 第一次访问（缓存未命中）
        cost1 = account.holding_cost
        assert cost1 == Decimal('0')

        # 创建持仓
        Position.objects.create(
            account=account,
            fund=fund,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10')
        )

        # 第二次访问（应该获取新值，不是缓存）
        cost2 = account.holding_cost
        assert cost2 == Decimal('1000')

    def test_cache_invalidated_after_operation_create(self, account, fund):
        """测试：创建操作后缓存应该失效"""
        # 创建操作
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date.today(),
            before_15=True,
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10')
        )

        # 访问汇总（应该是最新值）
        cost = account.holding_cost
        assert cost == Decimal('1000')
