"""
测试 PenetrationEngine (M3 功能1)

穿透估算引擎 — 通过基金持仓成分股权重 + 个股实时行情，
反向加权推算基金实时估值。
"""

import pytest
from decimal import Decimal
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock

from api.sources.penetration_engine import PenetrationEngine


# ── 辅助: 构造测试数据 ──

def _sample_holdings():
    """上证 50 ETF 前十大成分股"""
    return [
        {"stock_code": "600519", "stock_name": "贵州茅台", "weight": Decimal("7.29"),
         "price": None, "change_percent": None},
        {"stock_code": "601318", "stock_name": "中国平安", "weight": Decimal("6.50"),
         "price": None, "change_percent": None},
        {"stock_code": "600036", "stock_name": "招商银行", "weight": Decimal("5.80"),
         "price": None, "change_percent": None},
        {"stock_code": "601166", "stock_name": "兴业银行", "weight": Decimal("3.90"),
         "price": None, "change_percent": None},
        {"stock_code": "600887", "stock_name": "伊利股份", "weight": Decimal("3.50"),
         "price": None, "change_percent": None},
    ]


def _sample_quotes():
    """个股实时行情（模拟)"""
    return {
        "600519": {"price": Decimal("1337.44"), "change_percent": Decimal("1.32")},
        "601318": {"price": Decimal("52.30"), "change_percent": Decimal("-0.80")},
        "600036": {"price": Decimal("42.10"), "change_percent": Decimal("0.50")},
        "601166": {"price": Decimal("18.65"), "change_percent": Decimal("1.20")},
        "600887": {"price": Decimal("28.90"), "change_percent": Decimal("-0.30")},
    }


# ================================================================
# _is_applicable — 基金类型适用性
# ================================================================

class TestIsApplicable:
    """_is_applicable 类型判断"""

    def test_etf_applicable(self):
        engine = PenetrationEngine()
        assert engine._is_applicable("指数型-股票") is True
        assert engine._is_applicable("ETF-场内") is True

    def test_stock_fund_applicable(self):
        engine = PenetrationEngine()
        assert engine._is_applicable("股票型") is True
        assert engine._is_applicable("混合型-灵活") is True
        assert engine._is_applicable("混合型-偏股") is True

    def test_bond_not_applicable(self):
        engine = PenetrationEngine()
        assert engine._is_applicable("债券型") is False
        assert engine._is_applicable("债券型-长债") is False

    def test_money_not_applicable(self):
        engine = PenetrationEngine()
        assert engine._is_applicable("货币型") is False

    def test_qdii_not_applicable(self):
        engine = PenetrationEngine()
        assert engine._is_applicable("QDII") is False
        assert engine._is_applicable("QDII-股票") is False

    def test_none_type_applicable(self):
        """未知类型默认适用（不因缺少类型信息而放弃）"""
        engine = PenetrationEngine()
        assert engine._is_applicable(None) is True
        assert engine._is_applicable("") is True


# ================================================================
# _calculate — 加权推算
# ================================================================

class TestCalculate:
    """_calculate 加权推算核心算法"""

    def test_etf_no_coverage_ratio(self):
        """ETF 不乘覆盖率系数"""
        engine = PenetrationEngine()
        latest_nav = Decimal("1.2345")

        result = engine._calculate(
            _sample_holdings(), _sample_quotes(), "ETF-场内", latest_nav
        )

        assert result is not None
        # 手动验算:
        # weights = [7.29, 6.50, 5.80, 3.90, 3.50], sum = 26.99
        # normalized = [0.2701, 0.2408, 0.2149, 0.1445, 0.1297]
        # fund_growth = 0.2701*1.32 + 0.2408*(-0.80) + 0.2149*0.50 + 0.1445*1.20 + 0.1297*(-0.30)
        #            = 0.3565 - 0.1927 + 0.1075 + 0.1734 - 0.0389 = 0.4058
        # 约 0.4058%
        expected_growth = Decimal("0.4058")
        assert abs(result["estimate_growth"] - expected_growth) < Decimal("0.01"), (
            f"ETF 涨跌幅应约 0.4058%, 实际: {result['estimate_growth']}"
        )

        # estimate_nav = 1.2345 * (1 + 0.4058/100) ≈ 1.2395
        expected_nav = Decimal("1.2395")
        assert abs(result["estimate_nav"] - expected_nav) < Decimal("0.01"), (
            f"估值净值应约 1.2395, 实际: {result['estimate_nav']}"
        )

    def test_normalized_weights_sum_to_one(self):
        """归一化后的权重之和应为 1.0"""
        engine = PenetrationEngine()
        # 自己算一下归一化
        holdings = _sample_holdings()
        total_weight = sum(h["weight"] for h in holdings)
        normalized = [h["weight"] / total_weight for h in holdings]
        assert abs(sum(normalized) - Decimal("1.0")) < Decimal("0.0001")

    def test_missing_one_quote_still_works(self):
        """缺少少量行情（< 30%）时跳过缺失的，仍可计算"""
        engine = PenetrationEngine()
        quotes = _sample_quotes().copy()
        del quotes["600887"]  # 权重 3.50/26.99 ≈ 13% < 30%

        result = engine._calculate(
            _sample_holdings(), quotes, "ETF-场内", Decimal("1.0")
        )
        assert result is not None  # 13% 缺失 → 仍可计算

    def test_low_precision_when_over_30pct_missing(self):
        """超过 30% 成分股缺行情 → 返回 None"""
        engine = PenetrationEngine()
        quotes = {"600519": _sample_quotes()["600519"]}  # 只有 1/5 = 80% 缺

        result = engine._calculate(
            _sample_holdings(), quotes, "ETF-场内", Decimal("1.0")
        )
        assert result is None

    def test_latest_nav_none_returns_none(self):
        """最新净值为 None → 无法推算"""
        engine = PenetrationEngine()
        result = engine._calculate(
            _sample_holdings(), _sample_quotes(), "ETF-场内", None
        )
        assert result is None

    def test_decimal_precision(self):
        """所有计算使用 Decimal，防止浮点精度问题"""
        engine = PenetrationEngine()
        result = engine._calculate(
            _sample_holdings(), _sample_quotes(), "ETF-场内", Decimal("1.0")
        )
        assert isinstance(result["estimate_nav"], Decimal)
        assert isinstance(result["estimate_growth"], Decimal)

    def test_zero_weight_filtered(self):
        """权重为零的成分股被过滤"""
        engine = PenetrationEngine()
        holdings = _sample_holdings() + [
            {"stock_code": "000000", "stock_name": "零权重", "weight": Decimal("0"),
             "price": None, "change_percent": None},
        ]
        result = engine._calculate(holdings, _sample_quotes(), "ETF-场内", Decimal("1.0"))
        assert result is not None  # 零权重不影响计算


