"""
测试账户体系约束（阶段一）

测试点：
1. 每个用户只能有一个默认账户
2. 默认账户必须是父账户
3. 父账户不能有持仓
4. Position.account 必须是子账户
"""
import pytest
from decimal import Decimal
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestAccountDefaultConstraints:
    """测试默认账户约束"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    def test_only_one_default_account_per_user(self, user):
        """测试每个用户只能有一个默认账户（自动切换）"""
        from api.models import Account

        # 创建第一个默认账户
        account1 = Account.objects.create(
            user=user,
            name='默认账户1',
            is_default=True,
        )
        assert account1.is_default is True

        # 创建第二个默认账户（应该自动取消第一个）
        account2 = Account.objects.create(
            user=user,
            name='默认账户2',
            is_default=True,
        )

        # 刷新第一个账户
        account1.refresh_from_db()

        # 第一个账户应该不再是默认
        assert account1.is_default is False
        # 第二个账户应该是默认
        assert account2.is_default is True

        # 验证只有一个默认账户
        default_count = Account.objects.filter(
            user=user,
            is_default=True
        ).count()
        assert default_count == 1

    def test_different_users_can_have_default_accounts(self):
        """测试不同用户可以各自有默认账户"""
        from api.models import Account

        user1 = User.objects.create_user(username='user1', password='pass1')
        user2 = User.objects.create_user(username='user2', password='pass2')

        account1 = Account.objects.create(
            user=user1,
            name='用户1默认账户',
            is_default=True,
        )

        account2 = Account.objects.create(
            user=user2,
            name='用户2默认账户',
            is_default=True,
        )

        assert account1.is_default is True
        assert account2.is_default is True

    def test_default_account_must_be_parent(self, user):
        """测试默认账户必须是父账户（parent IS NULL）"""
        from api.models import Account

        # 创建父账户
        parent = Account.objects.create(
            user=user,
            name='父账户',
        )

        # 创建子账户
        child = Account.objects.create(
            user=user,
            name='子账户',
            parent=parent,
        )

        # 尝试将子账户设为默认应该失败
        child.is_default = True
        with pytest.raises(ValidationError):
            child.full_clean()

    def test_can_set_parent_account_as_default(self, user):
        """测试可以将父账户设为默认"""
        from api.models import Account

        parent = Account.objects.create(
            user=user,
            name='父账户',
            is_default=True,
        )

        assert parent.is_default is True
        assert parent.parent is None

    def test_change_default_account(self, user):
        """测试切换默认账户"""
        from api.models import Account

        # 创建第一个默认账户
        account1 = Account.objects.create(
            user=user,
            name='账户1',
            is_default=True,
        )

        # 创建第二个账户
        account2 = Account.objects.create(
            user=user,
            name='账户2',
            is_default=False,
        )

        # 将第二个账户设为默认（应该自动取消第一个）
        account2.is_default = True
        account2.save()

        # 刷新第一个账户
        account1.refresh_from_db()

        assert account1.is_default is False
        assert account2.is_default is True


@pytest.mark.django_db
class TestParentAccountPositionConstraints:
    """测试父账户持仓约束"""

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
        )

    def test_parent_account_cannot_have_position(self, user, fund):
        """测试父账户不能有持仓"""
        from api.models import Account, Position

        # 创建父账户
        parent = Account.objects.create(
            user=user,
            name='父账户',
        )

        # 尝试为父账户创建持仓应该失败
        position = Position(
            account=parent,
            fund=fund,
            holding_share=Decimal('100'),
        )

        with pytest.raises(ValidationError):
            position.full_clean()

    def test_child_account_can_have_position(self, user, fund):
        """测试子账户可以有持仓"""
        from api.models import Account, Position

        # 创建父账户
        parent = Account.objects.create(
            user=user,
            name='父账户',
        )

        # 创建子账户
        child = Account.objects.create(
            user=user,
            name='子账户',
            parent=parent,
        )

        # 为子账户创建持仓应该成功
        position = Position.objects.create(
            account=child,
            fund=fund,
            holding_share=Decimal('100'),
        )

        assert position.account == child
        assert position.fund == fund

    def test_position_account_must_be_child(self, user, fund):
        """测试 Position.account 必须是子账户"""
        from api.models import Account, Position

        # 创建父账户（没有 parent）
        parent = Account.objects.create(
            user=user,
            name='父账户',
        )

        # 尝试为父账户创建持仓
        with pytest.raises(ValidationError):
            position = Position(
                account=parent,
                fund=fund,
                holding_share=Decimal('100'),
            )
            position.full_clean()

    def test_position_operation_account_must_be_child(self, user, fund):
        """测试 PositionOperation.account 必须是子账户"""
        from api.models import Account, PositionOperation
        from datetime import date

        # 创建父账户
        parent = Account.objects.create(
            user=user,
            name='父账户',
        )

        # 尝试为父账户创建操作流水应该失败
        operation = PositionOperation(
            account=parent,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        with pytest.raises(ValidationError):
            operation.full_clean()

    def test_position_operation_with_child_account_succeeds(self, user, fund):
        """测试子账户可以创建操作流水"""
        from api.models import Account, PositionOperation
        from datetime import date

        # 创建父账户和子账户
        parent = Account.objects.create(
            user=user,
            name='父账户',
        )

        child = Account.objects.create(
            user=user,
            name='子账户',
            parent=parent,
        )

        # 为子账户创建操作流水应该成功
        operation = PositionOperation.objects.create(
            account=child,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        assert operation.account == child


@pytest.mark.django_db
class TestAccountHierarchyConstraints:
    """测试账户层级约束"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    def test_max_two_levels(self, user):
        """测试最多两层：父账户 -> 子账户"""
        from api.models import Account

        # 创建父账户
        parent = Account.objects.create(
            user=user,
            name='父账户',
        )

        # 创建子账户
        child = Account.objects.create(
            user=user,
            name='子账户',
            parent=parent,
        )

        # 尝试创建孙账户应该失败
        with pytest.raises(ValidationError):
            grandchild = Account(
                user=user,
                name='孙账户',
                parent=child,
            )
            grandchild.full_clean()

    def test_child_account_cannot_be_parent(self, user):
        """测试子账户不能再有子账户"""
        from api.models import Account

        parent = Account.objects.create(
            user=user,
            name='父账户',
        )

        child = Account.objects.create(
            user=user,
            name='子账户',
            parent=parent,
        )

        # 尝试将子账户作为父账户
        with pytest.raises(ValidationError):
            another_child = Account(
                user=user,
                name='另一个子账户',
                parent=child,
            )
            another_child.full_clean()
