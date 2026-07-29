"""
测试 M3 功能2: 估值 fallback 链 akshare → penetration → unavailable
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch, MagicMock
from django.utils import timezone
from rest_framework.test import APIClient


# ================================================================
# fetch_estimate fallback 链
# ================================================================

class TestFetchEstimateFallback:
    """EastMoneySource.fetch_estimate() fallback 链"""

    def test_akshare_success_no_penetration(self):
        """akshare 成功 → 不调穿透估算"""
        from api.sources.eastmoney import EastMoneySource

        source = EastMoneySource()

        with patch.object(source, "_get_estimate_engine") as mock_ak_engine:
            mock_ak_engine.return_value.get_estimate.return_value = {
                "fund_code": "000001",
                "fund_name": "华夏成长",
                "estimate_nav": Decimal("1.137"),
                "estimate_growth": Decimal("1.0"),
                "estimate_time": timezone.now(),
            }

            with patch.object(source, "_get_penetration_engine") as mock_pen:
                result = source.fetch_estimate("000001")

        assert result is not None
        assert result["estimate_source"] == "akshare"
        # 穿透引擎不应被调用
        mock_pen.assert_not_called()

    def test_akshare_none_falls_back_to_penetration(self):
        """akshare 返回 None → 调穿透估算"""
        from api.sources.eastmoney import EastMoneySource

        source = EastMoneySource()

        with patch.object(source, "_get_estimate_engine") as mock_ak:
            mock_ak.return_value.get_estimate.return_value = None

            with patch.object(source, "_get_penetration_engine") as mock_pen:
                mock_pen.return_value.estimate.return_value = (
                    {
                        "fund_code": "159915",
                        "estimate_nav": Decimal("1.2395"),
                        "estimate_growth": Decimal("0.41"),
                        "estimate_time": timezone.now(),
                        "method": "penetration",
                    },
                    "success",
                )

                result = source.fetch_estimate("510050")

        assert result is not None
        assert result.get("estimate_source") == "penetration", (
            f"穿透估算结果应有 estimate_source='penetration', 实际: {result}"
        )
        mock_pen.return_value.estimate.assert_called_once()

    def test_akshare_exception_falls_back_to_penetration(self):
        """akshare 抛异常 → 调穿透估算"""
        from api.sources.eastmoney import EastMoneySource

        source = EastMoneySource()

        with patch.object(source, "_get_estimate_engine") as mock_ak:
            mock_ak.return_value.get_estimate.side_effect = RuntimeError("boom")

            with patch.object(source, "_get_penetration_engine") as mock_pen:
                mock_pen.return_value.estimate.return_value = (
                    {
                        "fund_code": "510050",
                        "estimate_nav": Decimal("1.2"),
                        "estimate_growth": Decimal("0.5"),
                        "estimate_time": timezone.now(),
                        "method": "penetration",
                    },
                    "success",
                )

                result = source.fetch_estimate("510050")

        assert result is not None
        assert result["estimate_source"] == "penetration"

    def test_both_fail_returns_none(self):
        """akshare 失败 + 穿透估算不可用 → 返回 None"""
        from api.sources.eastmoney import EastMoneySource

        source = EastMoneySource()

        with patch.object(source, "_get_estimate_engine") as mock_ak:
            mock_ak.return_value.get_estimate.return_value = None

            with patch.object(source, "_get_penetration_engine") as mock_pen:
                mock_pen.return_value.estimate.return_value = (None, "not_applicable")

                result = source.fetch_estimate("000001")

        assert result is None

    def test_penetration_not_applicable_for_bond(self):
        """债券型 → 穿透估算不可用 → akshare 也不可用 → 返回 None"""
        from api.sources.eastmoney import EastMoneySource

        source = EastMoneySource()

        with patch.object(source, "_get_estimate_engine") as mock_ak:
            mock_ak.return_value.get_estimate.return_value = None

            with patch.object(source, "_get_penetration_engine") as mock_pen:
                mock_pen.return_value.estimate.return_value = (None, "not_applicable")

                result = source.fetch_estimate("000001")

        assert result is None
        mock_pen.return_value.estimate.assert_called_once()


# ================================================================
# _get_penetration_engine 懒加载
# ================================================================

class TestGetPenetrationEngine:
    """_get_penetration_engine() 懒加载"""

    def test_returns_engine_instance(self):
        """返回 PenetrationEngine 实例"""
        from api.sources.eastmoney import EastMoneySource
        from api.sources.penetration_engine import PenetrationEngine

        source = EastMoneySource()
        engine = source._get_penetration_engine()

        assert isinstance(engine, PenetrationEngine)

    def test_returns_same_instance(self):
        """多次调用返回同一实例"""
        from api.sources.eastmoney import EastMoneySource

        source = EastMoneySource()
        e1 = source._get_penetration_engine()
        e2 = source._get_penetration_engine()
        assert e1 is e2, "应该返回同一实例"


# ================================================================
# batch_estimate 穿透估算标注
# ================================================================

@pytest.mark.django_db
class TestBatchEstimatePenetrationSource:
    """batch_estimate 中穿透估算的 estimate_source 标注"""

    def setup_method(self):
        from api.models import Fund

        self.client = APIClient()
        Fund.objects.create(
            fund_code="510050", fund_name="上证50ETF",
            fund_type="ETF-场内", latest_nav=Decimal("1.2000"),
        )
        Fund.objects.create(
            fund_code="000001", fund_name="华夏成长",
            fund_type="混合型", latest_nav=Decimal("1.1000"),
        )

    def test_penetration_source_in_batch(self):
        """akshare None → 穿透估算成功 → batch 结果标记 estimate_source='penetration'"""
        with patch("api.sources.eastmoney.EastMoneySource.fetch_estimate") as mock_fetch:
            mock_fetch.return_value = {
                "fund_code": "510050",
                "estimate_nav": Decimal("1.2050"),
                "estimate_growth": Decimal("0.42"),
                "estimate_time": timezone.now(),
                "estimate_source": "penetration",
            }

            response = self.client.post(
                "/api/funds/batch_estimate/",
                {"fund_codes": ["510050", "000001"]},
                format="json",
            )

        assert response.status_code == 200
        data = response.json()
        # 穿透估算成功
        assert data["510050"].get("estimate_source") == "penetration", (
            f"穿透估算应有来源标记, 实际: {data['510050']}"
        )
