"""
EastMoney 持仓行情测试

回归：
1. A 股持仓行情走 Sina 批量接口，不再走 push2 批量接口
2. 港美股持仓仍走 push2
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from api.sources.eastmoney import EastMoneySource


def _holdings_response(stocks):
    mock = MagicMock()
    mock.json.return_value = {"Success": True, "Datas": {"fundStocks": stocks}}
    mock.raise_for_status = MagicMock()
    return mock


def _push2_response(items):
    mock = MagicMock()
    mock.json.return_value = {"data": {"diff": items}}
    mock.raise_for_status = MagicMock()
    return mock


class TestHoldingsQuotes:
    def test_a_share_holdings_use_sina_batch(self):
        stocks = [
            {"GPDM": "600177", "GPJC": "雅戈尔", "JZBL": "2.18", "NEWTEXCH": "1"},
            {"GPDM": "600919", "GPJC": "江苏银行", "JZBL": "2.28", "NEWTEXCH": "1"},
        ]

        with (
            patch(
                "api.sources.eastmoney.requests.get",
                return_value=_holdings_response(stocks),
            ) as mock_get,
            patch(
                "api.sources.sina.SinaStockSource.fetch_market_quotes",
                return_value={
                    "600177": {
                        "market_price": Decimal("8.11"),
                        "market_growth": Decimal("0.50"),
                    },
                    "600919": {
                        "market_price": Decimal("12.00"),
                        "market_growth": Decimal("-0.25"),
                    },
                },
            ) as mock_sina,
        ):
            result = EastMoneySource().fetch_index_holdings("100032")

        assert result[0]["stock_code"] == "600177"
        assert result[0]["price"] == Decimal("8.11")
        assert result[0]["change_percent"] == Decimal("0.50")
        assert result[1]["price"] == Decimal("12.00")
        mock_sina.assert_called_once_with(["600177", "600919"])
        # 只调持仓接口，A 股行情不再调 push2
        assert mock_get.call_count == 1
        assert "push2" not in str(mock_get.call_args)

    def test_hk_holdings_still_use_push2(self):
        stocks = [
            {"GPDM": "00700", "GPJC": "腾讯控股", "JZBL": "5.00", "NEWTEXCH": "116"},
        ]

        def fake_get(url, *args, **kwargs):
            if "FundMNInverstPosition" in str(url):
                return _holdings_response(stocks)
            return _push2_response([{"f12": "00700", "f2": 350.0, "f3": 1.5}])

        with (
            patch("api.sources.eastmoney.requests.get", side_effect=fake_get),
            patch(
                "api.sources.sina.SinaStockSource.fetch_market_quotes",
                return_value={},
            ) as mock_sina,
        ):
            result = EastMoneySource().fetch_index_holdings("513050")

        assert result[0]["stock_code"] == "00700"
        assert result[0]["price"] == Decimal("350.0")
        assert result[0]["change_percent"] == Decimal("1.5")
        mock_sina.assert_not_called()

    def test_sina_failure_does_not_break_holdings(self, caplog):
        stocks = [
            {"GPDM": "600177", "GPJC": "雅戈尔", "JZBL": "2.18", "NEWTEXCH": "1"},
        ]

        with (
            patch(
                "api.sources.eastmoney.requests.get",
                return_value=_holdings_response(stocks),
            ),
            patch(
                "api.sources.sina.SinaStockSource.fetch_market_quotes",
                side_effect=RuntimeError("sina down"),
            ),
        ):
            result = EastMoneySource().fetch_index_holdings("100032")

        assert len(result) == 1
        assert result[0]["price"] is None
        messages = " ".join(record.message for record in caplog.records)
        assert "100032" in messages
        assert "600177" in messages
