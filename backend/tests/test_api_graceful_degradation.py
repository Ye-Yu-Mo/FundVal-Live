"""
测试 M1 功能5: 后端 API 估值失败优雅降级

- FundViewSet.estimate → None 时返回 unavailable: true (不是 400 error)
- FundViewSet.batch_estimate → None 时标记 unavailable: true
- FundViewSet.sync → NotImplementedError 时返回明确错误提示
"""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestEstimateGracefulDegradation:
    """FundViewSet.estimate — 估值不可用时返回 unavailable: true"""

    def setup_method(self):
        from api.models import Fund

        self.client = APIClient()
        self.fund = Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
            latest_nav=Decimal("1.1000"),
        )

    def test_returns_unavailable_when_estimate_is_none(self):
        """fetch_estimate 返回 None → 200 + unavailable: true（不是 400 error）"""
        with patch("api.sources.eastmoney.EastMoneySource.fetch_estimate") as mock_fetch:
            mock_fetch.return_value = None

            response = self.client.get("/api/funds/000001/estimate/?source=eastmoney")

        assert response.status_code == 200, (
            f"应返回 200 而非 {response.status_code}: {response.data}"
        )
        data = response.json()
        assert data.get("unavailable") is True, f"应有 unavailable: true, 实际: {data}"
        assert "fund_code" in data
        assert "message" in data or data.get("estimate_nav") is None

    def test_estimate_still_works_when_data_valid(self):
        """fetch_estimate 返回有效数据时行为不变"""
        with patch("api.sources.eastmoney.EastMoneySource.fetch_estimate") as mock_fetch:
            mock_fetch.return_value = {
                "fund_code": "000001",
                "fund_name": "华夏成长混合",
                "estimate_nav": Decimal("1.1370"),
                "estimate_growth": Decimal("-1.05"),
                "estimate_time": timezone.now(),
            }

            response = self.client.get("/api/funds/000001/estimate/?source=eastmoney")

        assert response.status_code == 200
        data = response.json()
        assert data.get("unavailable") is not True, "有效数据不应有 unavailable 标记"
        assert data["fund_code"] == "000001"

    def test_danjuan_fallback_still_works(self):
        """蛋卷估值 fallback 到 eastmoney 的逻辑不变"""
        with patch("api.sources.eastmoney.EastMoneySource.fetch_estimate") as mock_fetch:
            mock_fetch.return_value = None  # eastmoney 也返回 None（M1 行为）

            response = self.client.get("/api/funds/000001/estimate/?source=danjuan")

        # danjuan fallback 到 eastmoney，然后 eastmoney 返回 unavailable
        assert response.status_code == 200
        assert response.json().get("unavailable") is True


@pytest.mark.django_db
class TestBatchEstimateGracefulDegradation:
    """FundViewSet.batch_estimate — 批量估值不可用时标记"""

    def setup_method(self):
        from api.models import Fund

        self.client = APIClient()
        Fund.objects.create(
            fund_code="000001",
            fund_name="基金1",
            latest_nav=Decimal("1.1000"),
        )
        Fund.objects.create(
            fund_code="000002",
            fund_name="基金2",
            latest_nav=Decimal("2.2000"),
        )

    def test_unavailable_funds_marked_in_batch(self):
        """fetch_estimate 返回 None → 批量结果中标记 unavailable"""
        with patch("api.sources.eastmoney.EastMoneySource.fetch_estimate") as mock_fetch:
            mock_fetch.return_value = None  # 所有估值返回 None

            response = self.client.post(
                "/api/funds/batch_estimate/",
                {"fund_codes": ["000001", "000002"]},
                format="json",
            )

        assert response.status_code == 200
        data = response.json()

        # 每个基金都应该有 unavailable 标记
        for code in ["000001", "000002"]:
            assert code in data, f"batch 结果应有 {code}"
            fund_result = data[code]
            assert fund_result.get("unavailable") is True, (
                f"{code} 应有 unavailable: true, 实际: {fund_result}"
            )
            assert "error" not in fund_result, f"{code} 不应返回 error, 实际: {fund_result}"

    def test_batch_mixed_available_and_unavailable(self):
        """部分估值可用，部分不可用"""
        with patch("api.sources.eastmoney.EastMoneySource.fetch_estimate") as mock_fetch:

            def side_effect(code):
                if code == "000001":
                    return {
                        "fund_code": "000001",
                        "fund_name": "基金1",
                        "estimate_nav": Decimal("1.1370"),
                        "estimate_growth": Decimal("1.0"),
                        "estimate_time": timezone.now(),
                    }
                return None  # 000002 不可用

            mock_fetch.side_effect = side_effect

            response = self.client.post(
                "/api/funds/batch_estimate/",
                {"fund_codes": ["000001", "000002"]},
                format="json",
            )

        assert response.status_code == 200
        data = response.json()

        # 000001 有估值数据
        assert data["000001"].get("unavailable") is not True
        assert data["000001"]["estimate_nav"] is not None

        # 000002 标记为不可用
        assert data["000002"].get("unavailable") is True


@pytest.mark.django_db
class TestSyncGracefulDegradation:
    """FundViewSet.sync — M2: 基金列表同步通过 akshare 恢复"""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            username="admin", password="admin123", email="admin@test.com"
        )
        self.client.force_authenticate(user=self.user)

    @patch("akshare.fund_name_em")
    def test_sync_returns_success(self, mock_ak):
        """M2: sync 通过 akshare 正常返回基金列表"""
        import pandas as pd

        mock_ak.return_value = pd.DataFrame(
            [
                {"基金代码": "000001", "基金简称": "华夏成长", "基金类型": "混合型"},
            ]
        )

        response = self.client.post("/api/funds/sync/")

        assert response.status_code == 200, (
            f"应为 200, 实际 {response.status_code}: {response.data}"
        )
        data = response.json()
        assert data["total"] == 1
        assert data["created"] > 0 or data["updated"] > 0
