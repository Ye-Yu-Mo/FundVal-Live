"""
穿透估算引擎

M3: 作为 akshare 估值失败时的 fallback 引擎。

通过基金持仓成分股权重 + 个股实时行情，反向加权推算基金实时估值。
优先覆盖 ETF/指数型基金（持仓透明、精度高）。

与 AkshareEstimateEngine 对称 — 都是估值引擎，不是数据源。
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal

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
        self._quote_cache: dict[str, dict] = {}  # stock_code → {price, change_percent, ts}

    # ── 公开方法 ──────────────────────────────────────────

    def estimate(self, fund_code: str, fund_type: str = None) -> tuple[dict | None, str]:
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
        blocked = {"债券", "货币", "债", "货"}
        for keyword in blocked:
            if keyword in ft:
                return False
        return True

    def _get_holdings(self, fund_code: str) -> list[dict]:
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

    def _get_latest_nav(self, fund_code: str) -> Decimal | None:
        """获取基金最新净值"""
        try:
            from api.models import Fund

            fund = Fund.objects.filter(fund_code=fund_code).first()
            if fund and fund.latest_nav:
                return fund.latest_nav
        except Exception as e:
            logger.warning(f"获取最新净值失败 ({fund_code}): {e}")
        return None

    def _get_quotes(self, stock_codes: list[str]) -> dict[str, dict]:
        """
        批量获取个股实时行情

        M4: 按股票代码格式分流到不同行情源。
        - 6 位数字 → A股 → SinaStockSource
        - 5 位数字 → 港股 → EastMoney push2 API (HTTPS, secid 前缀 116)
        - 字母 + 数字 → 美股 → EastMoney push2 API (HTTPS, secid 前缀 105/106)

        内存缓存 30s TTL，所有市场共享 _quote_cache。

        Returns:
            {stock_code: {price, change_percent}, ...}
        """
        result = {}
        need_sina = []  # A股 — Sina
        need_hk = []  # 港股 — akshare
        need_us = []  # 美股 — akshare

        now_ts = datetime.now().timestamp()

        # 分离缓存命中和未命中，按市场分组
        for code in stock_codes:
            cached = self._quote_cache.get(code)
            if cached and (now_ts - cached["ts"]) < QUOTE_CACHE_TTL:
                result[code] = {
                    "price": cached["price"],
                    "change_percent": cached["change_percent"],
                }
                continue

            market = self._detect_market(code)
            if market == "hk":
                need_hk.append(code)
            elif market == "us":
                need_us.append(code)
            else:
                need_sina.append(code)

        # A股 — Sina（现有逻辑）
        if need_sina:
            self._fetch_sina_quotes(need_sina, result, now_ts)

        # 港股 — akshare（M4 新增）
        if need_hk:
            self._fetch_hk_quotes(need_hk, result, now_ts)

        # 美股 — akshare（M4 新增）
        if need_us:
            self._fetch_us_quotes(need_us, result, now_ts)

        return result

    # ── 市场检测 ───────────────────────────────────────────

    @staticmethod
    def _detect_market(code: str) -> str:
        """
        检测股票所属市场

        - 1-5 位纯数字 → 港股 (hk) — 港股代码 1-5 位，如 "5", "700", "00700"
        - 6 位纯数字 → A股 (a)
        - 字母 + 数字混合 → 美股 (us)
        - 其他 → A股兜底
        """
        if not code:
            return "a"
        if code.isdigit():
            if len(code) <= 5:
                return "hk"
            return "a"  # 6 位 → A股
        return "us"  # 含字母 → 美股

    # ── A股行情（Sina）─────────────────────────────────────

    def _fetch_sina_quotes(self, codes: list[str], result: dict, now_ts: float) -> None:
        """通过 SinaStockSource 获取 A 股行情"""
        try:
            from .sina import SinaStockSource
            import time

            sina = SinaStockSource()
            for code in codes:
                try:
                    quote = sina.fetch_market_quote(code)
                    if quote and quote.get("market_price") is not None:
                        price = quote["market_price"]
                        change_pct = quote.get("market_growth", Decimal("0"))
                        result[code] = {"price": price, "change_percent": change_pct}
                        self._quote_cache[code] = {
                            "price": price,
                            "change_percent": change_pct,
                            "ts": now_ts,
                        }
                    time.sleep(0.1)  # M4: 100ms 间隔，防 Sina 限流
                except Exception as e:
                    logger.debug(f"A股行情获取失败 ({code}): {e}")
        except Exception as e:
            logger.warning(f"Sina 行情批量获取失败: {e}")

    # ── 港股行情（EastMoney push2 API, HTTPS）─────────────────

    _PUSH2_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"

    def _fetch_hk_quotes(self, codes: list[str], result: dict, now_ts: float) -> None:
        """通过 EastMoney push2 API (HTTPS) 获取港股行情，secid 前缀 116"""
        import requests

        # 港股代码规范化：zfill(5) 对齐（"700" → "00700"）
        normalized_map = {str(c).zfill(5): c for c in codes}

        try:
            secids = [f"116.{n}" for n in normalized_map]
            resp = requests.get(
                self._PUSH2_URL,
                params={"secids": ",".join(secids), "fields": "f12,f14,f2,f3", "fltt": "2"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("data", {}).get("diff", []):
                api_code = item["f12"]  # push2 返回的代码（如 "00700"）
                orig_code = normalized_map.get(api_code, api_code)  # 还原为原始代码
                try:
                    price = (
                        Decimal(str(item.get("f2", "0")))
                        if item.get("f2") not in (None, "-")
                        else None
                    )
                    change_pct = (
                        Decimal(str(item.get("f3", "0")))
                        if item.get("f3") not in (None, "-")
                        else Decimal("0")
                    )
                    if price is not None:
                        result[orig_code] = {"price": price, "change_percent": change_pct}
                        self._quote_cache[orig_code] = {
                            "price": price,
                            "change_percent": change_pct,
                            "ts": now_ts,
                        }
                except Exception as e:
                    logger.debug(f"港股行情解析失败 ({orig_code}): {e}")
        except Exception as e:
            logger.warning(f"港股行情获取失败: {e}")

    # ── 美股行情（EastMoney push2 API, HTTPS）─────────────────

    def _fetch_us_quotes(self, codes: list[str], result: dict, now_ts: float) -> None:
        """通过 EastMoney push2 API (HTTPS) 获取美股行情，secid 前缀 105/106"""
        import requests

        try:
            for prefix in ("105", "106"):
                secids = [f"{prefix}.{code}" for code in codes]
                resp = requests.get(
                    self._PUSH2_URL,
                    params={"secids": ",".join(secids), "fields": "f12,f14,f2,f3", "fltt": "2"},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("data", {}).get("diff", []):
                    code = item["f12"]
                    if code in result:
                        continue
                    try:
                        price = (
                            Decimal(str(item.get("f2", "0")))
                            if item.get("f2") not in (None, "-")
                            else None
                        )
                        change_pct = (
                            Decimal(str(item.get("f3", "0")))
                            if item.get("f3") not in (None, "-")
                            else Decimal("0")
                        )
                        if price is not None:
                            result[code] = {"price": price, "change_percent": change_pct}
                            self._quote_cache[code] = {
                                "price": price,
                                "change_percent": change_pct,
                                "ts": now_ts,
                            }
                    except Exception as e:
                        logger.debug(f"美股行情解析失败 ({code}): {e}")
        except Exception as e:
            logger.warning(f"美股行情获取失败: {e}")

    def _calculate(
        self,
        holdings: list[dict],
        quotes: dict[str, dict],
        fund_type: str | None,
        latest_nav: Decimal,
    ) -> dict | None:
        """
        加权推算基金估值

        ETF/指数型: fund_growth = Σ(normalized_weight[i] × change[i])
        主动型:     fund_growth = Σ(normalized_weight[i] × change[i]) × coverage_ratio
        """
        if latest_nav is None:
            return None

        # 过滤有效持仓：有权重且权重 > 0
        valid_holdings = [h for h in holdings if h.get("weight") and h["weight"] > Decimal("0")]

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
            "estimate_time": datetime.now(UTC),
        }
