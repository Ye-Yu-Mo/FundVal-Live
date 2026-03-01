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

    def _get_all_accounts(self) -> List[Dict]:
        """
        获取所有账户列表

        Returns:
            list: 账户列表 [{'id': str, 'title': str, ...}, ...]

        Raises:
            Exception: 未登录
        """
        if not self._token:
            raise Exception('未登录养基宝，无法获取账户列表')

        try:
            data = self._request('GET', '/user_account')
            accounts = data.get('list', [])
            return accounts if isinstance(accounts, list) else []
        except Exception as e:
            logger.error(f'获取账户列表失败: {e}')
            raise

    def _fetch_all_holdings(self) -> List[Dict]:
        """
        获取所有账户的持仓列表（合并）

        Returns:
            list: 所有持仓列表

        Raises:
            Exception: 未登录
        """
        if not self._token:
            raise Exception('未登录养基宝，无法获取持仓数据')

        try:
            accounts = self._get_all_accounts()

            if not accounts:
                logger.warning('用户没有账户')
                return []

            all_holdings = []

            for account in accounts:
                account_id = account.get('id')
                if not account_id:
                    continue

                try:
                    data = self._request('GET', f'/fund_hold?account_id={account_id}')
                    holdings = data if isinstance(data, list) else []
                    all_holdings.extend(holdings)
                except Exception as e:
                    logger.warning(f'获取账户 {account_id} 持仓失败: {e}')
                    continue

            return all_holdings

        except Exception as e:
            logger.error(f'获取持仓列表失败: {e}')
            raise

    def _find_fund_in_holdings(self, fund_code: str) -> Optional[Dict]:
        """
        从所有账户持仓中查找指定基金

        Args:
            fund_code: 基金代码

        Returns:
            dict: 基金持仓数据，未找到返回 None
        """
        holdings = self._fetch_all_holdings()

        for holding in holdings:
            if holding.get('code') == fund_code:
                return holding

        return None

    # ─────────────────────────────────────────────
    # 基金数据获取
    # ─────────────────────────────────────────────

    def fetch_estimate(self, fund_code: str) -> Optional[Dict]:
        """
        获取基金估值（从持仓列表提取）

        Args:
            fund_code: 基金代码

        Returns:
            dict: {
                'fund_code': str,
                'fund_name': str,
                'estimate_nav': Decimal,
                'estimate_time': datetime,
                'estimate_growth': Decimal,
            }
            如果基金不在持仓中或无估值数据，返回 None
        """
        try:
            holding = self._find_fund_in_holdings(fund_code)

            if not holding:
                logger.warning(f'基金 {fund_code} 不在持仓中')
                return None

            nv_info = holding.get('nv_info', {})

            # 优先级：gsz（实时估算） > vgsz（预估） > zsgz（昨日估算）
            estimate_nav_str = nv_info.get('gsz') or nv_info.get('vgsz') or nv_info.get('zsgz')
            estimate_growth_str = nv_info.get('gszzl') or nv_info.get('vgszzl') or nv_info.get('zsgzzl')

            if not estimate_nav_str or not estimate_growth_str:
                logger.warning(f'基金 {fund_code} 无估值数据')
                return None

            return {
                'fund_code': fund_code,
                'fund_name': holding.get('short_name', ''),
                'estimate_nav': Decimal(str(estimate_nav_str)),
                'estimate_time': datetime.now(),
                'estimate_growth': Decimal(str(estimate_growth_str)),
            }

        except Exception as e:
            logger.error(f'获取基金 {fund_code} 估值失败: {e}')
            return None

    def fetch_realtime_nav(self, fund_code: str) -> Optional[Dict]:
        """
        获取实际净值（从持仓列表提取昨日净值）

        Args:
            fund_code: 基金代码

        Returns:
            dict: {
                'fund_code': str,
                'nav': Decimal,
                'nav_date': date,
            }
            如果基金不在持仓中或无净值数据，返回 None
        """
        try:
            holding = self._find_fund_in_holdings(fund_code)

            if not holding:
                logger.warning(f'基金 {fund_code} 不在持仓中')
                return None

            nv_info = holding.get('nv_info', {})

            nav_str = nv_info.get('dwjz')
            nav_date_str = nv_info.get('jzrq')

            if not nav_str or not nav_date_str:
                logger.warning(f'基金 {fund_code} 无净值数据')
                return None

            return {
                'fund_code': fund_code,
                'nav': Decimal(str(nav_str)),
                'nav_date': datetime.strptime(nav_date_str, '%Y-%m-%d').date(),
            }

        except Exception as e:
            logger.error(f'获取基金 {fund_code} 净值失败: {e}')
            return None

    def fetch_today_nav(self, fund_code: str) -> Optional[Dict]:
        """
        获取当日确认净值（从持仓列表提取，带日期校验）

        Args:
            fund_code: 基金代码

        Returns:
            dict: {
                'fund_code': str,
                'nav': Decimal,
                'nav_date': date,
            }
            如果基金不在持仓中、无净值数据或净值日期不是今天，返回 None
        """
        try:
            holding = self._find_fund_in_holdings(fund_code)

            if not holding:
                logger.warning(f'基金 {fund_code} 不在持仓中')
                return None

            nv_info = holding.get('nv_info', {})

            nav_str = nv_info.get('dwjz')
            nav_date_str = nv_info.get('jzrq')

            if not nav_str or not nav_date_str:
                logger.warning(f'基金 {fund_code} 无净值数据')
                return None

            nav_date = datetime.strptime(nav_date_str, '%Y-%m-%d').date()

            # 日期校验：只返回当日净值
            if nav_date != date.today():
                logger.info(f'基金 {fund_code} 净值日期 {nav_date} 不是今天，跳过')
                return None

            return {
                'fund_code': fund_code,
                'nav': Decimal(str(nav_str)),
                'nav_date': nav_date,
            }

        except Exception as e:
            logger.error(f'获取基金 {fund_code} 当日净值失败: {e}')
            return None

    def fetch_fund_list(self) -> list:
        """获取基金列表（暂未实现）"""
        raise NotImplementedError('养基宝基金列表获取功能暂未实现')

    # ─────────────────────────────────────────────
    # 账户与持仓导入
    # ─────────────────────────────────────────────

    def fetch_accounts(self) -> List[Dict]:
        """
        获取账户列表（标准化格式）

        Returns:
            list: [{'account_id': str, 'name': str}, ...]

        Raises:
            Exception: 未登录
        """
        if not self._token:
            raise Exception('未登录养基宝，无法获取账户列表')

        data = self._request('GET', '/user_account')
        accounts = data.get('list', [])

        return [
            {
                'account_id': acc.get('id', ''),
                'name': acc.get('title', ''),
            }
            for acc in accounts
            if acc.get('id') and acc.get('title')
        ]

    def fetch_holdings(self, account_id: str) -> List[Dict]:
        """
        获取指定账户的持仓列表（标准化格式）

        Args:
            account_id: 养基宝账户ID

        Returns:
            list: [{
                'fund_code': str,
                'fund_name': str,
                'share': Decimal,
                'nav': Decimal,       # 单位成本
                'amount': Decimal,    # 总金额
                'operation_date': date,
            }, ...]

        Raises:
            Exception: 未登录
        """
        if not self._token:
            raise Exception('未登录养基宝，无法获取持仓数据')

        data = self._request('GET', f'/fund_hold?account_id={account_id}')
        holdings = data if isinstance(data, list) else []

        result = []
        for h in holdings:
            fund_code = h.get('code', '')
            fund_name = h.get('short_name', '')
            hold_share = h.get('hold_share')
            hold_cost = h.get('hold_cost')
            money = h.get('money')
            hold_day = h.get('hold_day')

            if not fund_code or hold_share is None or hold_cost is None:
                continue

            try:
                operation_date = (
                    datetime.strptime(hold_day, '%Y-%m-%d').date()
                    if hold_day else date.today()
                )
                result.append({
                    'fund_code': fund_code,
                    'fund_name': fund_name,
                    'share': Decimal(str(hold_share)),
                    'nav': Decimal(str(hold_cost)),
                    'amount': Decimal(str(money)) if money else Decimal(str(hold_share)) * Decimal(str(hold_cost)),
                    'operation_date': operation_date,
                })
            except Exception as e:
                logger.warning(f'解析持仓数据失败 {fund_code}: {e}')
                continue

        return result

    def fetch_nav_history(self, fund_code: str, start_date: date = None, end_date: date = None) -> list:
        """获取历史净值（养基宝暂不支持）"""
        return []

