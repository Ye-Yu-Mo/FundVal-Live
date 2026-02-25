"""
测试用户数据源偏好功能

测试点：
1. UserPreference 模型
2. GET /api/preferences/ - 获取偏好
3. PUT /api/preferences/ - 更新偏好
"""
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


# ─────────────────────────────────────────────
# 1. UserPreference 模型
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestUserPreferenceModel:

    def test_create_preference(self):
        """测试创建偏好"""
        from api.models import UserPreference
        user = User.objects.create_user(username='u1', password='pass')

        pref = UserPreference.objects.create(user=user, preferred_source='eastmoney')

        assert pref.preferred_source == 'eastmoney'
        assert pref.user == user

    def test_default_source_is_eastmoney(self):
        """测试默认数据源是 eastmoney"""
        from api.models import UserPreference
        user = User.objects.create_user(username='u2', password='pass')

        pref = UserPreference.objects.create(user=user)

        assert pref.preferred_source == 'eastmoney'

    def test_unique_per_user(self):
        """测试每个用户只能有一条偏好记录"""
        from api.models import UserPreference
        from django.db import IntegrityError
        user = User.objects.create_user(username='u3', password='pass')

        UserPreference.objects.create(user=user, preferred_source='eastmoney')

        with pytest.raises(IntegrityError):
            UserPreference.objects.create(user=user, preferred_source='yangjibao')

    def test_different_users_can_have_preferences(self):
        """测试不同用户可以各有偏好"""
        from api.models import UserPreference
        u1 = User.objects.create_user(username='u4', password='pass')
        u2 = User.objects.create_user(username='u5', password='pass')

        UserPreference.objects.create(user=u1, preferred_source='eastmoney')
        UserPreference.objects.create(user=u2, preferred_source='yangjibao')

        assert UserPreference.objects.filter(user=u1).first().preferred_source == 'eastmoney'
        assert UserPreference.objects.filter(user=u2).first().preferred_source == 'yangjibao'


# ─────────────────────────────────────────────
# 2. GET /api/preferences/
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestGetPreference:

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client.force_authenticate(user=self.user)

    def test_get_preference_returns_default(self):
        """测试无偏好记录时返回默认值"""
        response = self.client.get('/api/preferences/')

        assert response.status_code == 200
        assert response.json()['preferred_source'] == 'eastmoney'

    def test_get_preference_returns_saved(self):
        """测试返回已保存的偏好"""
        from api.models import UserPreference
        UserPreference.objects.create(user=self.user, preferred_source='yangjibao')

        response = self.client.get('/api/preferences/')

        assert response.status_code == 200
        assert response.json()['preferred_source'] == 'yangjibao'

    def test_get_preference_unauthenticated(self):
        """测试未登录时返回 401"""
        client = APIClient()
        response = client.get('/api/preferences/')

        assert response.status_code == 401


# ─────────────────────────────────────────────
# 3. PUT /api/preferences/
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestUpdatePreference:

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client.force_authenticate(user=self.user)

    def test_update_preference_creates_if_not_exists(self):
        """测试无记录时 PUT 自动创建"""
        response = self.client.put('/api/preferences/', {'preferred_source': 'yangjibao'}, format='json')

        assert response.status_code == 200
        assert response.json()['preferred_source'] == 'yangjibao'

    def test_update_preference_updates_existing(self):
        """测试更新已有偏好"""
        from api.models import UserPreference
        UserPreference.objects.create(user=self.user, preferred_source='eastmoney')

        response = self.client.put('/api/preferences/', {'preferred_source': 'yangjibao'}, format='json')

        assert response.status_code == 200
        assert response.json()['preferred_source'] == 'yangjibao'

    def test_update_preference_invalid_source(self):
        """测试无效数据源返回 400"""
        response = self.client.put('/api/preferences/', {'preferred_source': 'invalid_source'}, format='json')

        assert response.status_code == 400

    def test_update_preference_unauthenticated(self):
        """测试未登录时返回 401"""
        client = APIClient()
        response = client.put('/api/preferences/', {'preferred_source': 'yangjibao'}, format='json')

        assert response.status_code == 401

    def test_update_preference_idempotent(self):
        """测试多次 PUT 只有一条记录"""
        from api.models import UserPreference

        self.client.put('/api/preferences/', {'preferred_source': 'yangjibao'}, format='json')
        self.client.put('/api/preferences/', {'preferred_source': 'eastmoney'}, format='json')

        assert UserPreference.objects.filter(user=self.user).count() == 1
        assert UserPreference.objects.get(user=self.user).preferred_source == 'eastmoney'
