"""
测试净值同步多源 Fallback（M3）

测试点：
1. eastmoney 有数据 → danjuan 不调用
2. eastmoney 空 → danjuan 有数据 → 正确写入
3. eastmoney 空 → danjuan 也空 → count=0
4. eastmoney 空 → danjuan 未注册 → 不崩溃
5. eastmoney 空 → danjuan 抛异常 → 不崩溃
6. batch_sync_nav_history 间接受益
"""

import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import patch, MagicMock, call

from api.models import Fund, FundNavHistory
from api.services.nav_history import sync_nav_history, batch_sync_nav_history


@pytest.mark.django_db
class TestNavHistoryMultiSource:
    """sync_nav_history 多源 fallback 测试"""

    @pytest.fixture
    def fund(self):
        return Fund.objects.create(
            fund_code="000001",
            fund_name="测试基金",
        )

    @pytest.fixture
    def nav_data_eastmoney(self):
        return [
            {
                "nav_date": date(2024, 1, 1),
                "unit_nav": Decimal("1.1000"),
                "accumulated_nav": Decimal("2.1000"),
                "daily_growth": Decimal("0.5"),
            },
        ]

    @pytest.fixture
    def nav_data_danjuan(self):
        return [
            {
                "nav_date": date(2024, 6, 15),
                "unit_nav": Decimal("1.4070"),
                "accumulated_nav": None,
                "daily_growth": Decimal("3.61"),
            },
            {
                "nav_date": date(2024, 6, 14),
                "unit_nav": Decimal("1.3580"),
                "accumulated_nav": None,
                "daily_growth": Decimal("-1.20"),
            },
        ]

    # ──────────────────────────────────────────
    # eastmoney 成功，不调 danjuan
    # ──────────────────────────────────────────

    def test_eastmoney_success_no_danjuan_call(self, fund, nav_data_eastmoney):
        """eastmoney 有数据时，不调用 danjuan"""
        mock_eastmoney = MagicMock()
        mock_eastmoney.fetch_nav_history.return_value = nav_data_eastmoney

        mock_danjuan = MagicMock()

        def get_source(name):
            if name == "eastmoney":
                return mock_eastmoney
            elif name == "danjuan":
                return mock_danjuan
            return None

        with patch(
            "api.services.nav_history.SourceRegistry.get_source",
            side_effect=get_source,
        ):
            count = sync_nav_history("000001")

        assert count == 1
        # danjuan 的 fetch_nav_history 不应被调用
        mock_danjuan.fetch_nav_history.assert_not_called()

    # ──────────────────────────────────────────
    # eastmoney 空 → danjuan 有数据
    # ──────────────────────────────────────────

    def test_eastmoney_empty_fallback_danjuan_success(
        self, fund, nav_data_danjuan
    ):
        """eastmoney 返回空，danjuan 返回数据 → 写入 danjuan 数据"""
        mock_eastmoney = MagicMock()
        mock_eastmoney.fetch_nav_history.return_value = []

        mock_danjuan = MagicMock()
        mock_danjuan.fetch_nav_history.return_value = nav_data_danjuan

        def get_source(name):
            if name == "eastmoney":
                return mock_eastmoney
            elif name == "danjuan":
                return mock_danjuan
            return None

        with patch(
            "api.services.nav_history.SourceRegistry.get_source",
            side_effect=get_source,
        ):
            count = sync_nav_history("000001")

        assert count == 2
        assert FundNavHistory.objects.filter(fund=fund).count() == 2
        assert FundNavHistory.objects.filter(
            fund=fund, nav_date=date(2024, 6, 15)
        ).exists()
        assert FundNavHistory.objects.filter(
            fund=fund, nav_date=date(2024, 6, 14)
        ).exists()

    # ──────────────────────────────────────────
    # 两个源都空
    # ──────────────────────────────────────────

    def test_both_empty_returns_zero(self, fund):
        """eastmoney 空，danjuan 也空 → 返回 0"""
        mock_eastmoney = MagicMock()
        mock_eastmoney.fetch_nav_history.return_value = []

        mock_danjuan = MagicMock()
        mock_danjuan.fetch_nav_history.return_value = []

        def get_source(name):
            if name == "eastmoney":
                return mock_eastmoney
            elif name == "danjuan":
                return mock_danjuan
            return None

        with patch(
            "api.services.nav_history.SourceRegistry.get_source",
            side_effect=get_source,
        ):
            count = sync_nav_history("000001")

        assert count == 0
        assert FundNavHistory.objects.filter(fund=fund).count() == 0

    # ──────────────────────────────────────────
    # danjuan 未注册 → 不崩溃
    # ──────────────────────────────────────────

    def test_danjuan_not_registered_no_crash(self, fund):
        """danjuan 未注册到 SourceRegistry → 跳过 fallback，不崩溃"""
        mock_eastmoney = MagicMock()
        mock_eastmoney.fetch_nav_history.return_value = []

        def get_source(name):
            if name == "eastmoney":
                return mock_eastmoney
            # danjuan 和其他的都返回 None
            return None

        with patch(
            "api.services.nav_history.SourceRegistry.get_source",
            side_effect=get_source,
        ):
            count = sync_nav_history("000001")

        assert count == 0
        assert FundNavHistory.objects.filter(fund=fund).count() == 0

    # ──────────────────────────────────────────
    # danjuan 抛异常 → 不崩溃
    # ──────────────────────────────────────────

    def test_danjuan_raises_no_crash(self, fund):
        """danjuan.fetch_nav_history 抛异常 → 捕获，返回 count=0"""
        mock_eastmoney = MagicMock()
        mock_eastmoney.fetch_nav_history.return_value = []

        mock_danjuan = MagicMock()
        mock_danjuan.fetch_nav_history.side_effect = Exception(
            "danjuan API error"
        )

        def get_source(name):
            if name == "eastmoney":
                return mock_eastmoney
            elif name == "danjuan":
                return mock_danjuan
            return None

        with patch(
            "api.services.nav_history.SourceRegistry.get_source",
            side_effect=get_source,
        ):
            count = sync_nav_history("000001")

        assert count == 0
        assert FundNavHistory.objects.filter(fund=fund).count() == 0

    # ──────────────────────────────────────────
    # 回写 Fund.latest_nav
    # ──────────────────────────────────────────

    def test_latest_nav_backfill_from_danjuan(self, fund, nav_data_danjuan):
        """danjuan 数据写入后，Fund.latest_nav 正确回写"""
        mock_eastmoney = MagicMock()
        mock_eastmoney.fetch_nav_history.return_value = []

        mock_danjuan = MagicMock()
        mock_danjuan.fetch_nav_history.return_value = nav_data_danjuan

        def get_source(name):
            if name == "eastmoney":
                return mock_eastmoney
            elif name == "danjuan":
                return mock_danjuan
            return None

        with patch(
            "api.services.nav_history.SourceRegistry.get_source",
            side_effect=get_source,
        ):
            sync_nav_history("000001")

        fund.refresh_from_db()
        assert fund.latest_nav == Decimal("1.4070")
        assert fund.latest_nav_date == date(2024, 6, 15)


