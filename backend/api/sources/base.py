"""
数据源抽象基类
"""
from abc import ABC, abstractmethod
from typing import Dict
from decimal import Decimal
from datetime import datetime, date


class BaseEstimateSource(ABC):
    """估值数据源抽象基类"""

    @abstractmethod
    def get_source_name(self) -> str:
        """
        数据源名称

        Returns:
            str: 数据源唯一标识
        """
        pass

    @abstractmethod
    def fetch_estimate(self, fund_code: str) -> Dict:
        """
        获取基金估值

        Args:
            fund_code: 基金代码

        Returns:
            dict: {
                'fund_code': str,
                'fund_name': str,
                'estimate_nav': Decimal,
                'estimate_time': datetime,
                'estimate_growth': Decimal,  # 估算涨幅
            }
        """
        pass

    @abstractmethod
    def fetch_realtime_nav(self, fund_code: str) -> Dict:
        """
        获取实际净值（用于计算准确率）

        Args:
            fund_code: 基金代码

        Returns:
            dict: {
                'fund_code': str,
                'nav': Decimal,
                'nav_date': date,
            }
        """
        pass

    @abstractmethod
    def fetch_today_nav(self, fund_code: str) -> Dict:
        """
        获取当日确认净值（从历史净值接口取最新一条）

        Args:
            fund_code: 基金代码

        Returns:
            dict: {
                'fund_code': str,
                'nav': Decimal,
                'nav_date': date,
            }
            如果获取失败或数据为空，返回 None
        """
        pass

    @abstractmethod
    def get_qrcode(self) -> Dict:
        """
        获取登录二维码（用于需要登录的数据源）

        Returns:
            dict: {
                'qr_id': str,
                'qr_url': str,
            }
            如果数据源不支持二维码登录，返回 None
        """
        pass

    @abstractmethod
    def check_qrcode_state(self, qr_id: str) -> Dict:
        """
        检查二维码扫码状态

        Args:
            qr_id: 二维码ID

        Returns:
            dict: {
                'state': str,  # waiting/scanned/confirmed/expired
                'token': str,  # 仅 state=confirmed 时有值
            }
        """
        pass

    @abstractmethod
    def logout(self):
        """
        登出（清除 token）
        """
        pass

    @abstractmethod
    def fetch_fund_list(self) -> list:
        """
        获取基金列表

        Returns:
            list: [{
                'fund_code': str,
                'fund_name': str,
                'fund_type': str,
            }, ...]
        """
    @abstractmethod
    def fetch_nav_history(self, fund_code: str, start_date: date = None, end_date: date = None) -> list:
        """获取历史净值"""
        pass

    def fetch_market_quote(self, fund_code: str) -> Dict:
        """
        获取场内实时价格（非必选实现）
        
        Returns:
            dict: {
                'fund_code': str,
                'market_price': Decimal,
                'market_growth': Decimal,
                'market_time': datetime/str
            }
        """
        return None
