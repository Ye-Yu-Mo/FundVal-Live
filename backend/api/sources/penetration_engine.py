"""
穿透估算引擎

M3: 作为 akshare 估值失败时的 fallback 引擎。

通过基金持仓成分股权重 + 个股实时行情，反向加权推算基金实时估值。
优先覆盖 ETF/指数型基金（持仓透明、精度高）。

与 AkshareEstimateEngine 对称 — 都是估值引擎，不是数据源。
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 行情缓存 TTL（秒）
QUOTE_CACHE_TTL = 30
# 精度门禁：超过此比例的成分股缺少行情则放弃
MAX_MISSING_QUOTE_RATIO = 0.30


class PenetrationEngine:
    """穿透估算引擎

    通过前十大成分股权重 + 实时行情加权推算基金涨跌幅。
    ETF/指数基金不乘覆盖率系数（成分股高度相关）。
    """

    def __init__(self) -> None:
        self._quote_cache: Dict[str, Dict] = {}  # stock_code → {price, change_percent, ts}

    # ── 公开方法 ──────────────────────────────────────────

    def estimate(
        self, fund_code: str, fund_type: str = None
    ) -> Tuple[Optional[Dict], str]:
        """
        穿透估算单只基金

        Args:
            fund_code: 基金代码
            fund_type: 基金类型（用于适用性判断）

        Returns:
            (data, reason)
            - data: {estimate_nav, estimate_growth, estimate_time, method: "penetration"} 或 None
            - reason: "success" / "not_applicable" / "no_holdings" / "no_quotes" / "low_precision"
        """
        # 1. 类型检查
        if not self._is_applicable(fund_type):
            return None, "not_applicable"

        # 2. 获取持仓
        holdings = self._get_holdings(fund_code)
        if not holdings:
            return None, "no_holdings"

        # 3. 获取最新净值
        latest_nav = self._get_latest_nav(fund_code)
        if latest_nav is None:
            return None, "no_nav"

        # 4. 获取个股行情
        stock_codes = [h["stock_code"] for h in holdings if h.get("stock_code")]
        quotes = self._get_quotes(stock_codes)

        # 5. 加权推算
        result = self._calculate(holdings, quotes, fund_type, latest_nav)
        if result is None:
            return None, "low_precision"

        result["method"] = "penetration"
        return result, "success"

    # ── 内部方法 ──────────────────────────────────────────

    def _is_applicable(self, fund_type: str) -> bool:
        """
        判断基金类型是否适用穿透估算

        ETF/指数/股票/混合 → True
        债券/货币/QDII → False
        未知类型 → True（不因缺少类型信息而放弃）
        """
        if not fund_type:
            return True

        ft = fund_type.lower()
        # 不适用的类型
        blocked = {"债券", "货币", "qdii", "债", "货"}
        for keyword in blocked:
            if keyword in ft:
                return False
        return True

    def _get_holdings(self, fund_code: str) -> List[Dict]:
        """
        获取持仓权重列表

        M3a: 复用 EastMoneySource.fetch_index_holdings（ETF/指数型）。
        M3b: 扩展为 akshare 季报持仓（主动型）。

        Returns:
            [{stock_code, stock_name, weight, price, change_percent}, ...]
        """
        try:
            from .eastmoney import EastMoneySource

            source = EastMoneySource()
            holdings = source.fetch_index_holdings(fund_code)
            if not holdings:
                # 尝试不带前缀的代码
                return []
            return holdings
        except Exception as e:
            logger.warning(f"获取持仓失败 ({fund_code}): {e}")
            return []

    def _get_latest_nav(self, fund_code: str) -> Optional[Decimal]:
        """获取基金最新净值"""
        try:
            from api.models import Fund

            fund = Fund.objects.filter(fund_code=fund_code).first()
            if fund and fund.latest_nav:
                return fund.latest_nav
        except Exception as e:
            logger.warning(f"获取最新净值失败 ({fund_code}): {e}")
        return None

    def _get_quotes(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取个股实时行情

        M3: 优先走内存缓存（30s TTL），缓存未命中时调 SinaStockSource。
        Redis 增强后续可加。

        Returns:
            {stock_code: {price, change_percent}, ...}
        """
        result = {}
        need_fetch = []

        now_ts = datetime.now().timestamp()

        # 分离缓存命中和未命中
        for code in stock_codes:
            cached = self._quote_cache.get(code)
            if cached and (now_ts - cached["ts"]) < QUOTE_CACHE_TTL:
                result[code] = {
                    "price": cached["price"],
                    "change_percent": cached["change_percent"],
                }
            else:
                need_fetch.append(code)

        if not need_fetch:
            return result

        # 调 Sina 获取
        try:
            from .sina import SinaStockSource

            sina = SinaStockSource()
            for code in need_fetch:
                try:
                    quote = sina.fetch_market_quote(code)
                    if quote and quote.get("market_price") is not None:
                        price = quote["market_price"]
                        change_pct = quote.get("market_growth", Decimal("0"))
                        result[code] = {
                            "price": price,
                            "change_percent": change_pct,
                        }
                        self._quote_cache[code] = {
                            "price": price,
                            "change_percent": change_pct,
                            "ts": now_ts,
                        }
                except Exception as e:
                    logger.debug(f"个股行情获取失败 ({code}): {e}")
        except Exception as e:
            logger.warning(f"批量获取行情失败: {e}")

        return result

    def _calculate(
        self,
        holdings: List[Dict],
        quotes: Dict[str, Dict],
        fund_type: Optional[str],
        latest_nav: Decimal,
    ) -> Optional[Dict]:
        """
        加权推算基金估值

        ETF/指数型: fund_growth = Σ(normalized_weight[i] × change[i])
        主动型:     fund_growth = Σ(normalized_weight[i] × change[i]) × coverage_ratio
        """
        if latest_nav is None:
            return None

        # 过滤有效持仓：有权重且权重 > 0
        valid_holdings = [h for h in holdings
                          if h.get("weight") and h["weight"] > Decimal("0")]

        if not valid_holdings:
            return None

        # 计算行情覆盖率
        total_weight = sum(h["weight"] for h in valid_holdings)
        matched_weight = Decimal("0")
        for h in valid_holdings:
            if h["stock_code"] in quotes:
                matched_weight += h["weight"]

        missing_ratio = Decimal("1") - (matched_weight / total_weight)
        if missing_ratio > Decimal(str(MAX_MISSING_QUOTE_RATIO)):
            return None  # low_precision

        # 权重归一化 + 加权计算涨跌幅
        fund_growth = Decimal("0")
        for h in valid_holdings:
            code = h["stock_code"]
            if code not in quotes:
                continue
            normalized_weight = h["weight"] / total_weight
            fund_growth += normalized_weight * quotes[code]["change_percent"]

        # ETF/指数型不乘 coverage_ratio（调研报告修正）
        is_etf = fund_type and ("etf" in fund_type.lower() or "指数" in fund_type)
        if not is_etf:
            # 主动型：乘覆盖率系数（剩余仓位未知，保守假设涨跌=0）
            coverage_ratio = matched_weight / total_weight
            fund_growth *= coverage_ratio

        # 推算净值
        estimate_nav = latest_nav * (Decimal("1") + fund_growth / Decimal("100"))

        # 四舍五入到合理精度
        estimate_nav = estimate_nav.quantize(Decimal("0.0001"))
        fund_growth = fund_growth.quantize(Decimal("0.0001"))

        return {
            "estimate_nav": estimate_nav,
            "estimate_growth": fund_growth,
            "estimate_time": datetime.now(timezone.utc),
        }
