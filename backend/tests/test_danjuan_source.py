"""
测试 DanjuanSource（雪球基金 / 蛋卷基金数据源）— M1 更新

M1 (2026-07-29): danjuanfunds.com 返回 403 IP 封禁，所有 API 端点不可用。
fetch_nav_history / fetch_realtime_nav / fetch_today_nav / fetch_fund_detail
全部改为立即返回空/None + 日志。fetch_estimate 本来就是 None，不变。

保留原始数据验证测试（test_empty_items / test_network_error 等），
因为它们在 M1 下仍然通过（返回空/None）。
"""

import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import patch, MagicMock


# ================================================================
# fetch_nav_history — M1: 返回 [] + log
# ================================================================

class TestDanjuanNavHistory:
    """DanjuanSource.fetch_nav_history — M1: 直接返回 []"""

    def test_returns_empty_list(self):
        """M1: 不发起 HTTP 请求，直接返回 []"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        with patch("requests.get") as mock_get:
            result = source.fetch_nav_history("000001")

        assert result == []
        mock_get.assert_not_called()

    def test_returns_empty_list_with_date_range(self):
        """M1: 带日期范围也返回 []"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        result = source.fetch_nav_history(
            "000001", start_date=date(2026, 6, 15), end_date=date(2026, 6, 16)
        )
        assert result == []

    def test_logs_warning(self):
        """M1: 记录 403 封禁的 warning 日志"""
        import logging
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        with patch("logging.Logger.warning") as mock_warning:
            source.fetch_nav_history("000001")
            mock_warning.assert_called()
            args = str(mock_warning.call_args)
            assert "403" in args or "封禁" in args or "不可用" in args


# ================================================================
# fetch_realtime_nav — M1: 返回 None
# ================================================================

class TestDanjuanRealtimeNav:
    """DanjuanSource.fetch_realtime_nav — M1: 直接返回 None"""

    def test_returns_none(self):
        """M1: fetch_realtime_nav 直接返回 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        with patch("requests.get") as mock_get:
            result = source.fetch_realtime_nav("000001")

        assert result is None
        mock_get.assert_not_called()


# ================================================================
# fetch_today_nav — M1: 返回 None
# ================================================================

class TestDanjuanTodayNav:
    """DanjuanSource.fetch_today_nav — M1: 直接返回 None"""

    def test_returns_none(self):
        """M1: fetch_today_nav 直接返回 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        with patch("requests.get") as mock_get:
            result = source.fetch_today_nav("000001")

        assert result is None
        mock_get.assert_not_called()


# ================================================================
# fetch_estimate — 不变（本来就是 None）
# ================================================================

class TestDanjuanEstimate:
    """DanjuanSource.fetch_estimate — 行为不变"""

    def test_returns_none(self):
        """fetch_estimate 从第一天起就返回 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        result = source.fetch_estimate("000001")
        assert result is None


# ================================================================
# fetch_fund_detail — M1: 返回 None
# ================================================================

class TestDanjuanFundDetail:
    """DanjuanSource.fetch_fund_detail — M1: 直接返回 None"""

    def test_returns_none(self):
        """M1: fetch_fund_detail 直接返回 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        with patch("requests.get") as mock_get:
            result = source.fetch_fund_detail("000001")

        assert result is None
        mock_get.assert_not_called()

    def test_logs_warning(self):
        """M1: 记录 403 封禁的 warning 日志"""
        import logging
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        with patch("logging.Logger.warning") as mock_warning:
            source.fetch_fund_detail("000001")
            mock_warning.assert_called()


# ================================================================
# 非受影响方法 — 行为不变
# ================================================================

class TestDanjuanOtherMethods:
    """get_source_name / get_login_type / fetch_fund_list — 不受 M1 影响"""

    def test_get_source_name(self):
        from api.sources.danjuan import DanjuanSource
        source = DanjuanSource()
        assert source.get_source_name() == "danjuan"

    def test_get_login_type(self):
        from api.sources.danjuan import DanjuanSource
        source = DanjuanSource()
        assert source.get_login_type() == "none"

    def test_fetch_fund_list_raises(self):
        from api.sources.danjuan import DanjuanSource
        source = DanjuanSource()
        with pytest.raises(NotImplementedError):
            source.fetch_fund_list()


class TestDanjuanRegistry:
    """SourceRegistry 集成 — 蛋卷仍然注册"""

    def test_registry_has_danjuan(self):
        from api.sources.registry import SourceRegistry
        assert "danjuan" in SourceRegistry.list_sources()

    def test_registry_get_danjuan(self):
        from api.sources.registry import SourceRegistry
        source = SourceRegistry.get_source("danjuan")
        assert source is not None
        assert source.get_source_name() == "danjuan"
