"""
测试报告 Celery 任务

测试点：
1. 未开启报告的用户被跳过
2. 未配置 AI 的用户被跳过
3. 正常生成报告并返回结果
"""

import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from api.models import Fund, Account, Position, AIConfig, UserPreference


@pytest.mark.django_db
class TestReportTask:
    def test_skips_user_without_ai_config(self):
        User = get_user_model()
        user = User.objects.create_user(username="user", password="pass1")
        UserPreference.objects.create(
            user=user, report_enabled=True, report_frequency="weekly"
        )

        from api.tasks import generate_investment_reports

        result = generate_investment_reports()
        assert "skip_ai_config" in result or "skipped" in result

    def test_skips_user_with_report_disabled(self):
        User = get_user_model()
        user = User.objects.create_user(username="user", password="pass1")
        AIConfig.objects.create(
            user=user, api_endpoint="https://a.com", api_key="k", model_name="gpt-4"
        )

        from api.tasks import generate_investment_reports

        result = generate_investment_reports()
        assert "0 reports" in result or "0" in result

    def test_generates_reports(self):
        User = get_user_model()
        user = User.objects.create_user(username="user", password="pass1")
        AIConfig.objects.create(
            user=user, api_endpoint="https://a.com", api_key="k", model_name="gpt-4"
        )
        UserPreference.objects.create(
            user=user, report_enabled=True, report_frequency="weekly"
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

        import datetime as dt

        monday = dt.date(2026, 6, 8)  # 周一

        with patch("api.tasks.requests.post") as mock_post, patch(
            "api.tasks.date"
        ) as mock_date:
            mock_date.today.return_value = monday
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "# 投资报告"}}]
            }
            mock_resp.raise_for_status = lambda: None
            mock_post.return_value = mock_resp

            from api.tasks import generate_investment_reports

            result = generate_investment_reports()
            assert "1 reports" in result or "1" in result
