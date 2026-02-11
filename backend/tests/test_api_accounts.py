"""
测试账户相关 API

测试点：
1. 账户列表
2. 创建账户
3. 账户详情
4. 更新账户
5. 删除账户
6. 父子账户关系
7. 默认账户
"""
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestAccountListAPI:
    """测试账户列表 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def other_user(self):
        return User.objects.create_user(username='otheruser', password='pass')

    @pytest.fixture
    def accounts(self, user):
        from api.models import Account
        return [
            Account.objects.create(user=user, name='账户1'),
            Account.objects.create(user=user, name='账户2'),
        ]

    def test_list_accounts_authenticated(self, client, user, accounts):
        """测试认证用户查看自己的账户列表"""
        client.force_authenticate(user=user)
        response = client.get('/api/accounts/')
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_list_accounts_only_own(self, client, user, other_user, accounts):
        """测试只能看到自己的账户"""
        from api.models import Account
        Account.objects.create(user=other_user, name='其他人的账户')

        client.force_authenticate(user=user)
        response = client.get('/api/accounts/')
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_list_accounts_unauthenticated(self, client):
        """测试未认证用户不能查看账户"""
        response = client.get('/api/accounts/')
        assert response.status_code == 401


@pytest.mark.django_db
class TestAccountCreateAPI:
    """测试创建账户 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    def test_create_account(self, client, user):
        """测试创建账户"""
        client.force_authenticate(user=user)
        response = client.post('/api/accounts/', {
            'name': '我的账户',
        })
        assert response.status_code == 201
        assert response.data['name'] == '我的账户'
        assert response.data['is_default'] is False

    def test_create_default_account(self, client, user):
        """测试创建默认账户"""
        client.force_authenticate(user=user)
        response = client.post('/api/accounts/', {
            'name': '默认账户',
            'is_default': True,
        })
        assert response.status_code == 201
        assert response.data['is_default'] is True

    def test_create_child_account(self, client, user):
        """测试创建子账户"""
        from api.models import Account
        parent = Account.objects.create(user=user, name='总账户')

        client.force_authenticate(user=user)
        response = client.post('/api/accounts/', {
            'name': '子账户',
            'parent': str(parent.id),
        })
        assert response.status_code == 201
        assert response.data['parent'] == str(parent.id)

    def test_create_account_duplicate_name(self, client, user):
        """测试创建重名账户"""
        from api.models import Account
        Account.objects.create(user=user, name='我的账户')

        client.force_authenticate(user=user)
        response = client.post('/api/accounts/', {
            'name': '我的账户',
        })
        assert response.status_code == 400

    def test_create_account_unauthenticated(self, client):
        """测试未认证用户不能创建账户"""
        response = client.post('/api/accounts/', {
            'name': '我的账户',
        })
        assert response.status_code == 401


@pytest.mark.django_db
class TestAccountDetailAPI:
    """测试账户详情 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def other_user(self):
        return User.objects.create_user(username='otheruser', password='pass')

    @pytest.fixture
    def account(self, user, create_child_account):
        return create_child_account(user, '我的账户')

    def test_get_account_detail(self, client, user, account):
        """测试获取账户详情"""
        client.force_authenticate(user=user)
        response = client.get(f'/api/accounts/{account.id}/')
        assert response.status_code == 200
        assert response.data['name'] == '我的账户'

    def test_get_other_user_account(self, client, other_user, account):
        """测试不能查看其他用户的账户"""
        client.force_authenticate(user=other_user)
        response = client.get(f'/api/accounts/{account.id}/')
        assert response.status_code == 404

    def test_get_nonexistent_account(self, client, user):
        """测试获取不存在的账户"""
        client.force_authenticate(user=user)
        response = client.get('/api/accounts/00000000-0000-0000-0000-000000000000/')
        assert response.status_code == 404


@pytest.mark.django_db
class TestAccountUpdateAPI:
    """测试更新账户 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user, create_child_account):
        return create_child_account(user, '我的账户')

    def test_update_account_name(self, client, user, account):
        """测试更新账户名称"""
        client.force_authenticate(user=user)
        response = client.put(f'/api/accounts/{account.id}/', {
            'name': '新名称',
        })
        assert response.status_code == 200
        assert response.data['name'] == '新名称'

    def test_update_account_to_default(self, client, user):
        """测试设置为默认账户（只能设置父账户为默认）"""
        from api.models import Account

        # 创建父账户
        parent_account = Account.objects.create(user=user, name='父账户')

        client.force_authenticate(user=user)
        response = client.put(f'/api/accounts/{parent_account.id}/', {
            'name': '父账户',
            'is_default': True,
        })
        assert response.status_code == 200
        assert response.data['is_default'] is True

    def test_partial_update_account(self, client, user, account):
        """测试部分更新账户"""
        client.force_authenticate(user=user)
        response = client.patch(f'/api/accounts/{account.id}/', {
            'name': '新名称',
        })
        assert response.status_code == 200
        assert response.data['name'] == '新名称'


@pytest.mark.django_db
class TestAccountDeleteAPI:
    """测试删除账户 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user, create_child_account):
        return create_child_account(user, '我的账户')

    def test_delete_account(self, client, user, account):
        """测试删除账户"""
        client.force_authenticate(user=user)
        response = client.delete(f'/api/accounts/{account.id}/')
        assert response.status_code == 204

        from api.models import Account
        assert not Account.objects.filter(id=account.id).exists()

    def test_delete_account_with_positions(self, client, user, account):
        """测试删除有持仓的账户"""
        from api.models import Fund, Position
        fund = Fund.objects.create(fund_code='000001', fund_name='测试基金')
        Position.objects.create(
            account=account,
            fund=fund,
            holding_share=100,
        )

        client.force_authenticate(user=user)
        response = client.delete(f'/api/accounts/{account.id}/')
        # 应该级联删除持仓
        assert response.status_code == 204


@pytest.mark.django_db
class TestAccountPositionsAPI:
    """测试获取账户持仓 API"""

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
        from decimal import Decimal

        fund1 = Fund.objects.create(fund_code='000001', fund_name='基金1')
        fund2 = Fund.objects.create(fund_code='000002', fund_name='基金2')

        return [
            Position.objects.create(
                account=account,
                fund=fund1,
                holding_share=Decimal('100'),
                holding_cost=Decimal('1000'),
                holding_nav=Decimal('10'),
            ),
            Position.objects.create(
                account=account,
                fund=fund2,
                holding_share=Decimal('200'),
                holding_cost=Decimal('2000'),
                holding_nav=Decimal('10'),
            ),
        ]

    def test_get_account_positions(self, client, user, account, positions):
        """测试获取账户的所有持仓"""
        client.force_authenticate(user=user)
        response = client.get(f'/api/accounts/{account.id}/positions/')
        assert response.status_code == 200
        assert len(response.data) == 2
