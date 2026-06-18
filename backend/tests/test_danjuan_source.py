"""
测试 DanjuanSource（雪球基金 / 蛋卷基金数据源）

测试点：
1. fetch_nav_history - 成功/日期范围/空数据/网络错误/result_code异常/特殊percentage
2. fetch_realtime_nav - 成功/无数据
3. fetch_today_nav - 日期匹配/日期不匹配
4. fetch_estimate - 返回 None
5. fetch_fund_detail - 成功/网络错误/result_code异常
6. fetch_fund_list - NotImplementedError
7. get_source_name / get_login_type
8. SourceRegistry 集成
"""

import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────
# 辅助函数：构造蛋卷 API mock 响应
# ─────────────────────────────────────────────

NAV_HISTORY_URL = "https://danjuanfunds.com/djapi/fund/nav/history/{code}"
FUND_DETAIL_URL = "https://danjuanfunds.com/djapi/fund/{code}"


def _make_response(json_data, status_code=200):
    """构造通用的 requests.Response mock"""
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    return mock


def _nav_history_response(items):
    """构造蛋卷历史净值 API 响应"""
    return _make_response({
        "data": {
            "items": items,
            "current_page": 1,
            "size": 200,
            "total_items": len(items),
            "total_pages": 1,
        },
        "result_code": 0,
    })


def _fund_detail_response(fd_code="000001", fd_name="华夏成长混合", **overrides):
    """构造蛋卷基金详情 API 响应"""
    data = {
        "fd_code": fd_code,
        "fd_name": fd_name,
        "fd_type": "3",
        "found_date": "2001-12-18",
        "keeper_name": "华夏基金管理有限公司",
        "manager_name": "刘睿聪 郑晓辉",
        "risk_level": "4",
        "fund_derived": {
            "end_date": "2026-06-17",
            "unit_nav": "1.4070",
            "nav_grtd": "3.6083",
            "nav_grl1m": "12.92",
            "nav_grl3m": "32.36",
            "nav_grl6m": "33.87",
            "nav_grl1y": "72.32",
            "nav_grl3y": "55.52",
            "nav_grl5y": "5.58",
            "srank_l1m": "995/5347",
            "srank_l3m": "1129/5227",
            "srank_l6m": "1312/5013",
            "srank_l1y": "1263/4588",
            "srank_l3y": "1068/3594",
            "srank_l5y": "940/1917",
        },
    }
    data.update(overrides)
    return _make_response({"data": data, "result_code": 0})


