"""
测试 Account 模型

测试点：
1. 账户创建
2. 父子账户关系
3. 默认账户
4. 用户名下账户名唯一性
"""
import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestAccountModel:
    """Account 模型测试"""

    @pytest.fixture
    def user(self):
        """创建测试用户"""
        return User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_create_account(self, user):
        """测试创建账户"""
        from api.models import Account

        account = Account.objects.create(
            user=user,
            name='我的账户',
        )

        assert account.user == user
        assert account.name == '我的账户'
        assert account.parent is None
        assert account.is_default is False

    def test_parent_child_account(self, user):
        """测试父子账户关系"""
        from api.models import Account

        parent = Account.objects.create(
            user=user,
            name='总账户',
        )

        child = Account.objects.create(
            user=user,
            name='子账户',
            parent=parent,
        )

        assert child.parent == parent
        assert child.parent.name == '总账户'

    def test_default_account(self, user):
        """测试默认账户"""
        from api.models import Account

        account = Account.objects.create(
            user=user,
            name='默认账户',
            is_default=True,
        )

        assert account.is_default is True

    def test_account_name_unique_per_user(self, user):
        """测试同一用户下账户名唯一"""
        from api.models import Account
        from django.core.exceptions import ValidationError

        Account.objects.create(
            user=user,
            name='我的账户',
        )

        # 同一用户重复账户名应该报错
        with pytest.raises((IntegrityError, ValidationError)):
            Account.objects.create(
                user=user,
                name='我的账户',
            )

    def test_different_users_can_have_same_account_name(self):
        """测试不同用户可以有相同账户名"""
        from api.models import Account

        user1 = User.objects.create_user(username='user1', password='pass1')
        user2 = User.objects.create_user(username='user2', password='pass2')

        account1 = Account.objects.create(user=user1, name='我的账户')
        account2 = Account.objects.create(user=user2, name='我的账户')

        assert account1.name == account2.name
        assert account1.user != account2.user

    def test_delete_parent_cascades_to_children(self, user):
        """测试删除父账户会级联删除子账户"""
        from api.models import Account

        parent = Account.objects.create(user=user, name='总账户')
        child = Account.objects.create(user=user, name='子账户', parent=parent)

        parent_id = parent.id
        child_id = child.id

        parent.delete()

        # 父账户和子账户都应该被删除
        assert not Account.objects.filter(id=parent_id).exists()
        assert not Account.objects.filter(id=child_id).exists()
