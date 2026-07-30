"""
测试 DanjuanSource M1 清理

M1 (2026-07-29): danjuanfunds.com 返回 403 IP 封禁，所有 API 端点不可用。
所有对外方法改为立即返回空/None + 日志，保留原始代码在注释中。
"""

import logging
from datetime import date
from unittest.mock import patch

import pytest
from api.sources.danjuan import DanjuanSource

# ================================================================
# fetch_nav_history() → 返回 [] + warning 日志
# ================================================================


@pytest.mark.django_db
class TestDanjuanM1NavHistory:
    """M1: fetch_nav_history 返回空列表 + 日志"""

    def test_returns_empty_list(self):
        """fetch_nav_history 始终返回 []，不抛异常"""
        source = DanjuanSource()
        result = source.fetch_nav_history("000001")
        assert result == []

    def test_returns_empty_list_with_date_range(self):
        """带日期范围也返回 []"""
        source = DanjuanSource()
        result = source.fetch_nav_history(
            "000001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
        )
        assert result == []

    def test_logs_warning(self, caplog):
        """应记录蛋卷 403 不可用的 warning 日志"""
        caplog.set_level(logging.WARNING)

        source = DanjuanSource()
        source.fetch_nav_history("000001")

        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("403" in w or "不可用" in w or "封禁" in w for w in warnings), (
            f"应有蛋卷不可用的 warning 日志, 实际: {warnings}"
        )

    def test_does_not_make_http_request(self):
        """不应发起 HTTP 请求"""
        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            source.fetch_nav_history("000001")

        mock_get.assert_not_called()

    def test_code_preserved_as_comment(self):
        """原 API 调用代码应在注释中保留"""
        import inspect

        source_code, _ = inspect.getsourcelines(DanjuanSource)

        in_method = False
        method_lines = []
        for line in source_code:
            if "def fetch_nav_history" in line:
                in_method = True
                continue
            if in_method:
                # 只通过下一个 def 来检测方法结束
                if line.strip().startswith("def "):
                    break
                method_lines.append(line)

        # 原蛋卷 API 相关关键字应在注释中出现
        preserved_keywords = [
            "danjuanfunds",
            "NAV_HISTORY",
            "nav/history",
            "result_code",
            "unit_nav",
            "items",
        ]
        found = any(
            kw in line and "#" in line for line in method_lines for kw in preserved_keywords
        )
        assert found, f"原蛋卷 API 调用代码应在注释中保留，方法体行数: {len(method_lines)}"


# ================================================================
# fetch_realtime_nav() → 返回 None
# ================================================================


@pytest.mark.django_db
class TestDanjuanM1RealtimeNav:
    """M1: fetch_realtime_nav 返回 None"""

    def test_returns_none(self):
        """fetch_realtime_nav 始终返回 None"""
        source = DanjuanSource()
        result = source.fetch_realtime_nav("000001")
        assert result is None

    def test_does_not_make_http_request(self):
        """不应发起 HTTP 请求"""
        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            source.fetch_realtime_nav("000001")

        mock_get.assert_not_called()

    def test_code_preserved_as_comment(self):
        """原代码应在注释中保留"""
        import inspect

        source_code, _ = inspect.getsourcelines(DanjuanSource)

        in_method = False
        method_lines = []
        for line in source_code:
            if "def fetch_realtime_nav" in line:
                in_method = True
                continue
            if in_method:
                if line.strip().startswith("def "):
                    break
                method_lines.append(line)

        method_text = "".join(method_lines)
        assert "fetch_nav_history" in method_text or "history" in method_text.lower(), (
            "原代码应保留在注释中"
        )


# ================================================================
# fetch_fund_detail() → 返回 None
# ================================================================


@pytest.mark.django_db
class TestDanjuanM1FundDetail:
    """M1: fetch_fund_detail 返回 None"""

    def test_returns_none(self):
        """fetch_fund_detail 始终返回 None"""
        source = DanjuanSource()
        result = source.fetch_fund_detail("000001")
        assert result is None

    def test_logs_warning(self, caplog):
        """应记录 warning 日志"""
        caplog.set_level(logging.WARNING)

        source = DanjuanSource()
        source.fetch_fund_detail("000001")

        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("403" in w or "不可用" in w or "封禁" in w for w in warnings), (
            f"应有蛋卷不可用的 warning 日志, 实际: {warnings}"
        )

    def test_does_not_make_http_request(self):
        """不应发起 HTTP 请求"""
        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            source.fetch_fund_detail("000001")

        mock_get.assert_not_called()

    def test_code_preserved_as_comment(self):
        """原 API 调用代码应在注释中保留"""
        import inspect

        source_code, _ = inspect.getsourcelines(DanjuanSource)

        in_method = False
        method_lines = []
        for line in source_code:
            if "def fetch_fund_detail" in line:
                in_method = True
                continue
            if in_method:
                if line.strip().startswith("def "):
                    break
                method_lines.append(line)

        preserved_keywords = [
            "danjuanfunds",
            "FUND_DETAIL_URL",
            "result_code",
            "fund_derived",
            "period_returns",
        ]
        found = any(
            kw in line and "#" in line for line in method_lines for kw in preserved_keywords
        )
        assert found, f"原蛋卷 API 调用代码应在注释中保留，方法体行数: {len(method_lines)}"


# ================================================================
# fetch_today_nav() → 返回 None
# ================================================================


@pytest.mark.django_db
class TestDanjuanM1TodayNav:
    """M1: fetch_today_nav 返回 None"""

    def test_returns_none(self):
        """fetch_today_nav 始终返回 None"""
        source = DanjuanSource()
        result = source.fetch_today_nav("000001")
        assert result is None

    def test_does_not_make_http_request(self):
        """不应发起 HTTP 请求（不通过 fetch_nav_history 间接调用）"""
        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            source.fetch_today_nav("000001")

        mock_get.assert_not_called()


# ================================================================
# fetch_estimate() → 不变（本来就是 None）
# ================================================================


@pytest.mark.django_db
class TestDanjuanM1EstimateUnchanged:
    """M1: fetch_estimate 行为不变"""

    def test_still_returns_none(self):
        """fetch_estimate 本来就返回 None，M1 不改变"""
        source = DanjuanSource()
        result = source.fetch_estimate("000001")
        assert result is None


# ================================================================
# 非受影响方法 → 行为不变
# ================================================================


@pytest.mark.django_db
class TestDanjuanM1Unaffected:
    """M1 不应影响 fetch_fund_list / fetch_index_holdings / 基础属性"""

    def test_fetch_fund_list_still_raises(self):
        """fetch_fund_list 仍然抛 NotImplementedError"""
        source = DanjuanSource()
        with pytest.raises(NotImplementedError):
            source.fetch_fund_list()

    def test_get_source_name_unchanged(self):
        """get_source_name 返回 'danjuan'"""
        source = DanjuanSource()
        assert source.get_source_name() == "danjuan"

    def test_get_login_type_unchanged(self):
        """get_login_type 返回 'none'"""
        source = DanjuanSource()
        assert source.get_login_type() == "none"
