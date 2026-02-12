"""
测试历史净值同步接口权限

测试点：
1. 未认证用户同步 ≤15 个基金 → 200（允许）
2. 未认证用户同步 >15 个基金 → 403（拒绝）
3. 普通用户同步 ≤15 个基金 → 200（允许）
4. 普通用户同步 >15 个基金 → 403（拒绝）
5. 管理员同步任意数量基金 → 200（允许）
"""
import pytest
from django.test import Client
from django.contrib.auth import get_user_model


@pytest.mark.django_db
class TestNavHistorySyncPermission:
    """历史净值同步权限测试"""

    def test_sync_unauthenticated_small_batch(self):
        """未认证用户同步 ≤15 个基金应返回 200"""
        client = Client()
        response = client.post('/api/nav-history/sync/',
                              {'fund_codes': ['000001']},
                              content_type='application/json')

        assert response.status_code == 200

    def test_sync_unauthenticated_large_batch(self):
        """未认证用户同步 >15 个基金应返回 403"""
        client = Client()
        # 生成 16 个基金代码
        fund_codes = [f'{i:06d}' for i in range(16)]
        response = client.post('/api/nav-history/sync/',
                              {'fund_codes': fund_codes},
                              content_type='application/json')

        assert response.status_code == 403
        assert '超过 15 个基金' in response.data['error']

    def test_sync_normal_user_small_batch(self):
        """普通用户同步 ≤15 个基金应返回 200"""
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

        # 调用 sync 接口（≤15 个基金）
        response = client.post('/api/nav-history/sync/',
                              {'fund_codes': ['000001']},
                              content_type='application/json',
                              HTTP_AUTHORIZATION=f'Bearer {access_token}')

        assert response.status_code == 200

    def test_sync_normal_user_large_batch(self):
        """普通用户同步 >15 个基金应返回 403"""
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

        # 调用 sync 接口（>15 个基金）
        fund_codes = [f'{i:06d}' for i in range(16)]
        response = client.post('/api/nav-history/sync/',
                              {'fund_codes': fund_codes},
                              content_type='application/json',
                              HTTP_AUTHORIZATION=f'Bearer {access_token}')

        assert response.status_code == 403
        assert '超过 15 个基金' in response.data['error']

    def test_sync_admin_large_batch(self):
        """管理员同步 >15 个基金应返回 200"""
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

        # 调用 sync 接口（>15 个基金）
        fund_codes = [f'{i:06d}' for i in range(16)]
        response = client.post('/api/nav-history/sync/',
                              {'fund_codes': fund_codes},
                              content_type='application/json',
                              HTTP_AUTHORIZATION=f'Bearer {access_token}')

        # 应该返回 200（即使基金不存在，也应该返回成功的响应结构）
        assert response.status_code == 200
