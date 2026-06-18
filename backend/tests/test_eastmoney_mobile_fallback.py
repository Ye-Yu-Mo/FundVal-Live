"""
测试 EastMoneySource 移动端 API Fallback

测试点：
1. _fetch_nav_history_mobile - 成功/日期范围/空数据/网络错误
2. _fetch_realtime_nav_mobile - 成功/空数据/网络错误
3. fetch_nav_history fallback - Web API 空时走 mobile
4. fetch_nav_history no fallback - Web API 成功时不走 mobile
5. fetch_realtime_nav fallback - Web API None 时走 mobile
6. fetch_realtime_nav no fallback - Web API 成功时不走 mobile
"""

import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import patch, MagicMock, call

from api.sources.eastmoney import EastMoneySource


# ─────────────────────────────────────────────
# 辅助函数：构造 mobile API mock 响应
# ─────────────────────────────────────────────

MOBILE_NAV_HISTORY_URL = (
    "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList"
)
MOBILE_REALTIME_NAV_URL = (
    "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo"
)

PINGZHONGDATA_URL = "http://fund.eastmoney.com/pingzhongdata/{code}.js"
FUNDGZ_URL = "http://fundgz.1234567.com.cn/js/{code}.js"


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


def _make_web_nav_response(text):
    """构造 pingzhongdata 的 mock 响应"""
    mock = MagicMock()
    mock.text = text
    mock.raise_for_status = MagicMock()
    return mock


def _make_web_estimate_response(text):
    """构造 fundgz 的 mock 响应"""
    mock = MagicMock()
    mock.text = text
    mock.raise_for_status = MagicMock()
    return mock


# ─────────────────────────────────────────────
# _fetch_nav_history_mobile 单元测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestFetchNavHistoryMobile:
    """_fetch_nav_history_mobile 方法测试"""

    def test_success(self):
        """移动端历史净值获取成功"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response(
                [
                    {"FSRQ": "2026-06-17", "DWJZ": "1.4070", "LJJZ": "3.6083", "JZZZL": "3.61"},
                    {"FSRQ": "2026-06-16", "DWJZ": "1.3580", "LJJZ": "3.5593", "JZZZL": "-1.20"},
                    {"FSRQ": "2026-06-15", "DWJZ": "1.3745", "LJJZ": "3.5758", "JZZZL": "0.05"},
                ]
            )

            result = source._fetch_nav_history_mobile("000001")

            assert len(result) == 3
            assert result[0]["nav_date"] == date(2026, 6, 17)
            assert result[0]["unit_nav"] == Decimal("1.4070")
            assert result[0]["accumulated_nav"] == Decimal("3.6083")
            assert result[0]["daily_growth"] == Decimal("3.61")
            assert result[1]["nav_date"] == date(2026, 6, 16)
            assert result[1]["unit_nav"] == Decimal("1.3580")
            assert result[2]["nav_date"] == date(2026, 6, 15)

    def test_with_date_range(self):
        """移动端历史净值 - 日期范围过滤"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response(
                [
                    {"FSRQ": "2026-06-17", "DWJZ": "1.4070", "LJJZ": "3.6083", "JZZZL": "3.61"},
                    {"FSRQ": "2026-06-16", "DWJZ": "1.3580", "LJJZ": "3.5593", "JZZZL": "-1.20"},
                    {"FSRQ": "2026-06-15", "DWJZ": "1.3745", "LJJZ": "3.5758", "JZZZL": "0.05"},
                    {"FSRQ": "2026-06-14", "DWJZ": "1.3738", "LJJZ": "3.5751", "JZZZL": "0.00"},
                ]
            )

            result = source._fetch_nav_history_mobile(
                "000001", start_date=date(2026, 6, 15), end_date=date(2026, 6, 16)
            )

            assert len(result) == 2
            assert result[0]["nav_date"] == date(2026, 6, 16)
            assert result[1]["nav_date"] == date(2026, 6, 15)

    def test_empty_data(self):
        """移动端历史净值 - 空数据"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response([])

            result = source._fetch_nav_history_mobile("000001")

            assert result == []

    def test_network_error(self):
        """移动端历史净值 - 网络错误"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = source._fetch_nav_history_mobile("000001")

            # 不抛异常，返回空列表
            assert result == []

    def test_invalid_json(self):
        """移动端历史净值 - JSON 解析失败"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.json.side_effect = ValueError("Invalid JSON")
            mock.raise_for_status = MagicMock()
            mock_get.return_value = mock

            result = source._fetch_nav_history_mobile("000001")

            assert result == []

    def test_none_response(self):
        """移动端历史净值 - json() 返回 None"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.json.return_value = None
            mock.raise_for_status = MagicMock()
            mock_get.return_value = mock

            result = source._fetch_nav_history_mobile("000001")

            assert result == []

    def test_missing_fields(self):
        """移动端历史净值 - 缺少必需字段的记录被跳过"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response(
                [
                    {"FSRQ": "2026-06-17", "DWJZ": "1.4070", "LJJZ": "3.6083", "JZZZL": "3.61"},
                    {"FSRQ": "2026-06-16"},  # 缺少 DWJZ，应跳过
                    {"DWJZ": "1.3580", "LJJZ": "3.5593", "JZZZL": "-1.20"},  # 缺少 FSRQ，应跳过
                ]
            )

            result = source._fetch_nav_history_mobile("000001")

            # 只有第一条完整数据
            assert len(result) == 1
            assert result[0]["unit_nav"] == Decimal("1.4070")

    def test_decimal_precision(self):
        """移动端历史净值 - Decimal 精度"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response(
                [
                    {"FSRQ": "2026-06-17", "DWJZ": "1.23456789", "LJJZ": "3.60831234", "JZZZL": "3.61456789"},
                ]
            )

            result = source._fetch_nav_history_mobile("000001")

            assert result[0]["unit_nav"] == Decimal("1.23456789")
            assert result[0]["accumulated_nav"] == Decimal("3.60831234")
            assert result[0]["daily_growth"] == Decimal("3.61456789")