# ─────────────────────────────────────────────
# fetch_nav_history 测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestDanjuanNavHistory:
    """DanjuanSource.fetch_nav_history 测试"""

    def test_success(self):
        """历史净值获取成功"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _nav_history_response([
                {"date": "2026-06-17", "nav": "1.4070", "percentage": "3.61", "value": "1.4070"},
                {"date": "2026-06-16", "nav": "1.3580", "percentage": "-1.20", "value": "1.3580"},
                {"date": "2026-06-15", "nav": "1.3745", "percentage": "0.05", "value": "1.3745"},
            ])

            result = source.fetch_nav_history("000001")

            assert len(result) == 3
            assert result[0]["nav_date"] == date(2026, 6, 17)
            assert result[0]["unit_nav"] == Decimal("1.4070")
            assert result[0]["daily_growth"] == Decimal("3.61")
            assert result[0]["accumulated_nav"] is None  # 蛋卷不返回累计净值
            assert result[1]["unit_nav"] == Decimal("1.3580")
            assert result[1]["daily_growth"] == Decimal("-1.20")
            assert result[2]["unit_nav"] == Decimal("1.3745")
            assert result[2]["daily_growth"] == Decimal("0.05")

    def test_with_date_range(self):
        """带日期范围过滤"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _nav_history_response([
                {"date": "2026-06-17", "nav": "1.4070", "percentage": "3.61", "value": "1.4070"},
                {"date": "2026-06-16", "nav": "1.3580", "percentage": "-1.20", "value": "1.3580"},
                {"date": "2026-06-15", "nav": "1.3745", "percentage": "0.05", "value": "1.3745"},
                {"date": "2026-06-14", "nav": "1.3738", "percentage": "0.00", "value": "1.3738"},
            ])

            result = source.fetch_nav_history(
                "000001", start_date=date(2026, 6, 15), end_date=date(2026, 6, 16)
            )

            assert len(result) == 2
            assert result[0]["nav_date"] == date(2026, 6, 16)
            assert result[1]["nav_date"] == date(2026, 6, 15)

    def test_empty_items(self):
        """API 返回空 items"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _nav_history_response([])

            result = source.fetch_nav_history("000001")

            assert result == []

    def test_network_error(self):
        """网络错误 → 返回空列表"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = source.fetch_nav_history("000001")

            assert result == []

    def test_result_code_not_zero(self):
        """result_code != 0 → 返回空列表"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_response({
                "data": None,
                "result_code": 600001,
                "message": "该基金暂不销售",
            })

            result = source.fetch_nav_history("000001")

            assert result == []

    def test_percentage_dash(self):
        """percentage 为 '--' → daily_growth 为 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _nav_history_response([
                {"date": "2015-05-27", "nav": "1.0000", "percentage": "--", "value": "1.0000"},
            ])

            result = source.fetch_nav_history("000001")

            assert len(result) == 1
            assert result[0]["unit_nav"] == Decimal("1.0000")
            assert result[0]["daily_growth"] is None

    def test_percentage_zero(self):
        """percentage 为 '0.00' → Decimal('0.00')"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _nav_history_response([
                {"date": "2026-06-14", "nav": "1.3738", "percentage": "0.00", "value": "1.3738"},
            ])

            result = source.fetch_nav_history("000001")

            assert result[0]["daily_growth"] == Decimal("0.00")

    def test_invalid_json(self):
        """JSON 解析失败 → 返回空列表"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.json.side_effect = ValueError("Invalid JSON")
            mock.raise_for_status = MagicMock()
            mock_get.return_value = mock

            result = source.fetch_nav_history("000001")

            assert result == []

    def test_none_response_data(self):
        """响应中 data 为 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_response({
                "data": None,
                "result_code": 0,
            })

            result = source.fetch_nav_history("000001")

            assert result == []

    def test_decimal_precision(self):
        """Decimal 精度保持"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _nav_history_response([
                {"date": "2026-06-17", "nav": "1.23456789", "percentage": "3.61456789", "value": "1.23456789"},
            ])

            result = source.fetch_nav_history("000001")

            assert result[0]["unit_nav"] == Decimal("1.23456789")
            assert result[0]["daily_growth"] == Decimal("3.61456789")


# ─────────────────────────────────────────────
# fetch_realtime_nav 测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestDanjuanRealtimeNav:
    """DanjuanSource.fetch_realtime_nav 测试"""

    def test_success(self):
        """取最新一条净值"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _nav_history_response([
                {"date": "2026-06-17", "nav": "1.4070", "percentage": "3.61", "value": "1.4070"},
                {"date": "2026-06-16", "nav": "1.3580", "percentage": "-1.20", "value": "1.3580"},
            ])

            result = source.fetch_realtime_nav("000001")

            assert result is not None
            assert result["fund_code"] == "000001"
            assert result["nav"] == Decimal("1.4070")
            assert result["nav_date"] == date(2026, 6, 17)

    def test_empty_data(self):
        """无数据 → 返回 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _nav_history_response([])

            result = source.fetch_realtime_nav("000001")

            assert result is None

    def test_network_error(self):
        """网络错误 → 返回 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = source.fetch_realtime_nav("000001")

            assert result is None


# ─────────────────────────────────────────────
# fetch_today_nav 测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestDanjuanTodayNav:
    """DanjuanSource.fetch_today_nav 测试"""

    def test_date_matches_today(self):
        """最新净值日期等于今天 → 返回数据"""
        from api.sources.danjuan import DanjuanSource
        from datetime import date as date_type

        today = date_type.today()

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _nav_history_response([
                {"date": today.isoformat(), "nav": "1.4070", "percentage": "0.32", "value": "1.4070"},
                {"date": "2026-06-16", "nav": "1.3580", "percentage": "-1.20", "value": "1.3580"},
            ])

            result = source.fetch_today_nav("000001")

            assert result is not None
            assert result["fund_code"] == "000001"
            assert result["nav"] == Decimal("1.4070")
            assert result["nav_date"] == today

    def test_date_not_today(self):
        """最新净值日期不是今天 → 返回 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _nav_history_response([
                {"date": "2026-06-17", "nav": "1.4070", "percentage": "0.32", "value": "1.4070"},
            ])

            result = source.fetch_today_nav("000001")

            assert result is None

    def test_empty_data(self):
        """无数据 → 返回 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _nav_history_response([])

            result = source.fetch_today_nav("000001")

            assert result is None


# ─────────────────────────────────────────────
# fetch_estimate 测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestDanjuanEstimate:
    """DanjuanSource.fetch_estimate 测试"""

    def test_returns_none(self):
        """蛋卷不支持实时估值，始终返回 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        result = source.fetch_estimate("000001")

        assert result is None


