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

    def get_login_type(self) -> str:
        """
        数据源的登录类型

        Returns:
            'none'   — 不需要登录（如东方财富）
            'qrcode' — 二维码扫码登录（如养基宝）
            'phone'  — 手机号 + 短信验证码登录（如小倍养基）
        """
        return 'none'

    def get_qrcode(self) -> Dict:
        """
        获取登录二维码（login_type='qrcode' 的数据源实现）

        Returns:
            dict: {'qr_id': str, 'qr_url': str}
            不支持二维码登录的数据源返回 None
        """
        return None

    def check_qrcode_state(self, qr_id: str) -> Dict:
        """
        检查二维码扫码状态（login_type='qrcode' 的数据源实现）

        Returns:
            dict: {'state': str, 'token': str}
            不支持二维码登录的数据源返回 None
        """
        return None

    def logout(self):
        """登出（清除 token），不需要登录的数据源无操作"""
        pass

    def send_sms(self, phone: str) -> None:
        """
        发送短信验证码（login_type='phone' 的数据源实现）

        Args:
            phone: 手机号

        Raises:
            NotImplementedError: 数据源不支持手机号登录
        """
        raise NotImplementedError(f'{self.get_source_name()} 不支持手机号登录')

    def verify_phone(self, phone: str, code: str) -> dict:
        """
        手机号 + 验证码登录（login_type='phone' 的数据源实现）

        Args:
            phone: 手机号
            code:  短信验证码

        Returns:
            dict: {'token': str, 'union_id': str}

        Raises:
            NotImplementedError: 数据源不支持手机号登录
        """
        raise NotImplementedError(f'{self.get_source_name()} 不支持手机号登录')

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

    def fetch_index_holdings(self, fund_code: str) -> list:
        """
        获取基金持仓成分股（非必选实现）

        Returns:
            list of dict: [
                {
                    'stock_code': str,
                    'stock_name': str,
                    'weight': Decimal,
                    'price': Decimal,
                    'change_percent': Decimal,
                }
            ]
        """
        return []
