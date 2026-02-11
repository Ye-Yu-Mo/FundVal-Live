"""
测试持仓相关 API

测试点：
1. 持仓列表
2. 持仓详情
3. 创建持仓操作（建仓/加仓/减仓）
4. 操作流水列表
5. 操作详情
6. 删除操作
7. 重算持仓
"""
import pytest
from decimal import Decimal
from datetime import date
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestPositionListAPI:
    """测试持仓列表 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user, create_child_account):
        return create_child_account(user, '我的账户')

    @pytest.fixture
    def positions(self, account):
        from api.models import Fund, Position

        fund1 = Fund.objects.create(fund_code='000001', fund_name='基金1')
        fund2 = Fund.objects.create(fund_code='000002', fund_name='基金2')

        return [
            Position.objects.create(
                account=account,
                fund=fund1,
                holding_share=Decimal('100'),
            ),
            Position.objects.create(
                account=account,
                fund=fund2,
                holding_share=Decimal('200'),
            ),
        ]

    def test_list_positions(self, client, user, positions):
        """测试查看持仓列表"""
        client.force_authenticate(user=user)
        response = client.get('/api/positions/')
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_filter_positions_by_account(self, client, user, account, positions):
        """测试按账户过滤持仓"""
        client.force_authenticate(user=user)
        response = client.get(f'/api/positions/?account={account.id}')
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_list_positions_unauthenticated(self, client):
        """测试未认证用户不能查看持仓"""
        response = client.get('/api/positions/')
        assert response.status_code == 401


@pytest.mark.django_db
class TestPositionDetailAPI:
    """测试持仓详情 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def position(self, user, create_child_account):
        from api.models import Account, Fund, Position

        account = create_child_account(user, '我的账户')
        fund = Fund.objects.create(fund_code='000001', fund_name='基金1')

        return Position.objects.create(
            account=account,
            fund=fund,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

    def test_get_position_detail(self, client, user, position):
        """测试获取持仓详情"""
        client.force_authenticate(user=user)
        response = client.get(f'/api/positions/{position.id}/')
        assert response.status_code == 200
        assert Decimal(response.data['holding_share']) == Decimal('100')


@pytest.mark.django_db
class TestPositionOperationCreateAPI:
    """测试创建持仓操作 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user, create_child_account):
        return create_child_account(user, '我的账户')

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='华夏成长混合',
            latest_nav=Decimal('1.5000'),
        )

    def test_create_buy_operation(self, client, user, account, fund):
        """测试创建买入操作"""
        client.force_authenticate(user=user)
        response = client.post('/api/positions/operations/', {
            'account': str(account.id),
            'fund_code': fund.fund_code,
            'operation_type': 'BUY',
            'operation_date': '2024-02-11',
            'before_15': True,
            'amount': '1000',
            'share': '100',
            'nav': '10',
        })
        assert response.status_code == 201
        assert response.data['operation_type'] == 'BUY'

        # 验证持仓已自动计算
        from api.models import Position
        position = Position.objects.get(account=account, fund=fund)
        assert position.holding_share == Decimal('100')

    def test_create_sell_operation(self, client, user, account, fund):
        """测试创建卖出操作"""
        from api.models import PositionOperation

        # 先建仓
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        client.force_authenticate(user=user)
        response = client.post('/api/positions/operations/', {
            'account': str(account.id),
            'fund_code': fund.fund_code,
            'operation_type': 'SELL',
            'operation_date': '2024-02-12',
            'before_15': False,
            'amount': '600',
            'share': '50',
            'nav': '12',
        })
        assert response.status_code == 201

    def test_create_operation_invalid_fund(self, client, user, account):
        """测试使用不存在的基金"""
        client.force_authenticate(user=user)
        response = client.post('/api/positions/operations/', {
            'account': str(account.id),
            'fund_code': '999999',
            'operation_type': 'BUY',
            'operation_date': '2024-02-11',
            'amount': '1000',
            'share': '100',
            'nav': '10',
        })
        assert response.status_code == 400


@pytest.mark.django_db
class TestPositionOperationListAPI:
    """测试操作流水列表 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def operations(self, user, create_child_account):
        from api.models import Account, Fund, PositionOperation

        account = create_child_account(user, '我的账户')
        fund = Fund.objects.create(fund_code='000001', fund_name='基金1')

        return [
            PositionOperation.objects.create(
                account=account,
                fund=fund,
                operation_type='BUY',
                operation_date=date(2024, 2, 11),
                amount=Decimal('1000'),
                share=Decimal('100'),
                nav=Decimal('10'),
            ),
            PositionOperation.objects.create(
                account=account,
                fund=fund,
                operation_type='SELL',
                operation_date=date(2024, 2, 12),
                amount=Decimal('600'),
                share=Decimal('50'),
                nav=Decimal('12'),
            ),
        ]

    def test_list_operations(self, client, user, operations):
        """测试查看操作流水列表"""
        client.force_authenticate(user=user)
        response = client.get('/api/positions/operations/')
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_filter_operations_by_account(self, client, user, operations):
        """测试按账户过滤操作"""
        account_id = operations[0].account.id
        client.force_authenticate(user=user)
        response = client.get(f'/api/positions/operations/?account={account_id}')
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_filter_operations_by_fund(self, client, user, operations):
        """测试按基金过滤操作"""
        fund_code = operations[0].fund.fund_code
        client.force_authenticate(user=user)
        response = client.get(f'/api/positions/operations/?fund_code={fund_code}')
        assert response.status_code == 200
        assert len(response.data) == 2


@pytest.mark.django_db
class TestPositionOperationDetailAPI:
    """测试操作详情 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def operation(self, user, create_child_account):
        from api.models import Account, Fund, PositionOperation

        account = create_child_account(user, '我的账户')
        fund = Fund.objects.create(fund_code='000001', fund_name='基金1')

        return PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

    def test_get_operation_detail(self, client, user, operation):
        """测试获取操作详情"""
        client.force_authenticate(user=user)
        response = client.get(f'/api/positions/operations/{operation.id}/')
        assert response.status_code == 200
        assert response.data['operation_type'] == 'BUY'


@pytest.mark.django_db
class TestPositionOperationDeleteAPI:
    """测试删除操作 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def admin_user(self):
        return User.objects.create_superuser(username='admin', password='pass')

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='user', password='pass')

    @pytest.fixture
    def operation(self, user, create_child_account):
        from api.models import Account, Fund, PositionOperation

        account = create_child_account(user, '我的账户')
        fund = Fund.objects.create(fund_code='000001', fund_name='基金1')

        return PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

    def test_delete_operation_as_admin(self, client, admin_user, operation):
        """测试管理员删除操作"""
        client.force_authenticate(user=admin_user)
        response = client.delete(f'/api/positions/operations/{operation.id}/')
        assert response.status_code == 204

    def test_delete_operation_as_regular_user(self, client, user, operation):
        """测试普通用户不能删除操作"""
        client.force_authenticate(user=user)
        response = client.delete(f'/api/positions/operations/{operation.id}/')
        assert response.status_code == 403


@pytest.mark.django_db
class TestRecalculatePositionsAPI:
    """测试重算持仓 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def admin_user(self):
        return User.objects.create_superuser(username='admin', password='pass')

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='user', password='pass')

    def test_recalculate_positions_as_admin(self, client, admin_user):
        """测试管理员重算持仓"""
        client.force_authenticate(user=admin_user)
        response = client.post('/api/positions/recalculate/')
        assert response.status_code == 200

    def test_recalculate_positions_as_regular_user(self, client, user):
        """测试普通用户不能重算持仓"""
        client.force_authenticate(user=user)
        response = client.post('/api/positions/recalculate/')
        assert response.status_code == 403
