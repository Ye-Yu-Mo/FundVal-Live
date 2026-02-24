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
        pass