# ================================================================
# estimate — 顶层接口
# ================================================================

class TestEstimate:
    """estimate 顶层接口"""

    def test_not_applicable_for_bond(self):
        """债券型 → not_applicable"""
        engine = PenetrationEngine()
        data, reason = engine.estimate("000001", "债券型")
        assert data is None
        assert reason == "not_applicable"

    def test_not_applicable_for_qdii(self):
        """QDII → not_applicable"""
        engine = PenetrationEngine()
        data, reason = engine.estimate("000001", "QDII")
        assert data is None
        assert reason == "not_applicable"

    def test_no_holdings_when_fetch_fails(self):
        """获取持仓失败 → no_holdings"""
        engine = PenetrationEngine()

        with patch.object(engine, "_get_holdings", return_value=[]):
            data, reason = engine.estimate("510050", "ETF-场内")

        assert data is None
        assert reason == "no_holdings"

    def test_success_with_etf(self):
        """ETF 穿透估算成功"""
        engine = PenetrationEngine()

        with patch.object(engine, "_get_holdings", return_value=_sample_holdings()):
            with patch.object(engine, "_get_quotes", return_value=_sample_quotes()):
                with patch.object(engine, "_get_latest_nav", return_value=Decimal("1.2345")):
                    data, reason = engine.estimate("510050", "ETF-场内")

        assert data is not None
        assert reason == "success"
        assert "estimate_nav" in data
        assert "estimate_growth" in data
        assert "estimate_time" in data
        assert data.get("method") == "penetration"


# ================================================================
# _get_quotes — 行情缓存
# ================================================================

class TestGetQuotes:
    """_get_quotes 批量获取 + 缓存"""

    def test_batch_fetch(self):
        """批量获取个股行情"""
        engine = PenetrationEngine()

        with patch("api.sources.sina.SinaStockSource.fetch_market_quote") as mock_sina:
            def fake_quote(code):
                return {
                    "fund_code": code, "market_price": Decimal("10.0"),
                    "market_growth": Decimal("1.0"), "market_time": "2026-07-29",
                    "symbol": f"sh{code}",
                }
            mock_sina.side_effect = fake_quote

            quotes = engine._get_quotes(["600519", "601318"])

        assert len(quotes) == 2
        assert quotes["600519"]["price"] == Decimal("10.0")
        assert quotes["601318"]["change_percent"] == Decimal("1.0")

    def test_cache_hit(self):
        """缓存命中不调 Sina"""
        engine = PenetrationEngine()
        engine._quote_cache["600519"] = {
            "price": Decimal("100.0"), "change_percent": Decimal("2.0"),
            "ts": datetime.now().timestamp(),
        }

        with patch("api.sources.sina.SinaStockSource.fetch_market_quote") as mock_sina:
            quotes = engine._get_quotes(["600519"])

        assert quotes["600519"]["price"] == Decimal("100.0")
        mock_sina.assert_not_called()

    def test_cache_expired_refetches(self):
        """缓存过期重新拉取"""
        engine = PenetrationEngine()
        engine._quote_cache["600519"] = {
            "price": Decimal("100.0"), "change_percent": Decimal("2.0"),
            "ts": (datetime.now() - timedelta(seconds=40)).timestamp(),  # 过期
        }

        with patch("api.sources.sina.SinaStockSource.fetch_market_quote") as mock_sina:
            mock_sina.return_value = {
                "fund_code": "600519", "market_price": Decimal("101.0"),
                "market_growth": Decimal("3.0"), "market_time": "2026-07-29",
                "symbol": "sh600519",
            }
            quotes = engine._get_quotes(["600519"])

        assert quotes["600519"]["price"] == Decimal("101.0")  # 新数据
        mock_sina.assert_called_once()
