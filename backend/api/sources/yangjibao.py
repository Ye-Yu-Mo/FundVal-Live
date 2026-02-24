"""
养基宝数据源实现
"""
import hashlib
import logging
import requests
from decimal import Decimal
from datetime import datetime, date
from typing import Dict, Optional, List

from .base import BaseEstimateSource

logger = logging.getLogger(__name__)


class YangJiBaoSource(BaseEstimateSource):
    """养基宝数据源"""

    BASE_URL = 'http://browser-plug-api.yangjibao.com'
    SECRET = 'YxmKSrQR4uoJ5lOoWIhcbd7SlUEh9OOc'

    def __init__(self):
        self._token = None

    def get_source_name(self) -> str:
        return 'yangjibao'

    def _generate_sign(self, path: str, timestamp: int) -> str:
        """
        生成 API 签名

        签名算法：md5(pathname + path + token + timestamp + SECRET)
        - pathname: API base 的路径部分（这里为空字符串）
        - path: 请求路径（不含查询参数）
        - token: 用户 token（未登录时为空字符串）
        - timestamp: 请求时间戳（秒）
        - SECRET: 固定密钥
        """
        pathname = ""
        token = self._token or ""

        # 如果 path 包含查询参数，签名时只用路径部分
        sign_path = path.split('?')[0] if '?' in path else path

        sign_str = pathname + sign_path + token + str(timestamp) + self.SECRET
        return hashlib.md5(sign_str.encode()).hexdigest()

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        """
        发送 HTTP 请求（带签名）

        Args:
            method: HTTP 方法（GET/POST/DELETE）
            path: 请求路径（如 /qr_code）
            **kwargs: requests 参数

        Returns:
            响应的 data 字段
        """
        timestamp = int(datetime.now().timestamp())
        url = self.BASE_URL + path

        headers = {
            'Request-Time': str(timestamp),
            'Request-Sign': self._generate_sign(path, timestamp),
            'Content-Type': 'application/json'
        }

        if self._token:
            headers['Authorization'] = self._token

        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()

        result = response.json()

        # 检查业务状态码
        if result.get('code') != 200:
            raise Exception(f"API 错误: {result.get('message', 'Unknown error')}")

        return result.get('data')

    # ─────────────────────────────────────────────
    # 二维码登录
    # ─────────────────────────────────────────────

    def get_qrcode(self) -> Dict:
        """
        获取登录二维码

        Returns:
            dict: {
                'qr_id': str,
                'qr_url': str,
            }
        """
        try:
            data = self._request('GET', '/qr_code')

            qr_id = data.get('id')
            qr_url = data.get('url')

            if not qr_id or not qr_url:
                raise Exception('二维码数据格式错误')

            return {
                'qr_id': qr_id,
                'qr_url': qr_url,
            }

        except Exception as e:
            logger.error(f'获取二维码失败: {e}')
            raise

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

        养基宝 API 返回的 state 是数字：
        - 1: 等待扫码
        - 2: 扫码成功（返回 token）
        - 3: 已过期
        """
        try:
            data = self._request('GET', f'/qr_code_state/{qr_id}')

            state_code = data.get('state')
            token = data.get('token')

            # 映射数字状态码到字符串
            state_map = {
                1: 'waiting',
                '1': 'waiting',
                2: 'confirmed',
                '2': 'confirmed',
                3: 'expired',
                '3': 'expired',
            }

            state = state_map.get(state_code, 'unknown')

            return {
                'state': state,
                'token': token if state == 'confirmed' else None,
            }

        except Exception as e:
            logger.error(f'检查二维码状态失败: {e}')
            raise

    def logout(self):
        """登出（清除 token）"""
        self._token = None

    # ─────────────────────────────────────────────
    # 基金数据获取（暂未实现）
    # ─────────────────────────────────────────────

    def fetch_estimate(self, fund_code: str) -> Optional[Dict]:
        """获取基金估值（暂未实现）"""
        raise NotImplementedError('养基宝估值获取功能暂未实现')

    def fetch_realtime_nav(self, fund_code: str) -> Optional[Dict]:
        """获取实际净值（暂未实现）"""
        raise NotImplementedError('养基宝净值获取功能暂未实现')

    def fetch_today_nav(self, fund_code: str) -> Optional[Dict]:
        """获取当日确认净值（暂未实现）"""
        raise NotImplementedError('养基宝当日净值获取功能暂未实现')

    def fetch_fund_list(self) -> list:
        """获取基金列表（暂未实现）"""
        raise NotImplementedError('养基宝基金列表获取功能暂未实现')
