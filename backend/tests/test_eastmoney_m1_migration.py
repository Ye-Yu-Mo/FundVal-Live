"""
测试 EastMoneySource M1 净值方法迁移 Mobile API

M1 目标：fetch_nav_history / fetch_realtime_nav 直接调用 Mobile API，
不再经过已失效的 Web API（pingzhongdata / fundgz JSONP）。

这些测试在 RED 阶段会 FAIL，因为当前代码仍然先走 Web API 路径。
"""

import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import patch, MagicMock, call

from api.sources.eastmoney import EastMoneySource

MOBILE_NAV_HISTORY_URL = (
    "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList"
)
MOBILE_REALTIME_NAV_URL = (
    "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo"
)
WEB_PINGZHONGDATA_URL = "http://fund.eastmoney.com/pingzhongdata/"
WEB_FUNDGZ_URL = "http://fundgz.1234567.com.cn/js/"


def _make_mobile_nav_response(items):
    """构造 FundMNHisNetList 的 mock 响应"""
    mock = MagicMock()
    mock.json.return_value = {"Datas": items}
    mock.raise_for_status = MagicMock()
    return mock


def _make_mobile_realtime_response(items):
    """构造 FundMNFInfo 的 mock 响应"""
    mock = MagicMock()
    mock.json.return_value = {"Datas": items}
    mock.raise_for_status = MagicMock()
    return mock


# ================================================================
# fetch_nav_history — 直接调 Mobile API
# ================================================================

@pytest.mark.django_db
class TestFetchNavHistoryUsesMobileAPI:
    """fetch_nav_history() 应直接调用 Mobile API，不再先尝试 Web API"""

    def test_calls_mobile_api_directly(self):
        """验证 fetch_nav_history 直接请求 Mobile API，不请求 Web API"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response([
                {"FSRQ": "2026-06-17", "DWJZ": "1.4070", "LJJZ": "3.6083", "JZZZL": "3.61"},
                {"FSRQ": "2026-06-16", "DWJZ": "1.3580", "LJJZ": "3.5593", "JZZZL": "-1.20"},
            ])

            result = source.fetch_nav_history("000001")

            # 结果正确
            assert len(result) == 2
            assert result[0]["unit_nav"] == Decimal("1.4070")
            assert result[0]["nav_date"] == date(2026, 6, 17)

            # 验证调了 Mobile API
            called_urls = [str(c) for c in mock_get.call_args_list]
            assert any("FundMNHisNetList" in u for u in called_urls), (
                f"应该调了 Mobile API, 实际调用: {called_urls}"
            )
            # 验证 NOT 调 Web API
            assert not any("pingzhongdata" in u for u in called_urls), (
                f"不应该调 Web pingzhongdata API, 实际调用: {called_urls}"
            )

    def test_returns_correct_format_from_mobile(self):
        """Mobile API 返回的数据格式与标准格式一致"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response([
                {"FSRQ": "2026-07-28", "DWJZ": "2.3456", "LJJZ": "5.6789", "JZZZL": "1.23"},
            ])

            result = source.fetch_nav_history("000001")

            assert len(result) == 1
            item = result[0]
            # 验证所有标准字段存在且类型正确
            assert item["nav_date"] == date(2026, 7, 28)
            assert item["unit_nav"] == Decimal("2.3456")
            assert item["accumulated_nav"] == Decimal("5.6789")
            assert item["daily_growth"] == Decimal("1.23")

    def test_with_date_range(self):
        """日期范围过滤正常工作"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response([
                {"FSRQ": "2026-06-17", "DWJZ": "1.4070", "LJJZ": "3.6083", "JZZZL": "3.61"},
                {"FSRQ": "2026-06-16", "DWJZ": "1.3580", "LJJZ": "3.5593", "JZZZL": "-1.20"},
                {"FSRQ": "2026-06-15", "DWJZ": "1.3745", "LJJZ": "3.5758", "JZZZL": "0.05"},
            ])

            result = source.fetch_nav_history(
                "000001", start_date=date(2026, 6, 15), end_date=date(2026, 6, 16)
            )

            assert len(result) == 2
            assert result[0]["nav_date"] == date(2026, 6, 16)
            assert result[1]["nav_date"] == date(2026, 6, 15)

    def test_empty_data_returns_empty_list(self):
        """Mobile API 返回空数据 → 返回 []"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response([])

            result = source.fetch_nav_history("000001")

            assert result == []

    def test_network_error_returns_empty_list(self):
        """Mobile API 网络错误 → 返回 [] 不抛异常"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = source.fetch_nav_history("000001")

            assert result == []


# ================================================================
# fetch_realtime_nav — 直接调 Mobile API
# ================================================================

@pytest.mark.django_db
class TestFetchRealtimeNavUsesMobileAPI:
    """fetch_realtime_nav() 应直接调用 Mobile API，不再先尝试 Web API (fundgz)"""

    def test_calls_mobile_api_directly(self):
        """验证 fetch_realtime_nav 直接请求 Mobile API，不请求 fundgz"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_realtime_response([
                {
                    "FCODE": "000001",
                    "SHORTNAME": "华夏成长混合",
                    "ACCNAV": "1.4070",
                    "PDATE": "2026-06-17",
                }
            ])

            result = source.fetch_realtime_nav("000001")

            assert result is not None
            assert result["fund_code"] == "000001"
            assert result["nav"] == Decimal("1.4070")
            assert result["nav_date"] == date(2026, 6, 17)

            # 验证调了 Mobile API
            called_urls = [str(c) for c in mock_get.call_args_list]
            assert any("FundMNFInfo" in u for u in called_urls), (
                f"应该调了 Mobile API (FundMNFInfo), 实际调用: {called_urls}"
            )
            # 验证 NOT 调 fundgz Web API
            assert not any("fundgz" in u for u in called_urls), (
                f"不应该调 fundgz Web API, 实际调用: {called_urls}"
            )

    def test_returns_correct_format(self):
        """返回格式 {'fund_code', 'nav', 'nav_date'} 正确"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_realtime_response([
                {
                    "FCODE": "000001",
                    "ACCNAV": "2.3456",
                    "PDATE": "2026-07-28",
                }
            ])

            result = source.fetch_realtime_nav("000001")

            assert isinstance(result, dict)
            assert set(result.keys()) == {"fund_code", "nav", "nav_date"}
            assert result["fund_code"] == "000001"
            assert result["nav"] == Decimal("2.3456")
            assert result["nav_date"] == date(2026, 7, 28)

    def test_empty_data_returns_none(self):
        """Mobile API 返回空数据 → 返回 None"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_realtime_response([])

            result = source.fetch_realtime_nav("000001")

            assert result is None

    def test_missing_accnav_returns_none(self):
        """ACCNAV 缺失 → 返回 None"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_realtime_response([
                {"FCODE": "000001", "PDATE": "2026-07-28"}
            ])

            result = source.fetch_realtime_nav("000001")

            assert result is None

    def test_network_error_returns_none(self):
        """网络错误 → 返回 None 不抛异常"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = source.fetch_realtime_nav("000001")

            assert result is None


