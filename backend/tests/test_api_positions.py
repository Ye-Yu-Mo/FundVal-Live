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


@pytest.mark.django_db
class TestPositionClearAPI:
    """测试清空持仓 API"""

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
        return Fund.objects.create(fund_code='000001', fund_name='测试基金')

    @pytest.fixture
    def position_with_operations(self, account, fund):
        """创建有多条操作的持仓"""
        from api.models import Position, PositionOperation

        # 创建 3 条操作（会自动触发持仓计算）
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 1, 1),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 1),
            amount=Decimal('2000'),
            share=Decimal('200'),
            nav=Decimal('10'),
        )
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='SELL',
            operation_date=date(2024, 3, 1),
            amount=Decimal('500'),
            share=Decimal('50'),
            nav=Decimal('10'),
        )

        # 获取自动创建的持仓
        position = Position.objects.get(account=account, fund=fund)
        return position

    def test_clear_position(self, client, user, position_with_operations):
        """测试清空持仓"""
        from api.models import PositionOperation, Position

        position_id = position_with_operations.id
        account_id = position_with_operations.account.id
        fund_id = position_with_operations.fund.id

        # 确认操作存在
        assert PositionOperation.objects.filter(
            account_id=account_id, fund_id=fund_id
        ).count() == 3

        client.force_authenticate(user=user)
        response = client.delete(f'/api/positions/{position_id}/clear/')
        assert response.status_code == 204

        # 确认所有操作已删除
        assert PositionOperation.objects.filter(
            account_id=account_id, fund_id=fund_id
        ).count() == 0

        # 确认持仓已被删除或份额为 0
        position = Position.objects.filter(id=position_id).first()
        if position:
            assert position.holding_share == Decimal('0')

    def test_clear_position_not_owner(self, client, position_with_operations):
        """测试清空他人的持仓应被拒绝"""
        other_user = User.objects.create_user(username='other', password='pass')
        client.force_authenticate(user=other_user)
        response = client.delete(f'/api/positions/{position_with_operations.id}/clear/')
        assert response.status_code == 404

    def test_clear_nonexistent_position(self, client, user):
        """测试清空不存在的持仓"""
        import uuid
        client.force_authenticate(user=user)
        response = client.delete(f'/api/positions/{uuid.uuid4()}/clear/')
        assert response.status_code == 404


@pytest.mark.django_db
class TestPositionOperationBatchDeleteAPI:
    """测试批量删除操作 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def admin_user(self):
        return User.objects.create_superuser(username='admin', password='pass')

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user, create_child_account):
        return create_child_account(user, '我的账户')

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(fund_code='000001', fund_name='测试基金')

    @pytest.fixture
    def operations(self, account, fund):
        """创建多条操作"""
        from api.models import PositionOperation

        ops = []
        for i in range(5):
            op = PositionOperation.objects.create(
                account=account,
                fund=fund,
                operation_type='BUY',
                operation_date=date(2024, 1, i + 1),
                amount=Decimal('1000'),
                share=Decimal('100'),
                nav=Decimal('10'),
            )
            ops.append(op)
        return ops

    def test_batch_delete_operations_as_admin(self, client, admin_user, operations):
        """测试管理员批量删除操作"""
        from api.models import PositionOperation

        operation_ids = [str(op.id) for op in operations[:3]]

        client.force_authenticate(user=admin_user)
        response = client.post('/api/positions/operations/batch_delete/', {
            'operation_ids': operation_ids
        }, format='json')
        assert response.status_code == 200
        assert response.data['deleted_count'] == 3

        # 确认操作已删除
        for op_id in operation_ids:
            assert not PositionOperation.objects.filter(id=op_id).exists()

        # 确认其他操作仍存在
        assert PositionOperation.objects.filter(id=operations[3].id).exists()
        assert PositionOperation.objects.filter(id=operations[4].id).exists()

    def test_batch_delete_operations_as_regular_user(self, client, user, operations):
        """测试普通用户不能批量删除操作"""
        operation_ids = [str(op.id) for op in operations[:3]]

        client.force_authenticate(user=user)
        response = client.post('/api/positions/operations/batch_delete/', {
            'operation_ids': operation_ids
        }, format='json')
        assert response.status_code == 403

    def test_batch_delete_empty_list(self, client, admin_user):
        """测试批量删除空列表"""
        client.force_authenticate(user=admin_user)
        response = client.post('/api/positions/operations/batch_delete/', {
            'operation_ids': []
        }, format='json')
        assert response.status_code == 400
        assert 'operation_ids' in str(response.data) or '不能为空' in str(response.data)

    def test_batch_delete_nonexistent_operations(self, client, admin_user):
        """测试批量删除不存在的操作"""
        import uuid
        operation_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

        client.force_authenticate(user=admin_user)
        response = client.post('/api/positions/operations/batch_delete/', {
            'operation_ids': operation_ids
        }, format='json')
        assert response.status_code == 200
        assert response.data['deleted_count'] == 0


@pytest.mark.django_db
class TestPositionOperationDeleteAnyAPI:
    """测试删除任意操作（放宽限制）"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def admin_user(self):
        return User.objects.create_superuser(username='admin', password='pass')

    @pytest.fixture
    def account(self, admin_user, create_child_account):
        return create_child_account(admin_user, '我的账户')

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(fund_code='000001', fund_name='测试基金')

    @pytest.fixture
    def operations(self, account, fund):
        """创建按时间顺序的操作"""
        from api.models import PositionOperation

        ops = []
        for i in range(3):
            op = PositionOperation.objects.create(
                account=account,
                fund=fund,
                operation_type='BUY',
                operation_date=date(2024, 1, i + 1),
                amount=Decimal('1000'),
                share=Decimal('100'),
                nav=Decimal('10'),
            )
            ops.append(op)
        return ops

    def test_delete_middle_operation(self, client, admin_user, operations):
        """测试删除中间的操作（非最新）"""
        from api.models import PositionOperation, Position

        # 删除第二条操作（中间的）
        middle_op = operations[1]

        client.force_authenticate(user=admin_user)
        response = client.delete(f'/api/positions/operations/{middle_op.id}/')
        assert response.status_code == 204

        # 确认操作已删除
        assert not PositionOperation.objects.filter(id=middle_op.id).exists()

        # 确认其他操作仍存在
        assert PositionOperation.objects.filter(id=operations[0].id).exists()
        assert PositionOperation.objects.filter(id=operations[2].id).exists()

        # 确认持仓已重算（应该是 200 份，不是 300 份）
        position = Position.objects.filter(
            account=operations[0].account,
            fund=operations[0].fund
        ).first()
        if position:
            assert position.holding_share == Decimal('200')

    def test_delete_first_operation(self, client, admin_user, operations):
        """测试删除最早的操作"""
        from api.models import PositionOperation, Position

        first_op = operations[0]

        client.force_authenticate(user=admin_user)
        response = client.delete(f'/api/positions/operations/{first_op.id}/')
        assert response.status_code == 204

        # 确认持仓已重算（应该是 200 份）
        position = Position.objects.filter(
            account=operations[0].account,
            fund=operations[0].fund
        ).first()
        if position:
            assert position.holding_share == Decimal('200')
