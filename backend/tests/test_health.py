"""
测试 /health 接口

测试点：
1. 接口返回 200
2. 返回正确的 JSON 格式
3. 包含数据库连接状态
4. 包含系统初始化状态
"""

import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestHealthAPI:
    """健康检查接口测试"""

    def test_health_endpoint_exists(self):
        """测试 /health 接口存在"""
        client = Client()
        response = client.get("/api/health/")
        assert response.status_code == 200

    def test_health_response_format(self):
        """测试返回格式"""
        client = Client()
        response = client.get("/api/health/")
        data = response.json()

        assert "status" in data
        assert "database" in data
        assert "system_initialized" in data
        assert data["status"] == "ok"

    def test_health_database_connection(self):
        """测试数据库连接状态"""
        client = Client()
        response = client.get("/api/health/")
        data = response.json()

        assert data["database"] in ["connected", "disconnected"]

    def test_health_system_initialized_status(self):
        """测试系统初始化状态"""
        client = Client()
        response = client.get("/api/health/")
        data = response.json()

        assert isinstance(data["system_initialized"], bool)