# ─────────────────────────────────────────────
# _fetch_realtime_nav_mobile 单元测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestFetchRealtimeNavMobile:
    """_fetch_realtime_nav_mobile 方法测试"""

    def test_success(self):
        """移动端实时净值获取成功"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_realtime_response(
                [
                    {
                        "FCODE": "000001",
                        "SHORTNAME": "华夏成长混合",
                        "ACCNAV": "1.4070",
                        "PDATE": "2026-06-17",
                        "GZTIME": "2026-06-18 14:30:00",
                        "GSZZL": "0.32",
                    }
                ]
            )

            result = source._fetch_realtime_nav_mobile("000001")

            assert result is not None
            assert result["fund_code"] == "000001"
            assert result["nav"] == Decimal("1.4070")
            assert result["nav_date"] == date(2026, 6, 17)

    def test_empty_data(self):
        """移动端实时净值 - 空数据"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_realtime_response([])

            result = source._fetch_realtime_nav_mobile("000001")

            assert result is None

    def test_network_error(self):
        """移动端实时净值 - 网络错误"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = source._fetch_realtime_nav_mobile("000001")

            assert result is None

    def test_missing_nav(self):
        """移动端实时净值 - ACCNAV 为空"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_realtime_response(
                [
                    {
                        "FCODE": "000001",
                        "PDATE": "2026-06-17",
                    }
                ]
            )

            result = source._fetch_realtime_nav_mobile("000001")

            assert result is None

    def test_invalid_json(self):
        """移动端实时净值 - JSON 解析失败"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.json.side_effect = ValueError("Invalid JSON")
            mock.raise_for_status = MagicMock()
            mock_get.return_value = mock

            result = source._fetch_realtime_nav_mobile("000001")

            assert result is None


# ─────────────────────────────────────────────
# fetch_nav_history fallback 测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestFetchNavHistoryFallback:
    """fetch_nav_history 的 Web → Mobile fallback 逻辑"""

    def test_web_success_no_mobile_call(self):
        """Web API 成功时，不调用 mobile API"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            # Web API 返回数据
            mock_get.return_value = _make_web_nav_response("""
            var Data_netWorthTrend = [
                {"x":1748659200000,"y":1.2345,"equityReturn":0.9,"unitMoney":""}
            ];
            var Data_ACWorthTrend = [];
            """)

            result = source.fetch_nav_history("000001")

            # 结果正确
            assert len(result) == 1
            assert result[0]["unit_nav"] == Decimal("1.2345")

            # 验证只调了 pingzhongdata URL，没调 mobile URL
            called_urls = [c[0][0] for c in mock_get.call_args_list]
            assert any("pingzhongdata" in url for url in called_urls)
            assert not any("FundMNHisNetList" in url for url in called_urls)

    def test_web_empty_fallback_to_mobile(self):
        """Web API 返回空数据时，fallback 到 mobile API"""
        source = EastMoneySource()

        def url_based_response(url, *args, **kwargs):
            """根据请求 URL 返回不同响应"""
            if "pingzhongdata" in url:
                # Web API 返回空
                return _make_web_nav_response("""
                var Data_netWorthTrend = [];
                var Data_ACWorthTrend = [];
                """)
            elif "FundMNHisNetList" in url:
                # Mobile API 返回数据
                return _make_mobile_nav_response(
                    [
                        {"FSRQ": "2026-06-17", "DWJZ": "1.4070", "LJJZ": "3.6083", "JZZZL": "3.61"},
                        {"FSRQ": "2026-06-16", "DWJZ": "1.3580", "LJJZ": "3.5593", "JZZZL": "-1.20"},
                    ]
                )
            return MagicMock()

        with patch("requests.get", side_effect=url_based_response) as mock_get:
            result = source.fetch_nav_history("000001")

            # 应该拿到 mobile API 的数据
            assert len(result) == 2
            assert result[0]["unit_nav"] == Decimal("1.4070")
            assert result[0]["nav_date"] == date(2026, 6, 17)

    def test_both_empty_returns_empty(self):
        """Web 和 Mobile API 都返回空数据"""
        source = EastMoneySource()

        def url_based_response(url, *args, **kwargs):
            if "pingzhongdata" in url:
                return _make_web_nav_response("""
                var Data_netWorthTrend = [];
                var Data_ACWorthTrend = [];
                """)
            elif "FundMNHisNetList" in url:
                return _make_mobile_nav_response([])
            return MagicMock()

        with patch("requests.get", side_effect=url_based_response):
            result = source.fetch_nav_history("000001")

            assert result == []

    def test_web_error_fallback_to_mobile(self):
        """Web API 抛异常时，fallback 到 mobile API"""
        source = EastMoneySource()

        def url_based_response(url, *args, **kwargs):
            if "pingzhongdata" in url:
                raise Exception("Web API error")
            elif "FundMNHisNetList" in url:
                return _make_mobile_nav_response(
                    [
                        {"FSRQ": "2026-06-17", "DWJZ": "1.4070", "LJJZ": "3.6083", "JZZZL": "3.61"},
                    ]
                )
            return MagicMock()

        with patch("requests.get", side_effect=url_based_response):
            result = source.fetch_nav_history("000001")

            assert len(result) == 1
            assert result[0]["unit_nav"] == Decimal("1.4070")


