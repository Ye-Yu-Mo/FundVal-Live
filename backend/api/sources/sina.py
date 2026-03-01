import requests
import re
import logging
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, Dict, List

from .base import BaseEstimateSource

logger = logging.getLogger(__name__)

class SinaStockSource(BaseEstimateSource):
    """新浪财经股票/ETF实时行情"""
    
    BASE_URL = 'http://hq.sinajs.cn/list={symbol}'
    
    def get_source_name(self) -> str:
        return 'sina'

    def fetch_estimate(self, fund_code: str) -> Optional[Dict]:
        """实现 BaseEstimateSource 接口，虽然它主要用于场外估值，但我们也可以统一返回"""
        return self.fetch_market_quote(fund_code)

    def fetch_realtime_nav(self, fund_code: str) -> Optional[Dict]:
        return None

    def fetch_today_nav(self, fund_code: str) -> Optional[Dict]:
        """sina 源不支持确权净值查询，仅支持实时行情"""
        return None

    def get_qrcode(self) -> Optional[Dict]:
        """不需要 QR 登录"""
        return None

    def check_qrcode_state(self, qr_id: str) -> Optional[Dict]:
        """不需要扫码"""
        return None

    def logout(self):
        """无需登出"""
        pass

    def fetch_fund_list(self) -> list:
        return []

    def fetch_nav_history(self, fund_code: str, start_date=None, end_date=None) -> List[Dict]:
        return []

    def fetch_market_quote(self, fund_code: str) -> Optional[Dict]:
        """
        获取场内实时价格
        
        返回格式:
        var hq_str_sh511520="富国中债7-10年期国债ETF,115.630,115.635,115.660,115.680,115.580,115.660,115.670,1402200,162158860,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2026-02-27,15:00:00,00,0";
        """
        try:
            # 简单判断市场
            symbol_prefix = 'sh' if fund_code.startswith(('5', '6')) else 'sz'
            symbol = f'{symbol_prefix}{fund_code}'
                
            headers = {
                'Referer': 'http://finance.sina.com.cn'
            }
            url = self.BASE_URL.format(symbol=symbol)
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'
            
            text = response.text
            match = re.search(r'"(.*)"', text)
            if not match or not match.group(1):
                return None
                
            parts = match.group(1).split(',')
            if len(parts) < 32:
                return None
                
            current_price = Decimal(parts[3])
            prev_close = Decimal(parts[2])
            
            if current_price == 0:
                current_price = prev_close
                
            growth = Decimal(0)
            if prev_close > 0:
                growth = ((current_price - prev_close) / prev_close) * 100
                
            return {
                'fund_code': fund_code,
                'market_price': current_price,
                'market_growth': growth,
                'market_time': f"{parts[30]} {parts[31]}",
                'symbol': symbol
            }
        except Exception as e:
            logger.error(f"Sina fetch error for {fund_code}: {e}")
            return None