# ─────────────────────────────────────────────
# fetch_fund_detail 测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestDanjuanFundDetail:
    """DanjuanSource.fetch_fund_detail 测试"""

    def test_success(self):
        """获取基金详情成功，含评级排名"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _fund_detail_response()

            result = source.fetch_fund_detail("000001")

            assert result is not None
            assert result["fund_code"] == "000001"
            assert result["fund_name"] == "华夏成长混合"
            assert result["risk_level"] == "4"
            assert result["manager_name"] == "刘睿聪 郑晓辉"
            assert result["latest_nav"] == Decimal("1.4070")
            assert result["nav_date"] == date(2026, 6, 17)

            # 阶段收益
            assert result["period_returns"]["1m"] == Decimal("12.92")
            assert result["period_returns"]["1y"] == Decimal("72.32")

            # 同类排名
            assert result["peer_ranking"]["1m"] == "995/5347"
            assert result["peer_ranking"]["1y"] == "1263/4588"

    def test_network_error(self):
        """网络错误 → 返回 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = source.fetch_fund_detail("000001")

            assert result is None

    def test_result_code_not_zero(self):
        """result_code != 0 → 返回 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_response({
                "data": None,
                "result_code": 600001,
                "message": "该基金暂不销售",
            })

            result = source.fetch_fund_detail("000001")

            assert result is None

    def test_no_fund_derived(self):
        """无 fund_derived 字段 → peer_ranking 和 period_returns 为空 dict"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _fund_detail_response(fund_derived=None)

            result = source.fetch_fund_detail("000001")

            assert result is not None
            assert result["period_returns"] == {}
            assert result["peer_ranking"] == {}

    def test_missing_optional_fields(self):
        """可选字段缺失 → 对应值为 None"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_response({
                "data": {
                    "fd_code": "000001",
                    "fd_name": "华夏成长混合",
                },
                "result_code": 0,
            })

            result = source.fetch_fund_detail("000001")

            assert result is not None
            assert result["fund_code"] == "000001"
            assert result["fund_name"] == "华夏成长混合"
            assert result["risk_level"] is None
            assert result["manager_name"] is None
            assert result["latest_nav"] is None
            assert result["nav_date"] is None
            assert result["period_returns"] == {}
            assert result["peer_ranking"] == {}


# ─────────────────────────────────────────────
# 其他抽象方法测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestDanjuanOtherMethods:
    """DanjuanSource 的其他抽象方法测试"""

    def test_get_source_name(self):
        """返回 'danjuan'"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        assert source.get_source_name() == "danjuan"

    def test_get_login_type(self):
        """返回 'none'（无需登录）"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        assert source.get_login_type() == "none"

    def test_fetch_fund_list_raises(self):
        """fetch_fund_list 抛 NotImplementedError"""
        from api.sources.danjuan import DanjuanSource

        source = DanjuanSource()
        with pytest.raises(NotImplementedError):
            source.fetch_fund_list()


# ─────────────────────────────────────────────
# SourceRegistry 集成测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestDanjuanRegistry:
    """DanjuanSource 的 SourceRegistry 集成"""

    def test_registry_has_danjuan(self):
        """导入 api.sources 后，SourceRegistry 包含 danjuan"""
        # 强制重新导入以触发注册（若未注册则此测试失败）
        from api.sources import SourceRegistry

        sources = SourceRegistry.list_sources()
        assert "danjuan" in sources, (
            f"SourceRegistry 中缺少 'danjuan'，当前源: {sources}"
        )

    def test_registry_get_danjuan(self):
        """SourceRegistry.get_source('danjuan') 返回 DanjuanSource 实例"""
        from api.sources import SourceRegistry
        from api.sources.danjuan import DanjuanSource

        source = SourceRegistry.get_source("danjuan")
        assert source is not None
        assert isinstance(source, DanjuanSource)
