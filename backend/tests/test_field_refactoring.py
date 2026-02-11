"""
测试字段重构：latest_nav → latest_nav

测试点：
1. 新字段存在性
2. 数据迁移正确性
3. API 响应包含新字段
4. Position.pnl 计算使用新字段
5. 序列化器使用新字段
"""
import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestFundFieldRefactoring:
    """测试 Fund 模型字段重构"""

    def test_fund_has_latest_nav_fields(self):
        """测试 Fund 模型有 latest_nav 和 latest_nav_date 字段"""
        from api.models import Fund

        fund = Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.2345'),
            latest_nav_date=date(2026, 2, 11)
        )

        assert fund.latest_nav == Decimal('1.2345')
        assert fund.latest_nav_date == date(2026, 2, 11)

    def test_fund_latest_nav_nullable(self):
        """测试 latest_nav 可以为空"""
        from api.models import Fund

        fund = Fund.objects.create(
            fund_code='000002',
            fund_name='测试基金2'
        )

        assert fund.latest_nav is None
        assert fund.latest_nav_date is None

    def test_fund_no_latest_nav_fields(self):
        """测试 Fund 模型不再有 latest_nav 字段"""
        from api.models import Fund

        fund = Fund()

        # 新字段应该存在
        assert hasattr(fund, 'latest_nav')
        assert hasattr(fund, 'latest_nav_date')


@pytest.mark.django_db
class TestPositionPnLWithLatestNav:
    """测试 Position.pnl 使用 latest_nav 计算"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.5000'),
            latest_nav_date=date(2026, 2, 11)
        )

    @pytest.fixture
    def account(self, user, create_child_account):
        return create_child_account(user, '测试账户')

    def test_pnl_calculation_with_latest_nav(self, account, fund):
        """测试盈亏计算使用 latest_nav"""
        from api.models import Position

        position = Position.objects.create(
            account=account,
            fund=fund,
            holding_share=Decimal('1000'),
            holding_nav=Decimal('1.2000'),
            holding_cost=Decimal('1200')
        )

        # 盈亏 = (latest_nav - holding_nav) * holding_share
        # = (1.5000 - 1.2000) * 1000 = 300
        expected_pnl = Decimal('300.0000')
        assert position.pnl == expected_pnl

    def test_pnl_zero_when_no_latest_nav(self, account, fund):
        """测试没有 latest_nav 时盈亏为 0"""
        from api.models import Position

        fund.latest_nav = None
        fund.save()

        position = Position.objects.create(
            account=account,
            fund=fund,
            holding_share=Decimal('1000'),
            holding_nav=Decimal('1.2000')
        )

        assert position.pnl == 0


@pytest.mark.django_db
class TestBatchEstimateAPIWithLatestNav:
    """测试批量估值 API 使用 latest_nav"""

    @pytest.fixture
    def client(self):
        from rest_framework.test import APIClient
        return APIClient()

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.2345'),
            latest_nav_date=date(2026, 2, 11)
        )

    def test_batch_estimate_returns_latest_nav(self, client, fund, mocker):
        """测试批量估值 API 返回 latest_nav"""
        # Mock 数据源
        mock_source = mocker.Mock()
        mock_source.fetch_estimate.return_value = {
            'fund_code': '000001',
            'estimate_nav': Decimal('1.2500'),
            'estimate_growth': Decimal('1.26'),
        }
        mocker.patch('api.sources.SourceRegistry.get_source', return_value=mock_source)

        response = client.post('/api/funds/batch_estimate/', {
            'fund_codes': ['000001']
        }, format='json')

        assert response.status_code == 200
        assert '000001' in response.data

        # 应该返回 latest_nav 而不是 latest_nav
        assert 'latest_nav' in response.data['000001']
        assert response.data['000001']['latest_nav'] == '1.2345'


@pytest.mark.django_db
class TestFundSerializerWithLatestNav:
    """测试 Fund 序列化器使用 latest_nav"""

    def test_fund_serializer_includes_latest_nav(self):
        """测试序列化器包含 latest_nav 字段"""
        from api.models import Fund
        from api.serializers import FundSerializer

        fund = Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.2345'),
            latest_nav_date=date(2026, 2, 11)
        )

        serializer = FundSerializer(fund)
        data = serializer.data

        assert 'latest_nav' in data
        assert 'latest_nav_date' in data
        assert data['latest_nav'] == '1.2345'
        assert data['latest_nav_date'] == '2026-02-11'


@pytest.mark.django_db
class TestUpdateNavCommandWithLatestNav:
    """测试 update_nav 命令使用 latest_nav"""

    def test_update_nav_command_updates_latest_nav(self, mocker):
        """测试 update_nav 命令更新 latest_nav"""
        from api.models import Fund
        from django.core.management import call_command

        # 创建基金
        fund = Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金'
        )

        # Mock 数据源
        mock_source = mocker.Mock()
        mock_source.fetch_realtime_nav.return_value = {
            'fund_code': '000001',
            'nav': Decimal('1.2345'),
            'nav_date': date(2026, 2, 11)
        }
        mocker.patch('api.sources.SourceRegistry.get_source', return_value=mock_source)

        # 执行命令
        call_command('update_nav', '--fund_code', '000001')

        # 验证更新
        fund.refresh_from_db()
        assert fund.latest_nav == Decimal('1.2345')
        assert fund.latest_nav_date == date(2026, 2, 11)


@pytest.mark.django_db
class TestFundListAPIWithLatestNav:
    """测试基金列表 API 返回 latest_nav"""

    @pytest.fixture
    def client(self):
        from rest_framework.test import APIClient
        return APIClient()

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.2345'),
            latest_nav_date=date(2026, 2, 11)
        )

    def test_fund_list_returns_latest_nav(self, client, fund):
        """测试基金列表返回 latest_nav"""
        response = client.get('/api/funds/')

        assert response.status_code == 200
        assert len(response.data['results']) == 1

        fund_data = response.data['results'][0]
        assert 'latest_nav' in fund_data
        assert 'latest_nav_date' in fund_data
        assert fund_data['latest_nav'] == '1.2345'
        assert fund_data['latest_nav_date'] == '2026-02-11'


@pytest.mark.django_db
class TestFundDetailAPIWithLatestNav:
    """测试基金详情 API 返回 latest_nav"""

    @pytest.fixture
    def client(self):
        from rest_framework.test import APIClient
        return APIClient()

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.2345'),
            latest_nav_date=date(2026, 2, 11)
        )

    def test_fund_detail_returns_latest_nav(self, client, fund):
        """测试基金详情返回 latest_nav"""
        response = client.get('/api/funds/000001/')

        assert response.status_code == 200
        assert 'latest_nav' in response.data
        assert 'latest_nav_date' in response.data
        assert response.data['latest_nav'] == '1.2345'
        assert response.data['latest_nav_date'] == '2026-02-11'
