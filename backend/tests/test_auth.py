"""
测试用户认证系统

测试点：
1. 用户登录获取 JWT
2. JWT 刷新
3. 获取当前用户信息
4. 修改密码
5. 角色权限（admin/user）
"""

import pytest
from django.test import Client
from django.contrib.auth import get_user_model


@pytest.mark.django_db
class TestAuth:
    """用户认证测试"""

    def test_login_success(self):
        """测试登录成功"""
        User = get_user_model()
        User.objects.create_user(username="testuser", password="testpass123")

        client = Client()
        response = client.post(
            "/api/auth/login",
            {"username": "testuser", "password": "testpass123"},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "testuser"

    def test_login_invalid_credentials(self):
        """测试登录失败（错误密码）"""
        User = get_user_model()
        User.objects.create_user(username="testuser", password="testpass123")

        client = Client()
        response = client.post(
            "/api/auth/login",
            {"username": "testuser", "password": "wrongpass"},
            content_type="application/json",
        )

        assert response.status_code == 401

    def test_refresh_token(self):
        """测试刷新 token"""
        User = get_user_model()
        User.objects.create_user(username="testuser", password="testpass123")

        client = Client()

        # 先登录获取 token
        login_response = client.post(
            "/api/auth/login",
            {"username": "testuser", "password": "testpass123"},
            content_type="application/json",
        )

        refresh_token = login_response.json()["refresh_token"]

        # 刷新 token
        response = client.post(
            "/api/auth/refresh",
            {"refresh_token": refresh_token},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_get_current_user(self):
        """测试获取当前用户信息"""
        User = get_user_model()
        User.objects.create_user(username="testuser", password="testpass123")

        client = Client()

        # 先登录
        login_response = client.post(
            "/api/auth/login",
            {"username": "testuser", "password": "testpass123"},
            content_type="application/json",
        )

        access_token = login_response.json()["access_token"]

        # 获取用户信息
        response = client.get(
            "/api/auth/me", HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"

    def test_get_current_user_without_token(self):
        """测试未认证访问"""
        client = Client()
        response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_change_password(self):
        """测试修改密码"""
        User = get_user_model()
        User.objects.create_user(username="testuser", password="oldpass123")

        client = Client()

        # 先登录
        login_response = client.post(
            "/api/auth/login",
            {"username": "testuser", "password": "oldpass123"},
            content_type="application/json",
        )

        access_token = login_response.json()["access_token"]

        # 修改密码
        response = client.put(
            "/api/auth/password",
            {"old_password": "oldpass123", "new_password": "newpass123"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        assert response.status_code == 200

        # 用新密码登录
        new_login = client.post(
            "/api/auth/login",
            {"username": "testuser", "password": "newpass123"},
            content_type="application/json",
        )

        assert new_login.status_code == 200


@pytest.mark.django_db
class TestUserRoles:
    """用户角色测试"""

    def test_admin_role(self):
        """测试管理员角色"""
        User = get_user_model()
        admin = User.objects.create_superuser(
            username="admin", password="admin123", email="admin@example.com"
        )

        assert admin.is_staff is True
        assert admin.is_superuser is True

    def test_regular_user_role(self):
        """测试普通用户角色"""
        User = get_user_model()
        user = User.objects.create_user(username="user", password="user123")

        assert user.is_staff is False
        assert user.is_superuser is False
