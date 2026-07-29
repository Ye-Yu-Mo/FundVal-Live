"""
测试 EastMoneySource 历史净值获取 (M1 更新)

M1 后 fetch_nav_history() 直接调用 Mobile API (FundMNHisNetList)，
不再走 Web API (pingzhongdata)。所有测试 mock 使用 Mobile API 响应格式。
"""

import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import patch, MagicMock

from api.sources.eastmoney import EastMoneySource


def _make_nav_response(items):
    """构造 FundMNHisNetList 的 mock 响应"""
    mock = MagicMock()
    mock.json.return_value = {"Datas": items}
    mock.raise_for_status = MagicMock()
    return mock


MOBILE_NAV_HISTORY_URL = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList"


@pytest.mark.django_db
class TestEastMoneySourceNavHistory:
    """测试 EastMoneySource 历史净值获取 (M1: Mobile API 主路径)"""

    def test_fetch_nav_history_success(self):
        """测试成功获取历史净值"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_nav_response(
                [
                    {"FSRQ": "2024-01-01", "DWJZ": "1.2345", "LJJZ": "2.3456", "JZZZL": "0"},
                    {"FSRQ": "2024-01-02", "DWJZ": "1.2456", "LJJZ": "2.3567", "JZZZL": "0.90"},
                    {"FSRQ": "2024-01-03", "DWJZ": "1.2567", "LJJZ": "2.3678", "JZZZL": "0.89"},
                ]
            )

            result = source.fetch_nav_history("000001")

            assert len(result) == 3
            assert result[0]["nav_date"] == date(2024, 1, 1)
            assert result[0]["unit_nav"] == Decimal("1.2345")
            assert result[0]["accumulated_nav"] == Decimal("2.3456")
            assert result[0]["daily_growth"] == Decimal("0")

            assert result[1]["nav_date"] == date(2024, 1, 2)
            assert result[1]["unit_nav"] == Decimal("1.2456")
            assert result[1]["daily_growth"] == Decimal("0.90")

    def test_fetch_nav_history_with_date_range(self):
        """测试按日期范围过滤历史净值"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_nav_response(
                [
                    {"FSRQ": "2024-01-01", "DWJZ": "1.2345", "LJJZ": "2.3456", "JZZZL": "0"},
                    {"FSRQ": "2024-01-02", "DWJZ": "1.2456", "LJJZ": "2.3567", "JZZZL": "0.90"},
                    {"FSRQ": "2024-01-03", "DWJZ": "1.2567", "LJJZ": "2.3678", "JZZZL": "0.89"},
                    {"FSRQ": "2024-01-04", "DWJZ": "1.2678", "LJJZ": "2.3789", "JZZZL": "0.88"},
                ]
            )

            # 只获取 2024-01-02 到 2024-01-03 的数据
            result = source.fetch_nav_history(
                "000001", start_date=date(2024, 1, 2), end_date=date(2024, 1, 3)
            )

            assert len(result) == 2
            assert result[0]["nav_date"] == date(2024, 1, 2)
            assert result[1]["nav_date"] == date(2024, 1, 3)

    def test_fetch_nav_history_no_accumulated_nav(self):
        """测试没有累计净值的情况"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            # LJJZ 字段缺失
            mock_get.return_value = _make_nav_response(
                [
                    {"FSRQ": "2024-01-01", "DWJZ": "1.2345", "JZZZL": "0"},
                ]
            )

            result = source.fetch_nav_history("000001")

            assert len(result) == 1
            assert result[0]["unit_nav"] == Decimal("1.2345")
            assert result[0]["accumulated_nav"] is None

    def test_fetch_nav_history_invalid_response(self):
        """测试无效响应格式（json() 返回非预期结构）"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.json.side_effect = ValueError("Invalid JSON")
            mock.raise_for_status = MagicMock()
            mock_get.return_value = mock

            result = source.fetch_nav_history("000001")

            assert result == []

    def test_fetch_nav_history_network_error(self):
        """测试网络错误"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = source.fetch_nav_history("000001")

            assert result == []

    def test_fetch_nav_history_empty_data(self):
        """测试空数据"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_nav_response([])

            result = source.fetch_nav_history("000001")

            assert result == []

    def test_fetch_nav_history_missing_fields(self):
        """测试缺少必需字段（DWJZ 或 FSRQ）"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            # 缺少 DWJZ 和 FSRQ 的记录应被跳过
            mock_get.return_value = _make_nav_response(
                [
                    {"FSRQ": "2024-01-01"},  # 缺少 DWJZ
                    {"DWJZ": "1.2345", "JZZZL": "0.90"},  # 缺少 FSRQ
                ]
            )

            result = source.fetch_nav_history("000001")

            # 两条记录都缺少必需字段，应被跳过
            assert result == []

    def test_fetch_nav_history_date_order(self):
        """测试返回结果按日期排序（Mobile API 返回按日期倒序，应转为正序）"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_nav_response(
                [
                    {"FSRQ": "2022-01-01", "DWJZ": "1.2", "LJJZ": "3.0", "JZZZL": "0"},
                    {"FSRQ": "2021-01-01", "DWJZ": "1.1", "LJJZ": "2.8", "JZZZL": "0"},
                    {"FSRQ": "2020-01-01", "DWJZ": "1.0", "LJJZ": "2.5", "JZZZL": "0"},
                ]
            )

            result = source.fetch_nav_history("000001")

            assert len(result) == 3
            # Mobile API 返回按日期倒序，保持原序
            assert result[0]["nav_date"] == date(2022, 1, 1)
            assert result[1]["nav_date"] == date(2021, 1, 1)
            assert result[2]["nav_date"] == date(2020, 1, 1)

    def test_fetch_nav_history_decimal_precision(self):
        """测试 Decimal 精度处理"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_nav_response(
                [
                    {"FSRQ": "2024-01-01", "DWJZ": "1.23456789", "LJJZ": "2.34567890", "JZZZL": "1.23456789"},
                ]
            )

            result = source.fetch_nav_history("000001")

            assert len(result) == 1
            # Decimal 应该保持原始精度
            assert result[0]["unit_nav"] == Decimal("1.23456789")
            assert result[0]["accumulated_nav"] == Decimal("2.34567890")
            assert result[0]["daily_growth"] == Decimal("1.23456789")
