"""
测试最近修改的 viewsets.py

测试点：
1. FundViewSet.batch_estimate() - 批量获取估值（带缓存）
2. FundViewSet.batch_update_nav() - 批量更新净值
3. PositionSerializer 在 API 中返回基金详细信息
"""
import pytest
from decimal import Decimal
from datetime import datetime, date
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

from api.models import Fund, Account, Position, PositionOperation

User = get_user_model()


@pytest.mark.django_db
class TestFundBatchEstimate:
    """测试 FundViewSet.batch_estimate() - 批量获取估值"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def funds(self):
        """创建测试基金"""
        return [
            Fund.objects.create(
                fund_code='000001',
                fund_name='测试基金1',
                latest_nav=Decimal('1.5000')
            ),
            Fund.objects.create(
                fund_code='000002',
                fund_name='测试基金2',
                latest_nav=Decimal('2.0000')
            ),
        ]

    def test_batch_estimate_with_cache_miss(self, client, funds):
        """测试：缓存未命中时，从数据源获取估值"""
        with patch('api.viewsets.SourceRegistry.get_source') as mock_get_source:
            # Mock 数据源
            mock_source = MagicMock()
            mock_source.fetch_estimate.side_effect = [
                {
                    'fund_code': '000001',
                    'fund_name': '测试基金1',
                    'estimate_nav': Decimal('1.6000'),
                    'estimate_growth': Decimal('6.67'),
                },
                {
                    'fund_code': '000002',
                    'fund_name': '测试基金2',
                    'estimate_nav': Decimal('2.1000'),
                    'estimate_growth': Decimal('5.00'),
                },
            ]
            mock_get_source.return_value = mock_source

            # 调用 API
            response = client.post('/api/funds/batch_estimate/', {
                'fund_codes': ['000001', '000002']
            }, format='json')

            assert response.status_code == 200
            data = response.json()

            # 验证返回数据
            assert '000001' in data
            assert '000002' in data

            assert data['000001']['estimate_nav'] == '1.6000'
            assert data['000001']['estimate_growth'] == '6.67'
            assert data['000001']['from_cache'] is False

            assert data['000002']['estimate_nav'] == '2.1000'
            assert data['000002']['estimate_growth'] == '5.00'
            assert data['000002']['from_cache'] is False

            # 验证数据库已更新
            fund1 = Fund.objects.get(fund_code='000001')
            assert fund1.estimate_nav == Decimal('1.6000')
            assert fund1.estimate_growth == Decimal('6.67')
            assert fund1.estimate_time is not None

    def test_batch_estimate_with_cache_hit(self, client, funds):
        """测试：缓存命中时，直接返回缓存数据"""
        # 设置缓存数据（5 分钟内）
        fund1 = funds[0]
        fund1.estimate_nav = Decimal('1.6000')
        fund1.estimate_growth = Decimal('6.67')
        fund1.estimate_time = timezone.now()
        fund1.save()

        # 调用 API
        response = client.post('/api/funds/batch_estimate/', {
            'fund_codes': ['000001']
        }, format='json')

        assert response.status_code == 200
        data = response.json()

        # 验证返回缓存数据
        assert data['000001']['estimate_nav'] == '1.6000'
        assert data['000001']['from_cache'] is True

    def test_batch_estimate_with_expired_cache(self, client, funds):
        """测试：缓存过期时，重新获取估值"""
        # 设置过期缓存（6 分钟前）
        fund1 = funds[0]
        fund1.estimate_nav = Decimal('1.5000')
        fund1.estimate_growth = Decimal('0.00')
        fund1.estimate_time = timezone.now() - timezone.timedelta(minutes=6)
        fund1.save()

        with patch('api.viewsets.SourceRegistry.get_source') as mock_get_source:
            # Mock 数据源
            mock_source = MagicMock()
            mock_source.fetch_estimate.return_value = {
                'fund_code': '000001',
                'fund_name': '测试基金1',
                'estimate_nav': Decimal('1.6000'),
                'estimate_growth': Decimal('6.67'),
            }
            mock_get_source.return_value = mock_source

            # 调用 API
            response = client.post('/api/funds/batch_estimate/', {
                'fund_codes': ['000001']
            }, format='json')

            assert response.status_code == 200
            data = response.json()

            # 验证重新获取数据
            assert data['000001']['estimate_nav'] == '1.6000'
            assert data['000001']['from_cache'] is False

    def test_batch_estimate_with_nonexistent_fund(self, client):
        """测试：基金不存在时，返回错误"""
        response = client.post('/api/funds/batch_estimate/', {
            'fund_codes': ['999999']
        }, format='json')

        assert response.status_code == 200
        data = response.json()

        assert '999999' in data
        assert 'error' in data['999999']
        assert '基金不存在' in data['999999']['error']

    def test_batch_estimate_with_empty_fund_codes(self, client):
        """测试：fund_codes 为空时，返回错误"""
        response = client.post('/api/funds/batch_estimate/', {
            'fund_codes': []
        }, format='json')

        assert response.status_code == 400
        data = response.json()
        assert 'error' in data


@pytest.mark.django_db
class TestFundBatchUpdateNav:
    """测试 FundViewSet.batch_update_nav() - 批量更新净值"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def funds(self):
        """创建测试基金"""
        return [
            Fund.objects.create(
                fund_code='000001',
                fund_name='测试基金1',
            ),
            Fund.objects.create(
                fund_code='000002',
                fund_name='测试基金2',
            ),
        ]

    def test_batch_update_nav_success(self, client, funds):
        """测试：批量更新净值成功"""
        with patch('api.viewsets.SourceRegistry.get_source') as mock_get_source:
            # Mock 数据源
            mock_source = MagicMock()
            mock_source.fetch_realtime_nav.side_effect = [
                {
                    'fund_code': '000001',
                    'nav': Decimal('1.5000'),
                    'nav_date': date(2026, 2, 11),
                },
                {
                    'fund_code': '000002',
                    'nav': Decimal('2.0000'),
                    'nav_date': date(2026, 2, 11),
                },
            ]
            mock_get_source.return_value = mock_source

            # 调用 API
            response = client.post('/api/funds/batch_update_nav/', {
                'fund_codes': ['000001', '000002']
            }, format='json')

            assert response.status_code == 200
            data = response.json()

            # 验证返回数据
            assert '000001' in data
            assert '000002' in data

            assert data['000001']['latest_nav'] == '1.5000'
            assert data['000001']['latest_nav_date'] == '2026-02-11'

            assert data['000002']['latest_nav'] == '2.0000'
            assert data['000002']['latest_nav_date'] == '2026-02-11'

            # 验证数据库已更新
            fund1 = Fund.objects.get(fund_code='000001')
            assert fund1.latest_nav == Decimal('1.5000')
            assert fund1.latest_nav_date == date(2026, 2, 11)

    def test_batch_update_nav_with_error(self, client, funds):
        """测试：获取净值失败时，返回错误"""
        with patch('api.viewsets.SourceRegistry.get_source') as mock_get_source:
            # Mock 数据源抛出异常
            mock_source = MagicMock()
            mock_source.fetch_realtime_nav.side_effect = Exception('网络错误')
            mock_get_source.return_value = mock_source

            # 调用 API
            response = client.post('/api/funds/batch_update_nav/', {
                'fund_codes': ['000001']
            }, format='json')

            assert response.status_code == 200
            data = response.json()

            # 验证返回错误
            assert '000001' in data
            assert 'error' in data['000001']
            assert '获取净值失败' in data['000001']['error']

    def test_batch_update_nav_with_empty_fund_codes(self, client):
        """测试：fund_codes 为空时，返回错误"""
        response = client.post('/api/funds/batch_update_nav/', {
            'fund_codes': []
        }, format='json')

        assert response.status_code == 400
        data = response.json()
        assert 'error' in data


