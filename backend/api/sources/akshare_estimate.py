"""
akshare 估值引擎

M2: 替代已失效的 fundgz JSONP，通过 akshare 获取全市场基金实时估值。

akshare.fund_em_value_estimation() 单次返回所有基金的估值数据（DataFrame），
引擎在内存中缓存 5 分钟，避免频繁 HTTP 调用。

这不是数据源（不继承 BaseEstimateSource）——它是估值计算引擎，
被 EastMoneySource.fetch_estimate() 调用。职责分离：
- 数据源管数据获取（净值、持仓等）
- 引擎管估值计算
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class AkshareEstimateEngine:
    """akshare 估值引擎

    通过在内存中缓存全市场估值 DataFrame 来减少 API 调用。
    缓存 TTL 5 分钟，与 estimate_cache_ttl 一致。
    """

    _cache_ttl: int = 300  # 5 分钟（秒）

    def __init__(self) -> None:
        self._cached_df: Optional[pd.DataFrame] = None
        self._last_fetch_time: Optional[datetime] = None

    # ── 公开方法 ──────────────────────────────────────────

    def get_estimate(self, fund_code: str) -> Optional[Dict]:
        """
        获取单只基金估值

        Args:
            fund_code: 基金代码

        Returns:
            {
                'fund_code': str,
                'fund_name': str,
                'estimate_nav': Decimal,
                'estimate_growth': Decimal,
                'estimate_time': datetime,
            }
            或 None（基金不存在 / 数据不可用）
        """
        df = self._load_all_estimates()
        if df.empty:
            return None
        return self._extract_fund(df, fund_code)

    def get_batch_estimate(self, fund_codes: List[str]) -> Dict[str, Optional[Dict]]:
        """
        批量获取估值

        Args:
            fund_codes: 基金代码列表

        Returns:
            {fund_code: dict 或 None}
        """
        df = self._load_all_estimates()
        results: Dict[str, Optional[Dict]] = {}
        for code in fund_codes:
            if df.empty:
                results[code] = None
            else:
                results[code] = self._extract_fund(df, code)
        return results

    def _refresh_cache(self) -> None:
        """强制刷新缓存"""
        self._cached_df = None
        self._last_fetch_time = None

    # ── 内部方法 ──────────────────────────────────────────

    def _load_all_estimates(self) -> pd.DataFrame:
        """
        加载全市场估值 DataFrame

        如果缓存有效（5 分钟内）返回缓存；否则调 akshare 重新拉取。
        异常时返回空 DataFrame，不抛异常。
        """
        now = datetime.now(timezone.utc)

        # 缓存命中
        if (
            self._cached_df is not None
            and self._last_fetch_time is not None
            and (now - self._last_fetch_time).total_seconds() < self._cache_ttl
        ):
            return self._cached_df

        # 缓存过期 / 首次加载
        try:
            import akshare as ak

            df = ak.fund_value_estimation_em()
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                logger.warning("akshare fund_em_value_estimation 返回空数据")
                self._cached_df = pd.DataFrame()
            else:
                self._cached_df = df
            self._last_fetch_time = now
        except Exception as e:
            logger.warning(f"akshare 获取全市场估值失败: {e}")
            # 异常时不清除已有缓存（如果有的话），但标记时间为 now
            # 这样下次调用会在一段时间后重试
            if self._cached_df is None:
                self._cached_df = pd.DataFrame()
            self._last_fetch_time = now

        return self._cached_df

    def _extract_fund(
        self, df: pd.DataFrame, fund_code: str
    ) -> Optional[Dict]:
        """
        从 DataFrame 中提取单只基金的估值数据

        akshare 1.18 列名（会因版本和交易时段变化）:
        - 基金代码            → fund_code
        - 基金名称            → fund_name
        - 交易日-估算数据-估算值   → estimate_nav（或旧版: 估算值）
        - 交易日-估算数据-估算增长率 → estimate_growth（或旧版: 估算增长率）
        - 交易日-单位净值       → 参考净值日期
        - (无)                → estimate_time = timezone.now()
        """
        # 检查必需列 — 兼容新旧 akshare 列名格式
        code_col = "基金代码"
        if code_col not in df.columns:
            logger.warning("akshare DataFrame 缺少基金代码列")
            return None

        # 估值净值列：兼容新旧格式
        nav_col = None
        for candidate in ("交易日-估算数据-估算值", "估算值"):
            if candidate in df.columns:
                nav_col = candidate
                break
        if nav_col is None:
            logger.warning("akshare DataFrame 缺少估算值列")
            return None

        # 增长率列：兼容新旧格式
        growth_col = None
        for candidate in ("交易日-估算数据-估算增长率", "估算增长率"):
            if candidate in df.columns:
                growth_col = candidate
                break

        # 按基金代码筛选
        row = df[df[code_col] == fund_code]
        if row.empty:
            return None

        row = row.iloc[0]

        # 估值净值
        try:
            estimate_nav = Decimal(str(row[nav_col]))
        except (InvalidOperation, ValueError, TypeError):
            logger.warning(f"无法解析 {fund_code} 的估算值: {row.get(nav_col)}")
            return None

        # 估值增长率（去掉可能存在的 % 符号）
        estimate_growth = None
        if growth_col:
            growth_val = row.get(growth_col)
            if growth_val is not None:
                try:
                    growth_str = str(growth_val).replace("%", "").strip()
                    estimate_growth = Decimal(growth_str)
                except (InvalidOperation, ValueError, TypeError):
                    pass

        # 基金名称（可选）
        fund_name = ""
        name_col = "基金名称"
        if name_col in df.columns:
            fund_name = str(row[name_col]) if row.get(name_col) else ""

        return {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "estimate_nav": estimate_nav,
            "estimate_growth": estimate_growth,
            "estimate_time": datetime.now(timezone.utc),
        }
