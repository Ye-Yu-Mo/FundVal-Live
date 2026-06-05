"""
测试 Bootstrap 初始化机制

测试点：
1. bootstrap_key 生成
2. 验证 bootstrap_key
3. 初始化系统（创建管理员）
4. 初始化后 bootstrap 接口失效（404/410）
5. system_initialized 状态更新
"""

import pytest
from django.test import Client
from fundval.config import config


@pytest.fixture(autouse=True)
def reset_system_state():
    """每个测试前重置系统状态"""
    config.set("system_initialized", False)
    yield
    # 测试后清理
    config.set("system_initialized", False)


@pytest.mark.django_db
class TestBootstrap:
    """Bootstrap 初始化测试"""

    def test_bootstrap_key_generated_on_startup(self):
        """测试启动时生成 bootstrap_key"""
        # 未初始化时应该有 bootstrap_key
        from fundval.bootstrap import get_bootstrap_key

        key = get_bootstrap_key()
        assert key is not None
        assert len(key) >= 32  # 高熵随机字符串

    def test_verify_bootstrap_key_valid(self):
        """测试验证有效的 bootstrap_key"""
        from fundval.bootstrap import get_bootstrap_key

        key = get_bootstrap_key()
        client = Client()

        response = client.post(
            "/api/admin/bootstrap/verify",
            {"bootstrap_key": key},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True

    def test_verify_bootstrap_key_invalid(self):
        """测试验证无效的 bootstrap_key"""
        client = Client()

        response = client.post(
            "/api/admin/bootstrap/verify",
            {"bootstrap_key": "invalid_key"},
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.json()
        assert data["valid"] is False

    def test_initialize_system_with_valid_key(self):
        """测试使用有效 key 初始化系统"""
        from fundval.bootstrap import get_bootstrap_key
        from django.contrib.auth import get_user_model

        User = get_user_model()
        key = get_bootstrap_key()
        client = Client()

        response = client.post(
            "/api/admin/bootstrap/initialize",
            {
                "bootstrap_key": key,
                "admin_username": "admin",
                "admin_password": "admin123456",
                "allow_register": False,
            },
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "系统初始化成功"

        # 验证管理员创建
        admin = User.objects.get(username="admin")
        assert admin.is_staff is True
        assert admin.is_superuser is True

        # 验证配置更新
        assert config.get("system_initialized") is True
        assert config.get("allow_register") is False

    def test_initialize_system_with_invalid_key(self):
        """测试使用无效 key 初始化系统"""
        client = Client()

        response = client.post(
            "/api/admin/bootstrap/initialize",
            {
                "bootstrap_key": "invalid_key",
                "admin_username": "admin",
                "admin_password": "admin123456",
                "allow_register": False,
            },
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_bootstrap_endpoints_disabled_after_init(self):
        """测试初始化后 bootstrap 接口失效"""
        from fundval.bootstrap import get_bootstrap_key

        # 先初始化系统
        key = get_bootstrap_key()
        client = Client()

        client.post(
            "/api/admin/bootstrap/initialize",
            {
                "bootstrap_key": key,
                "admin_username": "admin",
                "admin_password": "admin123456",
                "allow_register": False,
            },
            content_type="application/json",
        )

        # 初始化后再次访问应该返回 404 或 410
        response = client.post(
            "/api/admin/bootstrap/verify",
            {"bootstrap_key": key},
            content_type="application/json",
        )

        assert response.status_code in [404, 410]

    def test_cannot_initialize_twice(self):
        """测试不能重复初始化"""
        from fundval.bootstrap import get_bootstrap_key

        key = get_bootstrap_key()
        client = Client()

        # 第一次初始化
        client.post(
            "/api/admin/bootstrap/initialize",
            {
                "bootstrap_key": key,
                "admin_username": "admin",
                "admin_password": "admin123456",
                "allow_register": False,
            },
            content_type="application/json",
        )

        # 第二次初始化应该失败
        response = client.post(
            "/api/admin/bootstrap/initialize",
            {
                "bootstrap_key": key,
                "admin_username": "admin2",
                "admin_password": "admin123456",
                "allow_register": False,
            },
            content_type="application/json",
        )

        assert response.status_code in [404, 410]