@pytest.mark.django_db
class TestBatchSyncMultiSource:
    """batch_sync_nav_history 多源 fallback 测试"""

    @pytest.fixture
    def funds(self):
        return [
            Fund.objects.create(fund_code="000001", fund_name="基金1"),
            Fund.objects.create(fund_code="000002", fund_name="基金2"),
        ]

    def test_batch_sync_mixed_results(self, funds):
        """基金1 eastmoney 有数据，基金2 需要 danjuan fallback"""
        mock_eastmoney = MagicMock()

        def eastmoney_nav(code, start_date=None, end_date=None):
            if code == "000001":
                return [
                    {
                        "nav_date": date(2024, 1, 1),
                        "unit_nav": Decimal("1.1000"),
                        "accumulated_nav": None,
                        "daily_growth": Decimal("0.5"),
                    },
                ]
            return []  # 000002 无数据

        mock_eastmoney.fetch_nav_history.side_effect = eastmoney_nav

        mock_danjuan = MagicMock()

        def danjuan_nav(code, start_date=None, end_date=None):
            if code == "000002":
                return [
                    {
                        "nav_date": date(2024, 6, 15),
                        "unit_nav": Decimal("1.4070"),
                        "accumulated_nav": None,
                        "daily_growth": Decimal("3.61"),
                    },
                ]
            return []

        mock_danjuan.fetch_nav_history.side_effect = danjuan_nav

        def get_source(name):
            if name == "eastmoney":
                return mock_eastmoney
            elif name == "danjuan":
                return mock_danjuan
            return None

        with patch(
            "api.services.nav_history.SourceRegistry.get_source",
            side_effect=get_source,
        ):
            results = batch_sync_nav_history(["000001", "000002"])

        assert results["000001"]["success"] is True
        assert results["000001"]["count"] == 1
        assert results["000002"]["success"] is True
        assert results["000002"]["count"] == 1

        # 两个基金都有净值记录
        assert FundNavHistory.objects.filter(fund=funds[0]).count() == 1
        assert FundNavHistory.objects.filter(fund=funds[1]).count() == 1
