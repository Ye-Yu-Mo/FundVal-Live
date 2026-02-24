"""
测试养基宝登录与会话管理功能

测试点：
1. BaseEstimateSource.login / logout 抽象方法
2. YangJiBaoSource 登录实现
3. UserSourceCredential 模型
4. SourceCredentialViewSet API
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


# ─────────────────────────────────────────────
# 1. 抽象基类
# ─────────────────────────────────────────────

class TestBaseEstimateSourceLoginMethods:
    """BaseEstimateSource 登录抽象方法测试"""

    def test_login_abstract_method_exists(self):
        """login 抽象方法存在"""
        from api.sources.base import BaseEstimateSource
        assert hasattr(BaseEstimateSource, 'login')

    def test_logout_abstract_method_exists(self):
        """logout 抽象方法存在"""
        from api.sources.base import BaseEstimateSource
        assert hasattr(BaseEstimateSource, 'logout')

    def test_cannot_instantiate_without_implementing_login(self):
        """未实现 login/logout 不能实例化"""
        from api.sources.base import BaseEstimateSource

        class IncompleteSource(BaseEstimateSource):
            def get_source_name(self): return 'test'
            def fetch_estimate(self, code): pass
            def fetch_realtime_nav(self, code): pass
            def fetch_today_nav(self, code): pass
            def fetch_fund_list(self): pass
            # 故意不实现 login / logout

        with pytest.raises(TypeError):
            IncompleteSource()


# ─────────────────────────────────────────────
# 2. YangJiBaoSource 登录实现
# ─────────────────────────────────────────────

class TestYangJiBaoSourceLogin:
    """YangJiBaoSource.login 实现测试"""

    @patch('requests.post')
    def test_login_success(self, mock_post):
        """测试登录成功"""
        from api.sources.yangjibao import YangJiBaoSource

        mock_response = Mock()
        mock_response.json.return_value = {
            'code': 200,
            'data': {'token': 'test-token-abc123'}
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        source = YangJiBaoSource()
        result = source.login('testuser', 'testpass')

        assert result['success'] is True
        assert result['token'] == 'test-token-abc123'
        assert 'error' not in result or result['error'] is None

    @patch('requests.post')
    def test_login_wrong_password(self, mock_post):
        """测试密码错误"""
        from api.sources.yangjibao import YangJiBaoSource

        mock_response = Mock()
        mock_response.json.return_value = {
            'code': 401,
            'message': '用户名或密码错误'
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        source = YangJiBaoSource()
        result = source.login('testuser', 'wrongpass')

        assert result['success'] is False
        assert result['token'] is None
        assert '用户名或密码错误' in result['error']

    @patch('requests.post')
    def test_login_network_error(self, mock_post):
        """测试网络错误"""
        from api.sources.yangjibao import YangJiBaoSource

        mock_post.side_effect = Exception('Network error')

        source = YangJiBaoSource()
        result = source.login('testuser', 'testpass')

        assert result['success'] is False
        assert result['token'] is None
        assert result['error'] is not None

    def test_logout_clears_token(self):
        """测试登出清除 token"""
        from api.sources.yangjibao import YangJiBaoSource

        source = YangJiBaoSource()
        source._token = 'some-token'

        source.logout()

        assert source._token is None

    def test_get_source_name(self):
        """测试数据源名称"""
        from api.sources.yangjibao import YangJiBaoSource

        source = YangJiBaoSource()
        assert source.get_source_name() == 'yangjibao'


# ─────────────────────────────────────────────
# 3. UserSourceCredential 模型
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestUserSourceCredentialModel:
    """UserSourceCredential 模型测试"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    def test_create_credential(self, user):
        """测试创建凭证"""
        from api.models import UserSourceCredential

        cred = UserSourceCredential.objects.create(
            user=user,
            source_name='yangjibao',
            token='test-token-abc123',
        )

        assert cred.user == user
        assert cred.source_name == 'yangjibao'
        assert cred.token == 'test-token-abc123'
        assert cred.is_active is True

    def test_unique_per_user_and_source(self, user):
        """测试同一用户同一数据源只能有一条凭证"""
        from api.models import UserSourceCredential
        from django.db import IntegrityError

        UserSourceCredential.objects.create(
            user=user,
            source_name='yangjibao',
            token='token-1',
        )

        with pytest.raises(IntegrityError):
            UserSourceCredential.objects.create(
                user=user,
                source_name='yangjibao',
                token='token-2',
            )

    def test_different_users_can_have_same_source(self, user):
        """测试不同用户可以有同一数据源的凭证"""
        from api.models import UserSourceCredential

        user2 = User.objects.create_user(username='user2', password='pass')

        UserSourceCredential.objects.create(
            user=user,
            source_name='yangjibao',
            token='token-user1',
        )
        UserSourceCredential.objects.create(
            user=user2,
            source_name='yangjibao',
            token='token-user2',
        )

        assert UserSourceCredential.objects.filter(source_name='yangjibao').count() == 2

    def test_is_active_default_true(self, user):
        """测试 is_active 默认为 True"""
        from api.models import UserSourceCredential

        cred = UserSourceCredential.objects.create(
            user=user,
            source_name='yangjibao',
            token='test-token',
        )

        assert cred.is_active is True

    def test_deactivate_credential(self, user):
        """测试停用凭证"""
        from api.models import UserSourceCredential

        cred = UserSourceCredential.objects.create(
            user=user,
            source_name='yangjibao',
            token='test-token',
        )

        cred.is_active = False
        cred.save()

        cred.refresh_from_db()
        assert cred.is_active is False


