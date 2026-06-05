"""
测试管理员统计 API 和任务触发

测试点：
1. stats 端点返回正确的系统统计数据
2. trigger_task 白名单校验
3. 非管理员访问返回 403
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import Client
from django.contrib.auth import get_user_model
from api.models import Fund


def _get_token(client, username, password):
    resp = client.post(
        "/api/auth/login",
        {"username": username, "password": password},
        content_type="application/json",
    )
    return resp.json()["access_token"]


@pytest.mark.django_db
class TestAdminStats:
    def test_returns_correct_counts(self):
        User = get_user_model()
        User.objects.create_superuser(username="admin", password="admin123")
        User.objects.create_user(username="u1", password="p1")
        User.objects.create_user(username="u2", password="p2")
        Fund.objects.create(fund_code="000001", fund_name="Test Fund")
        Fund.objects.create(fund_code="000002", fund_name="Test Fund 2")

        client = Client()
        token = _get_token(client, "admin", "admin123")
        resp = client.get("/api/admin/stats/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_count"] == 3
        assert data["fund_count"] == 2
        assert "version" in data

    def test_non_admin_denied(self):
        User = get_user_model()
        User.objects.create_superuser(username="admin", password="admin123")
        User.objects.create_user(username="normal", password="pass1")

        client = Client()
        token = _get_token(client, "normal", "pass1")
        resp = client.get("/api/admin/stats/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestAdminTriggerTask:
    def test_trigger_update_fund_nav(self):
        User = get_user_model()
        User.objects.create_superuser(username="admin", password="admin123")

        client = Client()
        token = _get_token(client, "admin", "admin123")

        mock_result = MagicMock()
        mock_result.id = "fake-task-id-123"
        with patch("fundval.celery.app.send_task", return_value=mock_result):
            resp = client.post(
                "/api/admin/tasks/update_fund_nav/",
                HTTP_AUTHORIZATION=f"Bearer {token}",
                content_type="application/json",
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "triggered"
        assert data["task_id"] == "fake-task-id-123"

    def test_trigger_unknown_task_returns_400(self):
        User = get_user_model()
        User.objects.create_superuser(username="admin", password="admin123")

        client = Client()
        token = _get_token(client, "admin", "admin123")
        resp = client.post(
            "/api/admin/tasks/unknown_task/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_non_admin_cannot_trigger(self):
        User = get_user_model()
        User.objects.create_superuser(username="admin", password="admin123")
        User.objects.create_user(username="normal", password="pass1")

        client = Client()
        token = _get_token(client, "normal", "pass1")
        resp = client.post(
            "/api/admin/tasks/update_fund_nav/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            content_type="application/json",
        )
        assert resp.status_code == 403
