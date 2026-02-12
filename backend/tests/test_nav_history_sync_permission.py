"""
测试历史净值同步接口权限

测试点：
1. 未认证用户调用 sync → 401
2. 普通用户调用 sync → 403
3. 管理员调用 sync → 200
"""
import pytest
from django.test import Client
from django.contrib.auth import get_user_model


@pytest.mark.django_db
class TestNavHistorySyncPermission:
    """历史净值同步权限测试"""

    def test_sync_requires_authentication(self):
        """未认证用户调用 sync 应返回 401"""
        client = Client()
        response = client.post('/api/nav-history/sync/',
                              {'fund_codes': ['000001']},
                              content_type='application/json')

        assert response.status_code == 401

    def test_sync_requires_admin(self):
        """普通用户调用 sync 应返回 403"""
        User = get_user_model()
        user = User.objects.create_user(
            username='normaluser',
            password='testpass123',
            is_staff=False,
            is_superuser=False
        )

        client = Client()

        # 登录普通用户
        login_response = client.post('/api/auth/login',
                                    {
                                        'username': 'normaluser',
                                        'password': 'testpass123'
                                    },
                                    content_type='application/json')

        access_token = login_response.json()['access_token']

        # 调用 sync 接口
        response = client.post('/api/nav-history/sync/',
                              {'fund_codes': ['000001']},
                              content_type='application/json',
                              HTTP_AUTHORIZATION=f'Bearer {access_token}')

        assert response.status_code == 403

    def test_sync_admin_success(self):
        """管理员调用 sync 应返回 200"""
        User = get_user_model()
        admin = User.objects.create_user(
            username='admin',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )

        client = Client()

        # 登录管理员
        login_response = client.post('/api/auth/login',
                                    {
                                        'username': 'admin',
                                        'password': 'adminpass123'
                                    },
                                    content_type='application/json')

        access_token = login_response.json()['access_token']

        # 调用 sync 接口
        response = client.post('/api/nav-history/sync/',
                              {'fund_codes': ['000001']},
                              content_type='application/json',
                              HTTP_AUTHORIZATION=f'Bearer {access_token}')

        # 应该返回 200（即使基金不存在，也应该返回成功的响应结构）
        assert response.status_code == 200