# ─────────────────────────────────────────────
# 4. SourceCredentialViewSet API
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestSourceCredentialAPI:
    """SourceCredentialViewSet API 测试"""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client.force_authenticate(user=self.user)

    @patch('api.sources.yangjibao.requests.post')
    def test_login_success(self, mock_post):
        """测试登录接口成功"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'code': 200,
            'data': {'token': 'test-token-abc123'}
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        response = self.client.post('/api/source-credentials/login/', {
            'source_name': 'yangjibao',
            'username': 'yjb_user',
            'password': 'yjb_pass',
        }, format='json')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['source_name'] == 'yangjibao'

    @patch('api.sources.yangjibao.requests.post')
    def test_login_saves_credential(self, mock_post):
        """测试登录成功后保存凭证"""
        from api.models import UserSourceCredential

        mock_response = Mock()
        mock_response.json.return_value = {
            'code': 200,
            'data': {'token': 'test-token-abc123'}
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        self.client.post('/api/source-credentials/login/', {
            'source_name': 'yangjibao',
            'username': 'yjb_user',
            'password': 'yjb_pass',
        }, format='json')

        cred = UserSourceCredential.objects.get(user=self.user, source_name='yangjibao')
        assert cred.token == 'test-token-abc123'
        assert cred.is_active is True

    @patch('api.sources.yangjibao.requests.post')
    def test_login_wrong_password(self, mock_post):
        """测试登录失败"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'code': 401,
            'message': '用户名或密码错误'
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        response = self.client.post('/api/source-credentials/login/', {
            'source_name': 'yangjibao',
            'username': 'yjb_user',
            'password': 'wrong',
        }, format='json')

        assert response.status_code == 400
        data = response.json()
        assert data['success'] is False

    def test_login_unauthenticated(self):
        """测试未登录不能调用接口"""
        client = APIClient()
        response = client.post('/api/source-credentials/login/', {
            'source_name': 'yangjibao',
            'username': 'yjb_user',
            'password': 'yjb_pass',
        }, format='json')

        assert response.status_code == 401

    def test_logout_success(self):
        """测试登出接口"""
        from api.models import UserSourceCredential

        # 先创建凭证
        UserSourceCredential.objects.create(
            user=self.user,
            source_name='yangjibao',
            token='test-token',
            is_active=True,
        )

        response = self.client.post('/api/source-credentials/logout/', {
            'source_name': 'yangjibao',
        }, format='json')

        assert response.status_code == 200

        # 验证凭证已停用
        cred = UserSourceCredential.objects.get(user=self.user, source_name='yangjibao')
        assert cred.is_active is False

    def test_status_logged_in(self):
        """测试查询已登录状态"""
        from api.models import UserSourceCredential

        UserSourceCredential.objects.create(
            user=self.user,
            source_name='yangjibao',
            token='test-token',
            is_active=True,
        )

        response = self.client.get('/api/source-credentials/status/?source_name=yangjibao')

        assert response.status_code == 200
        data = response.json()
        assert data['logged_in'] is True
        assert data['source_name'] == 'yangjibao'

    def test_status_not_logged_in(self):
        """测试查询未登录状态"""
        response = self.client.get('/api/source-credentials/status/?source_name=yangjibao')

        assert response.status_code == 200
        data = response.json()
        assert data['logged_in'] is False

    def test_status_logged_out(self):
        """测试查询已登出状态"""
        from api.models import UserSourceCredential

        UserSourceCredential.objects.create(
            user=self.user,
            source_name='yangjibao',
            token='test-token',
            is_active=False,  # 已登出
        )

        response = self.client.get('/api/source-credentials/status/?source_name=yangjibao')

        assert response.status_code == 200
        data = response.json()
        assert data['logged_in'] is False

    def test_login_updates_existing_credential(self):
        """测试重复登录更新已有凭证"""
        from api.models import UserSourceCredential

        # 先创建旧凭证
        UserSourceCredential.objects.create(
            user=self.user,
            source_name='yangjibao',
            token='old-token',
            is_active=True,
        )

        with patch('api.sources.yangjibao.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                'code': 200,
                'data': {'token': 'new-token'}
            }
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            self.client.post('/api/source-credentials/login/', {
                'source_name': 'yangjibao',
                'username': 'yjb_user',
                'password': 'yjb_pass',
            }, format='json')

        # 验证只有一条凭证，且 token 已更新
        creds = UserSourceCredential.objects.filter(user=self.user, source_name='yangjibao')
        assert creds.count() == 1
        assert creds.first().token == 'new-token'

    def test_login_unsupported_source(self):
        """测试不支持的数据源"""
        response = self.client.post('/api/source-credentials/login/', {
            'source_name': 'nonexistent_source',
            'username': 'user',
            'password': 'pass',
        }, format='json')

        assert response.status_code == 400
