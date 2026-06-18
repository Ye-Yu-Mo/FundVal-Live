"""
测试 M4: 后端 API 集成（danjuan 偏好 + 估值 fallback + 基金详情）
"""

import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import patch, MagicMock
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model

from api.models import Fund

User = get_user_model()

NAV_DATE = date(2026, 6, 17)
factory = APIRequestFactory()


@pytest.mark.django_db
class TestDanjuanIntegration:
    """M4 后端 API 集成测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.user = User.objects.create_user(username="test", password="pass")
        self.fund = Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
            latest_nav=Decimal("1.4070"),
            latest_nav_date=NAV_DATE,
        )

    # ─────────────────────────────────────
    # 1. UserPreference — 直接用 ViewSet（不走 URL 路由）
    # ─────────────────────────────────────

    def test_preference_accepts_danjuan(self):
        from api.viewsets import UserPreferenceViewSet

        req = factory.put("/", {"preferred_source": "danjuan"}, format="json")
        force_authenticate(req, user=self.user)
        view = UserPreferenceViewSet.as_view({"put": "update"})
        resp = view(req)
        assert resp.status_code == 200
        assert resp.data["preferred_source"] == "danjuan"

    def test_preference_rejects_invalid(self):
        from api.viewsets import UserPreferenceViewSet

        req = factory.put("/", {"preferred_source": "nope"}, format="json")
        force_authenticate(req, user=self.user)
        view = UserPreferenceViewSet.as_view({"put": "update"})
        resp = view(req)
        assert resp.status_code == 400

    def test_preference_other_sources_work(self):
        from api.viewsets import UserPreferenceViewSet

        for s in ["eastmoney", "yangjibao", "xiaobeiyangji"]:
            req = factory.put("/", {"preferred_source": s}, format="json")
            force_authenticate(req, user=self.user)
            view = UserPreferenceViewSet.as_view({"put": "update"})
            resp = view(req)
            assert resp.status_code == 200, s

    # ─────────────────────────────────────
    # 2. estimate fallback
    # ─────────────────────────────────────

    def test_estimate_danjuan_fallback(self):
        from api.viewsets import FundViewSet

        mock_source = MagicMock()
        mock_source.fetch_estimate.return_value = {
            "fund_code": "000001",
            "fund_name": "测试",
            "estimate_nav": Decimal("1.4100"),
            "estimate_growth": Decimal("0.32"),
            "estimate_time": MagicMock(),
        }

        with patch(
            "api.viewsets.SourceRegistry.get_source", return_value=mock_source
        ):
            req = factory.get("/?source=danjuan")
            force_authenticate(req, user=self.user)
            view = FundViewSet.as_view({"get": "estimate"})
            resp = view(req, fund_code="000001")

        assert resp.status_code == 200
        assert "error" not in resp.data

    def test_estimate_eastmoney_still_works(self):
        from api.viewsets import FundViewSet

        mock_source = MagicMock()
        mock_source.fetch_estimate.return_value = {
            "fund_code": "000001",
            "fund_name": "测试",
            "estimate_nav": Decimal("1.4100"),
            "estimate_growth": Decimal("0.32"),
            "estimate_time": MagicMock(),
        }

        with patch(
            "api.viewsets.SourceRegistry.get_source", return_value=mock_source
        ):
            req = factory.get("/?source=eastmoney")
            force_authenticate(req, user=self.user)
            view = FundViewSet.as_view({"get": "estimate"})
            resp = view(req, fund_code="000001")

        assert resp.status_code == 200

    # ─────────────────────────────────────
    # 3. batch_estimate fallback
    # ─────────────────────────────────────

    def test_batch_estimate_danjuan_fallback(self):
        from api.viewsets import FundViewSet

        mock_source = MagicMock()
        mock_source.fetch_estimate.return_value = {
            "fund_code": "000001",
            "fund_name": "测试",
            "estimate_nav": Decimal("1.4100"),
            "estimate_growth": Decimal("0.32"),
            "estimate_time": MagicMock(),
        }

        with patch(
            "api.viewsets.SourceRegistry.get_source", return_value=mock_source
        ):
            req = factory.post(
                "/",
                {"fund_codes": ["000001"], "source": "danjuan"},
                format="json",
            )
            force_authenticate(req, user=self.user)
            view = FundViewSet.as_view({"post": "batch_estimate"})
            resp = view(req)

        assert resp.status_code == 200
        assert "error" not in resp.data.get("000001", {})

    # ─────────────────────────────────────
    # 4. fund_detail action
    # ─────────────────────────────────────

    def test_fund_detail_danjuan_success(self):
        from api.viewsets import FundViewSet

        mock_source = MagicMock()
        mock_source.fetch_fund_detail.return_value = {
            "fund_code": "000001",
            "fund_name": "华夏成长混合",
            "fund_type": "3",
            "risk_level": "4",
            "manager_name": "张三",
            "company_name": "华夏基金",
            "latest_nav": Decimal("1.4070"),
            "nav_date": NAV_DATE,
            "period_returns": {"1m": Decimal("12.92")},
            "peer_ranking": {"1m": "995/5347"},
        }

        with patch(
            "api.viewsets.SourceRegistry.get_source", return_value=mock_source
        ):
            req = factory.get("/?source=danjuan")
            force_authenticate(req, user=self.user)
            view = FundViewSet.as_view({"get": "fund_detail"})
            resp = view(req, fund_code="000001")

        assert resp.status_code == 200
        assert resp.data["detail"]["peer_ranking"]["1m"] == "995/5347"

    def test_fund_detail_danjuan_no_data(self):
        from api.viewsets import FundViewSet

        mock_source = MagicMock()
        mock_source.fetch_fund_detail.return_value = None

        with patch(
            "api.viewsets.SourceRegistry.get_source", return_value=mock_source
        ):
            req = factory.get("/?source=danjuan")
            force_authenticate(req, user=self.user)
            view = FundViewSet.as_view({"get": "fund_detail"})
            resp = view(req, fund_code="000001")

        assert resp.status_code == 404

    def test_fund_detail_eastmoney_unsupported(self):
        from api.viewsets import FundViewSet

        req = factory.get("/?source=eastmoney")
        force_authenticate(req, user=self.user)
        view = FundViewSet.as_view({"get": "fund_detail"})
        resp = view(req, fund_code="000001")

        assert resp.status_code == 400
