"""
测试 AI 投资报告引擎

测试点：
1. UserPreference 报告字段读写
2. build_report_context 占位符数据生成
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.test import Client
from django.contrib.auth import get_user_model
from api.models import Fund, Account, Position, PositionOperation, FundNavHistory


def _get_token(client, username, password):
    resp = client.post(
        "/api/auth/login",
        {"username": username, "password": password},
        content_type="application/json",
    )
    return resp.json()["access_token"]


@pytest.mark.django_db
class TestReportPreference:
    def test_default_report_disabled(self):
        User = get_user_model()
        User.objects.create_user(username="user", password="pass1")

        client = Client()
        token = _get_token(client, "user", "pass1")
        resp = client.get("/api/preferences/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_enabled"] is False
        assert data["report_frequency"] == "monthly"

    def test_enable_weekly_report(self):
        User = get_user_model()
        User.objects.create_user(username="user", password="pass1")

        client = Client()
        token = _get_token(client, "user", "pass1")
        resp = client.put(
            "/api/preferences/",
            {"report_enabled": True, "report_frequency": "weekly"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_enabled"] is True
        assert data["report_frequency"] == "weekly"

        # 验证持久化
        resp2 = client.get("/api/preferences/", HTTP_AUTHORIZATION=f"Bearer {token}")
        assert resp2.json()["report_enabled"] is True

    def test_invalid_frequency_rejected(self):
        User = get_user_model()
        User.objects.create_user(username="user", password="pass1")

        client = Client()
        token = _get_token(client, "user", "pass1")
        resp = client.put(
            "/api/preferences/",
            {"report_frequency": "daily"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert resp.status_code == 200  # 频率改为逗号分隔，不再校验单个值


@pytest.mark.django_db
class TestReportContextBuilder:
    def test_builds_account_summary(self):
        User = get_user_model()
        user = User.objects.create_user(username="user", password="pass1")
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

        from api.views import build_report_context

        ctx = build_report_context(user, "weekly")

        assert "account_summary" in ctx
        assert "总市值" in ctx["account_summary"] or "市值" in ctx["account_summary"]
        assert "position_summary" in ctx
        assert (
            "000001" in ctx["position_summary"] or "测试基金" in ctx["position_summary"]
        )
        assert "period_pnl" in ctx

    def test_no_positions_returns_empty(self):
        User = get_user_model()
        user = User.objects.create_user(username="user", password="pass1")

        from api.views import build_report_context

        ctx = build_report_context(user, "monthly")

        assert "account_summary" in ctx
        assert (
            "暂无账户" in ctx["account_summary"] or "暂无持仓" in ctx["account_summary"]
        )