@pytest.mark.django_db
class TestPositionAPIWithFundDetails:
    """测试持仓 API 返回基金详细信息"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user):
        parent = Account.objects.create(user=user, name='父账户')
        return Account.objects.create(user=user, name='子账户', parent=parent)

    @pytest.fixture
    def fund_with_estimate(self):
        """创建包含估值的基金"""
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            fund_type='股票型',
            latest_nav=Decimal('1.5000'),
            latest_nav_date=date(2026, 2, 11),
            estimate_nav=Decimal('1.6000'),
            estimate_growth=Decimal('6.67'),
            estimate_time=timezone.make_aware(datetime(2026, 2, 12, 14, 30))
        )

    def test_position_list_includes_fund_details(self, client, user, account, fund_with_estimate):
        """测试：持仓列表包含基金详细信息"""
        # 创建持仓
        Position.objects.create(
            account=account,
            fund=fund_with_estimate,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        client.force_authenticate(user=user)
        response = client.get(f'/api/positions/?account={account.id}')

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        position = data[0]

        # 验证 fund 字段存在且包含详细信息
        assert 'fund' in position
        assert position['fund']['fund_code'] == '000001'
        assert position['fund']['fund_name'] == '测试基金'
        assert position['fund']['fund_type'] == '股票型'
        assert position['fund']['latest_nav'] == '1.5000'
        assert position['fund']['latest_nav_date'] == '2026-02-11'
        assert position['fund']['estimate_nav'] == '1.6000'
        assert position['fund']['estimate_growth'] == '6.6700'  # Decimal 保留 4 位小数
        assert position['fund']['estimate_time'] is not None

        # 验证旧字段仍然存在（向后兼容）
        assert position['fund_code'] == '000001'
        assert position['fund_name'] == '测试基金'
        assert position['fund_type'] == '股票型'

    def test_position_detail_includes_fund_details(self, client, user, account, fund_with_estimate):
        """测试：持仓详情包含基金详细信息"""
        # 创建持仓
        position = Position.objects.create(
            account=account,
            fund=fund_with_estimate,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        client.force_authenticate(user=user)
        response = client.get(f'/api/positions/{position.id}/')

        assert response.status_code == 200
        data = response.json()

        # 验证 fund 字段存在且包含详细信息
        assert 'fund' in data
        assert data['fund']['fund_code'] == '000001'
        assert data['fund']['estimate_nav'] == '1.6000'


@pytest.mark.django_db
class TestPositionOperationAPIWithRecalculation:
    """测试持仓操作 API 自动重算持仓"""

    @pytest.fixture
    def client(self):
        return APIClient()

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

    def test_create_operation_recalculates_position(self, client, user, account, fund):
        """测试：创建操作后自动重算持仓"""
        client.force_authenticate(user=user)

        # 创建操作
        response = client.post('/api/positions/operations/', {
            'account': str(account.id),
            'fund_code': '000001',
            'operation_type': 'BUY',
            'operation_date': date.today().isoformat(),
            'before_15': True,
            'amount': '1000.00',
            'share': '100.0000',
            'nav': '10.0000',
        }, format='json')

        assert response.status_code == 201

        # 验证持仓自动创建
        position = Position.objects.get(account=account, fund=fund)
        assert position.holding_share == Decimal('100')
        assert position.holding_cost == Decimal('1000')

    def test_create_multiple_operations_recalculates_correctly(self, client, user, account, fund):
        """测试：多次操作后持仓计算正确"""
        client.force_authenticate(user=user)

        # 第一次建仓
        client.post('/api/positions/operations/', {
            'account': str(account.id),
            'fund_code': '000001',
            'operation_type': 'BUY',
            'operation_date': date.today().isoformat(),
            'before_15': True,
            'amount': '1000.00',
            'share': '100.0000',
            'nav': '10.0000',
        }, format='json')

        # 第二次加仓
        client.post('/api/positions/operations/', {
            'account': str(account.id),
            'fund_code': '000001',
            'operation_type': 'BUY',
            'operation_date': date.today().isoformat(),
            'before_15': True,
            'amount': '500.00',
            'share': '50.0000',
            'nav': '10.0000',
        }, format='json')

        # 验证持仓累加
        position = Position.objects.get(account=account, fund=fund)
        assert position.holding_share == Decimal('150')
        assert position.holding_cost == Decimal('1500')
