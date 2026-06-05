"""
测试夜间模式偏好 API

测试点：
1. 首次获取返回默认 theme_mode=light
2. 更新 theme_mode 为 dark
3. 无效值被拒绝
"""

import pytest
from django.test import Client
from django.contrib.auth import get_user_model


def _get_token(client, username, password):
    resp = client.post(
        "/api/auth/login",
        {"username": username, "password": password},
        content_type="application/json",
    )
    return resp.json()["access_token"]


@pytest.mark.django_db
class TestThemePreference:
    def test_default_theme_is_light(self):
        User = get_user_model()
        User.objects.create_user(username="user", password="pass1")

        client = Client()
        token = _get_token(client, "user", "pass1")
        resp = client.get("/api/preferences/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme_mode"] == "light"

    def test_update_theme_to_dark(self):
        User = get_user_model()
        User.objects.create_user(username="user", password="pass1")

        client = Client()
        token = _get_token(client, "user", "pass1")
        resp = client.put(
            "/api/preferences/",
            {"theme_mode": "dark"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 200
        assert resp.json()["theme_mode"] == "dark"

        # 验证持久化
        resp2 = client.get("/api/preferences/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp2.json()["theme_mode"] == "dark"

    def test_invalid_theme_rejected(self):
        User = get_user_model()
        User.objects.create_user(username="user", password="pass1")

        client = Client()
        token = _get_token(client, "user", "pass1")
        resp = client.put(
            "/api/preferences/",
            {"theme_mode": "blue"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 400

    def test_theme_switch_does_not_affect_source(self):
        User = get_user_model()
        User.objects.create_user(username="user", password="pass1")

        client = Client()
        token = _get_token(client, "user", "pass1")
        # 先设 source
        client.put(
            "/api/preferences/",
            {"preferred_source": "yangjibao"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        # 再切 theme
        client.put(
            "/api/preferences/",
            {"theme_mode": "dark"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        # source 应保持不变
        resp = client.get("/api/preferences/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.json()["preferred_source"] == "yangjibao"
        assert resp.json()["theme_mode"] == "dark"
