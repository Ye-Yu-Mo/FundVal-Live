"""
Sina 行情批量获取测试

回归：
1. 多只股票一次请求完成，不再逐只请求
2. 响应按行解析，GBK 编码
3. 单只查询复用批量实现
4. 网络错误不向上抛
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from api.sources.sina import SinaStockSource


def _quote_line(symbol: str, name: str, prev_close: str, current: str) -> str:
    fields = [name, "0", prev_close, current, current, current, "0", "0", "0", "0"]
    fields += ["0"] * 20
    fields += ["2026-10-23", "15:34:59"]
    assert len(fields) == 32
    return f'var hq_str_{symbol}="{",".join(fields)}";'


def _mock_response(text: str) -> MagicMock:
    mock = MagicMock()
    mock.text = text
    mock.raise_for_status = MagicMock()
    return mock


class TestSinaBatchQuotes:
    def test_multiple_codes_in_one_request(self):
        source = SinaStockSource()
        text = "\n".join(
            [
                _quote_line("sh600177", "雅戈尔", "8.12", "8.11"),
                _quote_line("sh600188", "兖矿能源", "18.10", "18.29"),
            ]
        )

        with patch("api.sources.sina.requests.get") as mock_get:
            mock_get.return_value = _mock_response(text)
            quotes = source.fetch_market_quotes(["600177", "600188"])

        assert set(quotes) == {"600177", "600188"}
        assert quotes["600177"]["market_price"] == Decimal("8.11")
        assert quotes["600188"]["market_price"] == Decimal("18.29")
        assert round(float(quotes["600188"]["market_growth"]), 2) == 1.05
        mock_get.assert_called_once()
        called_url = mock_get.call_args[0][0]
        assert "sh600177" in called_url
        assert "sh600188" in called_url

    def test_single_quote_delegates_to_batch(self):
        source = SinaStockSource()
        expected = {"600177": {"market_price": Decimal("8.11")}}

        with patch.object(
            SinaStockSource, "fetch_market_quotes", return_value=expected
        ) as mock_batch:
            result = source.fetch_market_quote("600177")

        assert result == expected["600177"]
        mock_batch.assert_called_once_with(["600177"])

    def test_malformed_lines_are_skipped(self):
        source = SinaStockSource()
        text = "\n".join(
            [
                "not a quote line",
                _quote_line("sh600177", "雅戈尔", "8.12", "8.11"),
                'var hq_str_sh600188="too,short";',
            ]
        )

        with patch("api.sources.sina.requests.get") as mock_get:
            mock_get.return_value = _mock_response(text)
            quotes = source.fetch_market_quotes(["600177", "600188"])

        assert set(quotes) == {"600177"}

    def test_network_error_returns_empty(self):
        source = SinaStockSource()

        with patch("api.sources.sina.requests.get") as mock_get:
            mock_get.side_effect = TimeoutError("read timed out")
            quotes = source.fetch_market_quotes(["600177"])

        assert quotes == {}