# ─────────────────────────────────────────────
# fetch_realtime_nav fallback 测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestFetchRealtimeNavFallback:
    """fetch_realtime_nav 的 Web → Mobile fallback 逻辑"""

    def test_web_success_no_mobile_call(self):
        """Web API 成功时，不调用 mobile API"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_web_estimate_response(
                'jsonpgz({"fundcode":"000001","name":"华夏成长","jzrq":"2026-06-17","dwjz":"1.4070","gsz":"1.4100","gszzl":"0.21","gztime":"2026-06-18 14:30:00"});'
            )

            result = source.fetch_realtime_nav("000001")

            assert result is not None
            assert result["nav"] == Decimal("1.4070")

            # 验证没调 mobile URL
            called_urls = [str(c) for c in mock_get.call_args_list]
            assert not any("FundMNFInfo" in u for u in called_urls)

    def test_web_none_fallback_to_mobile(self):
        """Web API 返回 None 时（缺少字段），fallback 到 mobile API"""
        source = EastMoneySource()

        def url_based_response(url, *args, **kwargs):
            if "fundgz" in url:
                # 缺少 dwjz/jzrq 字段，fetch_realtime_nav 返回 None
                return _make_web_estimate_response(
                    'jsonpgz({"fundcode":"000001","name":"华夏成长","gsz":"1.4100","gszzl":"0.21","gztime":"2026-06-18 14:30:00"});'
                )
            elif "FundMNFInfo" in url:
                return _make_mobile_realtime_response(
                    [
                        {
                            "FCODE": "000001",
                            "ACCNAV": "1.4070",
                            "PDATE": "2026-06-17",
                        }
                    ]
                )
            return MagicMock()

        with patch("requests.get", side_effect=url_based_response):
            result = source.fetch_realtime_nav("000001")

            assert result is not None
            assert result["nav"] == Decimal("1.4070")
            assert result["nav_date"] == date(2026, 6, 17)

    def test_both_fail_returns_none(self):
        """Web 和 Mobile 都失败时返回 None"""
        source = EastMoneySource()

        def url_based_response(url, *args, **kwargs):
            if "fundgz" in url:
                raise Exception("Web API error")
            elif "FundMNFInfo" in url:
                return _make_mobile_realtime_response([])
            return MagicMock()

        with patch("requests.get", side_effect=url_based_response):
            result = source.fetch_realtime_nav("000001")

            assert result is None


# ─────────────────────────────────────────────
# fetch_today_nav 间接受益测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestFetchTodayNavFallback:
    """fetch_today_nav 通过 fetch_nav_history 的 fallback 间接受益"""

    def test_today_nav_via_mobile_fallback(self):
        """Web API 空 → mobile API 有数据 → fetch_today_nav 返回最新净值"""
        from datetime import date as date_type

        source = EastMoneySource()

        def url_based_response(url, *args, **kwargs):
            if "pingzhongdata" in url:
                return _make_web_nav_response("""
                var Data_netWorthTrend = [];
                var Data_ACWorthTrend = [];
                """)
            elif "FundMNHisNetList" in url:
                return _make_mobile_nav_response(
                    [
                        {"FSRQ": "2026-06-15", "DWJZ": "1.3745", "LJJZ": "3.5758", "JZZZL": "0.05"},
                        {"FSRQ": "2026-06-16", "DWJZ": "1.3580", "LJJZ": "3.5593", "JZZZL": "-1.20"},
                        {"FSRQ": "2026-06-17", "DWJZ": "1.4070", "LJJZ": "3.6083", "JZZZL": "3.61"},
                    ]
                )
            return MagicMock()

        with patch("requests.get", side_effect=url_based_response):
            result = source.fetch_today_nav("000001")

            assert result is not None
            assert result["fund_code"] == "000001"
            assert result["nav"] == Decimal("1.4070")
            assert result["nav_date"] == date_type(2026, 6, 17)

    def test_today_nav_both_empty(self):
        """Web 和 Mobile 都空时，fetch_today_nav 返回 None"""
        source = EastMoneySource()

        def url_based_response(url, *args, **kwargs):
            if "pingzhongdata" in url:
                return _make_web_nav_response("""
                var Data_netWorthTrend = [];
                var Data_ACWorthTrend = [];
                """)
            elif "FundMNHisNetList" in url:
                return _make_mobile_nav_response([])
            return MagicMock()

        with patch("requests.get", side_effect=url_based_response):
            result = source.fetch_today_nav("000001")

            assert result is None
