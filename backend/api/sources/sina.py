import logging
import re
from decimal import Decimal, InvalidOperation

import requests

from .base import BaseEstimateSource

logger = logging.getLogger(__name__)


class SinaStockSource(BaseEstimateSource):
    """新浪财经股票/ETF实时行情"""

    BASE_URL = "https://hq.sinajs.cn/list={symbols}"
    HEADERS = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    BATCH_SIZE = 50

    def get_source_name(self) -> str:
        return "sina"

    def fetch_estimate(self, fund_code: str) -> dict | None:
        """实现 BaseEstimateSource 接口，虽然它主要用于场外估值，但我们也可以统一返回"""
        return self.fetch_market_quote(fund_code)

    def fetch_realtime_nav(self, fund_code: str) -> dict | None:
        return None

    def fetch_today_nav(self, fund_code: str) -> dict | None:
        """sina 源不支持确权净值查询，仅支持实时行情"""
        return None

    def get_login_type(self) -> str:
        return "none"

    def fetch_fund_list(self) -> list:
        return []

    def fetch_nav_history(self, fund_code: str, start_date=None, end_date=None) -> list[dict]:
        return []

    @staticmethod
    def _to_symbol(fund_code: str) -> str:
        """把 6 位代码转成 Sina 的 sh/sz 前缀格式"""
        if fund_code.startswith(("50", "51", "52", "56", "58")):
            prefix = "sh"
        elif fund_code.startswith(("15", "16", "18")):
            prefix = "sz"
        else:
            prefix = "sh" if fund_code.startswith("6") else "sz"
        return f"{prefix}{fund_code}"

    def fetch_market_quote(self, fund_code: str) -> dict | None:
        """获取单只场内实时价格（复用批量实现）"""
        return self.fetch_market_quotes([fund_code]).get(fund_code)

    def fetch_market_quotes(self, fund_codes: list[str]) -> dict[str, dict]:
        """
        批量获取场内实时价格

        一次请求最多 BATCH_SIZE 只，返回 {代码: 行情}。
        单只失败不影响整批，网络异常返回已解析到的部分。
        """
        result: dict[str, dict] = {}
        codes = [code for code in dict.fromkeys(fund_codes) if code]

        for start in range(0, len(codes), self.BATCH_SIZE):
            batch = codes[start : start + self.BATCH_SIZE]
            symbols = {self._to_symbol(code): code for code in batch}
            try:
                response = requests.get(
                    self.BASE_URL.format(symbols=",".join(symbols)),
                    headers=self.HEADERS,
                    timeout=10,
                )
                response.raise_for_status()
                response.encoding = "gbk"

                for line in response.text.splitlines():
                    match = re.search(r'hq_str_([^=]+)="(.*)"', line)
                    if not match:
                        continue
                    symbol, payload = match.group(1), match.group(2)
                    code = symbols.get(symbol)
                    if not code:
                        continue
                    quote = self._parse_quote(code, symbol, payload)
                    if quote:
                        result[code] = quote
            except Exception as e:
                logger.error(f"Sina batch fetch error ({len(batch)} codes): {e}")

        return result

    @staticmethod
    def _parse_quote(fund_code: str, symbol: str, payload: str) -> dict | None:
        """解析 Sina 单行行情数据"""
        parts = payload.split(",")
        if len(parts) < 32:
            return None

        try:
            current_price = Decimal(parts[3])
            prev_close = Decimal(parts[2])
        except (InvalidOperation, ValueError, TypeError):
            return None

        if current_price == 0:
            current_price = prev_close

        growth = Decimal(0)
        if prev_close > 0:
            growth = ((current_price - prev_close) / prev_close) * 100

        return {
            "fund_code": fund_code,
            "market_price": current_price,
            "market_growth": growth,
            "market_time": f"{parts[30]} {parts[31]}",
            "symbol": symbol,
        }