# ================================================================
# fetch_today_nav — 无需改动，自动受益
# ================================================================

@pytest.mark.django_db
class TestFetchTodayNavUnchanged:
    """
    fetch_today_nav() 不改代码，但通过 fetch_nav_history() 迁移到 Mobile API
    自动获得更好的覆盖率。

    这些测试验证它在新路径下的行为。
    """

    def test_returns_latest_nav_from_mobile_data(self):
        """从 Mobile API 数据中正确地取最新净值"""
        from datetime import date as date_type

        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response([
                {"FSRQ": "2026-06-15", "DWJZ": "1.3745", "LJJZ": "3.5758", "JZZZL": "0.05"},
                {"FSRQ": "2026-06-16", "DWJZ": "1.3580", "LJJZ": "3.5593", "JZZZL": "-1.20"},
                {"FSRQ": "2026-06-17", "DWJZ": "1.4070", "LJJZ": "3.6083", "JZZZL": "3.61"},
            ])

            result = source.fetch_today_nav("000001")

            assert result is not None
            assert result["fund_code"] == "000001"
            # 取最后一条（最新日期）
            assert result["nav"] == Decimal("1.4070")
            assert result["nav_date"] == date_type(2026, 6, 17)

    def test_returns_none_when_no_data(self):
        """无历史净值数据 → 返回 None"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response([])

            result = source.fetch_today_nav("000001")

            assert result is None


# ================================================================
# DEPRECATED 注释验证
# ================================================================

@pytest.mark.django_db
class TestDeprecatedComments:
    """Web API URL 常量上方应有 DEPRECATED 注释"""

    def test_estimate_url_has_deprecated_comment(self):
        """ESTIMATE_URL 行前应有 DEPRECATED 注释"""
        import inspect
        source_code, _ = inspect.getsourcelines(EastMoneySource)
        source_text = "".join(source_code)

        # ESTIMATE_URL 定义行上方应有 DEPRECATED 注释
        assert "ESTIMATE_URL" in source_text, "ESTIMATE_URL 常量必须存在（保留以备恢复）"

        # 找到 ESTIMATE_URL 常量定义所在行号
        estimate_url_line = None
        for i, line in enumerate(source_code):
            if "ESTIMATE_URL" in line and "=" in line and "fundgz" in line:
                estimate_url_line = i
                break

        assert estimate_url_line is not None, "找不到 ESTIMATE_URL 常量定义行"

        # 检查上方 1-3 行是否有 DEPRECATED 注释
        surrounding = "".join(
            source_code[max(0, estimate_url_line - 3): estimate_url_line]
        )
        assert "DEPRECATED" in surrounding.upper(), (
            f"ESTIMATE_URL 上方应有 DEPRECATED 注释，实际内容:\n{surrounding}"
        )

    def test_fund_list_url_has_deprecated_comment(self):
        """FUND_LIST_URL 行前应有 DEPRECATED 注释"""
        import inspect
        source_code, _ = inspect.getsourcelines(EastMoneySource)

        fund_list_url_line = None
        for i, line in enumerate(source_code):
            if "FUND_LIST_URL" in line and "=" in line and "fundcode_search" in line:
                fund_list_url_line = i
                break

        assert fund_list_url_line is not None, "找不到 FUND_LIST_URL 常量定义行"

        surrounding = "".join(
            source_code[max(0, fund_list_url_line - 3): fund_list_url_line]
        )
        assert "DEPRECATED" in surrounding.upper(), (
            f"FUND_LIST_URL 上方应有 DEPRECATED 注释，实际内容:\n{surrounding}"
        )

    def test_history_url_has_deprecated_comment(self):
        """HISTORY_URL 行前应有 DEPRECATED 注释"""
        import inspect
        source_code, _ = inspect.getsourcelines(EastMoneySource)

        history_url_line = None
        for i, line in enumerate(source_code):
            if "HISTORY_URL" in line and "=" in line and "pingzhongdata" in line:
                history_url_line = i
                break

        assert history_url_line is not None, "找不到 HISTORY_URL 常量定义行"

        surrounding = "".join(
            source_code[max(0, history_url_line - 3): history_url_line]
        )
        assert "DEPRECATED" in surrounding.upper(), (
            f"HISTORY_URL 上方应有 DEPRECATED 注释，实际内容:\n{surrounding}"
        )
