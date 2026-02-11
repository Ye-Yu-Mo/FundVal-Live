"""
测试数据源和其他 API

测试点：
1. 数据源列表
2. 数据源准确率
3. 用户注册
4. 用户资产汇总
"""
import pytest
from decimal import Decimal
from datetime import date
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestSourceListAPI:
    """测试数据源列表 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    def test_list_sources(self, client):
        """测试列出所有数据源"""
        response = client.get('/api/sources/')
        assert response.status_code == 200
        assert 'eastmoney' in [s['name'] for s in response.data]


@pytest.mark.django_db
class TestSourceAccuracyAPI:
    """测试数据源准确率 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def accuracy_records(self):
        from api.models import Fund, EstimateAccuracy

        fund1 = Fund.objects.create(fund_code='000001', fund_name='基金1')
        fund2 = Fund.objects.create(fund_code='000002', fund_name='基金2')

        records = []
        for i in range(10):
            records.append(EstimateAccuracy.objects.create(
                source_name='eastmoney',
                fund=fund1,
                estimate_date=date(2024, 2, i + 1),
                estimate_nav=Decimal('1.1000'),
                actual_nav=Decimal('1.1100'),
                error_rate=Decimal('0.009009'),
            ))
            records.append(EstimateAccuracy.objects.create(
                source_name='eastmoney',
                fund=fund2,
                estimate_date=date(2024, 2, i + 1),
                estimate_nav=Decimal('1.2000'),
                actual_nav=Decimal('1.2200'),
                error_rate=Decimal('0.016393'),
            ))

        return records

    def test_get_source_accuracy(self, client, accuracy_records):
        """测试获取数据源整体准确率"""
        response = client.get('/api/sources/eastmoney/accuracy/')
        assert response.status_code == 200
        assert 'avg_error_rate' in response.data
        assert 'record_count' in response.data
        assert response.data['record_count'] == 20

    def test_get_source_accuracy_with_days(self, client, accuracy_records):
        """测试获取指定天数的准确率"""
        response = client.get('/api/sources/eastmoney/accuracy/?days=5')
        assert response.status_code == 200
        # 最近5天，每天2条记录
        assert response.data['record_count'] <= 10


@pytest.mark.django_db
class TestUserRegisterAPI:
    """测试用户注册 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    def test_register_user(self, client, mocker):
        """测试用户注册"""
        # Mock 配置：允许注册
        mocker.patch('fundval.config.config.get', return_value=True)

        response = client.post('/api/users/register/', {
            'username': 'newuser',
            'password': 'password123',
            'password_confirm': 'password123',
        })
        assert response.status_code == 201
        assert 'access_token' in response.data

    def test_register_user_password_mismatch(self, client, mocker):
        """测试密码不匹配"""
        mocker.patch('fundval.config.config.get', return_value=True)

        response = client.post('/api/users/register/', {
            'username': 'newuser',
            'password': 'password123',
            'password_confirm': 'password456',
        })
        assert response.status_code == 400

    def test_register_user_duplicate_username(self, client, mocker):
        """测试用户名重复"""
        mocker.patch('fundval.config.config.get', return_value=True)
        User.objects.create_user(username='existinguser', password='pass')

        response = client.post('/api/users/register/', {
            'username': 'existinguser',
            'password': 'password123',
            'password_confirm': 'password123',
        })
        assert response.status_code == 400

    def test_register_user_not_allowed(self, client, mocker):
        """测试注册未开放"""
        # Mock 配置：不允许注册
        mocker.patch('fundval.config.config.get', return_value=False)

        response = client.post('/api/users/register/', {
            'username': 'newuser',
            'password': 'password123',
            'password_confirm': 'password123',
        })
        assert response.status_code == 403


@pytest.mark.django_db
class TestUserSummaryAPI:
    """测试用户资产汇总 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def user_data(self, user, create_child_account):
        from api.models import Account, Fund, Position

        account1 = create_child_account(user, '账户1')
        account2 = create_child_account(user, '账户2')

        fund1 = Fund.objects.create(
            fund_code='000001',
            fund_name='基金1',
            latest_nav=Decimal('1.5000'),
        )
        fund2 = Fund.objects.create(
            fund_code='000002',
            fund_name='基金2',
            latest_nav=Decimal('2.0000'),
        )

        Position.objects.create(
            account=account1,
            fund=fund1,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )
        Position.objects.create(
            account=account2,
            fund=fund2,
            holding_share=Decimal('200'),
            holding_cost=Decimal('2000'),
            holding_nav=Decimal('10'),
        )

        return {
            'accounts': [account1, account2],
            'funds': [fund1, fund2],
        }

    def test_get_user_summary(self, client, user, user_data):
        """测试获取用户资产汇总"""
        client.force_authenticate(user=user)
        response = client.get('/api/users/me/summary/')
        assert response.status_code == 200

        # 验证汇总数据
        assert 'total_cost' in response.data
        assert 'total_value' in response.data
        assert 'total_pnl' in response.data
        assert 'account_count' in response.data
        assert 'position_count' in response.data

        # 总成本：1000 + 2000 = 3000
        assert Decimal(response.data['total_cost']) == Decimal('3000')

        # 账户数：4（2个父账户 + 2个子账户）
        assert response.data['account_count'] == 4

        # 持仓数：2
        assert response.data['position_count'] == 2

    def test_get_user_summary_unauthenticated(self, client):
        """测试未认证用户不能查看汇总"""
        response = client.get('/api/users/me/summary/')
        assert response.status_code == 401
