"""
测试 AI 报告预览 API

测试点：
1. 无 AI 配置返回错误
2. 有 AI 配置时返回报告预览（mock AI 调用）
3. 无持仓用户返回空报告
"""

import pytest
from unittest.mock import patch
from django.test import Client
from django.contrib.auth import get_user_model
from api.models import Fund, Account, Position, AIConfig, AIPromptTemplate


def _get_token(client, username, password):
    resp = client.post(
        "/api/auth/login",
        {"username": username, "password": password},
        content_type="application/json",
    )
    return resp.json()["access_token"]


@pytest.mark.django_db
class TestReportPreview:
    def test_no_ai_config_returns_error(self):
        User = get_user_model()
        User.objects.create_user(username="user", password="pass1")

        client = Client()
        token = _get_token(client, "user", "pass1")
        resp = client.post(
            "/api/ai/report-preview/",
            {"period": "weekly"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 400
        assert "未配置" in resp.json()["error"]

    def test_preview_with_ai_returns_report(self):
        User = get_user_model()
        user = User.objects.create_user(username="user", password="pass1")
        AIConfig.objects.create(
            user=user,
            api_endpoint="https://api.test.com",
            api_key="test-key",
            model_name="gpt-4",
        )
        parent = Account.objects.create(
            user=user, name="主账户", parent=None, is_default=True
        )
        child = Account.objects.create(user=user, name="子账户", parent=parent)
        fund = Fund.objects.create(
            fund_code="000001", fund_name="测试基金", latest_nav="1.5"
        )
        Position.objects.create(
            account=child,
            fund=fund,
            holding_share="100",
            holding_cost="120.00",
            holding_nav="1.2",
        )

        client = Client()
        token = _get_token(client, "user", "pass1")

        with patch("api.views.requests.post") as mock_post:
            mock_resp = mock_post.return_value
            mock_resp.json.return_value = {
                "choices": [
                    {"message": {"content": "# 投资周报\n\n本周盈亏: +100.00 元"}}
                ]
            }
            mock_resp.raise_for_status = lambda: None

            resp = client.post(
                "/api/ai/report-preview/",
                {"period": "weekly", "template_id": ""},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "result" in data
            assert "# 投资周报" in data["result"]

    def test_no_positions_returns_empty_report(self):
        User = get_user_model()
        user = User.objects.create_user(username="user", password="pass1")
        AIConfig.objects.create(
            user=user,
            api_endpoint="https://api.test.com",
            api_key="test-key",
            model_name="gpt-4",
        )

        client = Client()
        token = _get_token(client, "user", "pass1")

        with patch("api.views.requests.post") as mock_post:
            mock_resp = mock_post.return_value
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "暂无持仓数据"}}]
            }
            mock_resp.raise_for_status = lambda: None

            resp = client.post(
                "/api/ai/report-preview/",
                {"period": "monthly"},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )
            assert resp.status_code == 200
            assert "result" in resp.json()
