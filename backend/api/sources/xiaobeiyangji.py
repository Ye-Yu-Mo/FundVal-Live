"""
小倍养基数据源实现
"""
import logging
import math
import requests
from decimal import Decimal
from datetime import datetime, date
from typing import Dict, Optional, List

from .base import BaseEstimateSource

logger = logging.getLogger(__name__)


class XiaoBeiYangJiSource(BaseEstimateSource):
    """小倍养基数据源（手机号登录）"""

    BASE_URL = 'https://api.xiaobeiyangji.com'
    VERSION = '3.5.7.0'

    def __init__(self):
        self._token = None
        self._union_id = None

    # ─────────────────────────────────────────────
    # 基础属性
    # ─────────────────────────────────────────────

    def get_source_name(self) -> str:
        return 'xiaobeiyangji'

    def get_login_type(self) -> str:
        return 'phone'

    def get_qrcode(self):
        return None

    def check_qrcode_state(self, qr_id: str):
        return None

    # ─────────────────────────────────────────────
    # 内部工具
    # ─────────────────────────────────────────────

    def _common_body(self) -> Dict:
        return {
            'unionId': self._union_id,
            'version': self.VERSION,
            'clientType': 'APP',
        }

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        url = self.BASE_URL + path
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._token or ""}',
        }
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        result = response.json()
        if result.get('code') != 200:
            raise Exception(f"API 错误: {result.get('msg', 'Unknown error')}")
        return result.get('data')

    def _require_login(self):
        if not self._token:
            raise Exception('未登录小倍养基，请先登录')

    # ─────────────────────────────────────────────
    # 手机号登录
    # ─────────────────────────────────────────────

    def send_sms(self, phone: str) -> None:
        """发送短信验证码"""
        url = self.BASE_URL + '/yangji-api/api/send-sms'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ',
        }
        body = {
            'phoneNumber': phone,
            'isBind': False,
            'version': self.VERSION,
            'clientType': 'APP',
        }
        response = requests.request('POST', url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get('code') != 200:
            raise Exception(f"发送短信失败: {result.get('msg', 'Unknown error')}")

    def verify_phone(self, phone: str, code: str) -> dict:
        """手机号 + 验证码登录"""
        url = self.BASE_URL + '/yangji-api/api/login/phone'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ',
        }
        body = {
            'phone': phone,
            'code': code,
            'clientType': 'PHONE',
            'version': self.VERSION,
        }
        response = requests.request('POST', url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get('code') != 200:
            raise Exception(f"登录失败: {result.get('msg', 'Unknown error')}")

        data = result['data']
        self._token = data['accessToken']
        self._union_id = data['user']['unionId']
        return {'token': self._token, 'union_id': self._union_id}

    def logout(self):
        self._token = None
        self._union_id = None

    # ─────────────────────────────────────────────
    # 估值
    # ─────────────────────────────────────────────

    def _get_optional_change_nav(self, fund_codes: List[str]) -> List[Dict]:
        """批量获取估值数据"""
        today = date.today()
        yesterday = today.replace(day=today.day - 1)  # 简单减一天，实际用 timedelta
        from datetime import timedelta
        yesterday = today - timedelta(days=1)

        body = {
            'dataResources': '4',
            'dataSourceSwitch': True,
            'valuationDate': today.isoformat(),
            'navDate': yesterday.isoformat(),
            'isTD': True,
            'codeArr': fund_codes,
            **self._common_body(),
        }
        return self._request('POST', '/yangji-api/api/get-optional-change-nav', json=body)

    def _get_fund_detail(self, fund_code: str) -> Dict:
        """获取基金详情"""
        body = {
            'code': fund_code,
            'accountId': 0,
            'dataResources': '4',
            'dataSourceSwitch': True,
            'isHasPosition': True,
            'fromType': 'home',
            **self._common_body(),
        }
        return self._request('POST', '/yangji-api/api/get-fund-detail-v310', json=body)

    def fetch_estimate(self, fund_code: str) -> Optional[Dict]:
        self._require_login()
        try:
            nav_list = self._get_optional_change_nav([fund_code])
            if not nav_list:
                return None

            item = next((x for x in nav_list if x.get('code') == fund_code), None)
            if not item:
                return None

            valuation = item.get('valuation', 0)
            valuation_y = item.get('valuationY', 0)
            nav = item.get('nav', 0)
            nav_y = item.get('navY', 0)

            # 非交易时段 valuation=0，fallback 到昨日净值
            if valuation and valuation != 0:
                estimate_nav = Decimal(str(valuation))
                estimate_growth = Decimal(str(valuation_y)) * 100
            else:
                estimate_nav = Decimal(str(nav))
                estimate_growth = Decimal(str(nav_y)) * 100

            # 获取基金名称
            detail = self._get_fund_detail(fund_code)
            fund_name = detail.get('name', '') if detail else ''

            return {
                'fund_code': fund_code,
                'fund_name': fund_name,
                'estimate_nav': estimate_nav,
                'estimate_time': datetime.now(),
                'estimate_growth': estimate_growth,
            }
        except Exception as e:
            logger.error(f'获取基金 {fund_code} 估值失败: {e}')
            return None

    def fetch_realtime_nav(self, fund_code: str) -> Optional[Dict]:
        self._require_login()
        try:
            detail = self._get_fund_detail(fund_code)
            if not detail:
                return None

            nav_str = detail.get('nav')
            nav_date_str = detail.get('latestPriceDate')
            if not nav_str or not nav_date_str:
                return None

            return {
                'fund_code': fund_code,
                'nav': Decimal(str(nav_str)),
                'nav_date': date.fromisoformat(nav_date_str),
            }
        except Exception as e:
            logger.error(f'获取基金 {fund_code} 净值失败: {e}')
            return None

    def fetch_today_nav(self, fund_code: str) -> Optional[Dict]:
        self._require_login()
        result = self.fetch_realtime_nav(fund_code)
        if result and result['nav_date'] == date.today():
            return result
        return None

    # ─────────────────────────────────────────────
    # 历史净值
    # ─────────────────────────────────────────────

    def fetch_nav_history(
        self,
        fund_code: str,
        start_date: date = None,
        end_date: date = None,
    ) -> List[Dict]:
        self._require_login()
        try:
            # 计算 range（月数）
            if start_date and end_date:
                months = math.ceil((end_date - start_date).days / 30)
                range_months = min(max(months, 1), 12)
            else:
                range_months = 3

            body = {
                'code': fund_code,
                'type': 'normal',
                'range': range_months,
                **self._common_body(),
            }
            data = self._request('POST', '/yangji-api/api/get-trajectory-v310', json=body)
            if not data:
                return []

            records = data.get('data', [])
            result = []
            for r in records:
                nav_date = date.fromisoformat(r['d'])

                # 日期过滤
                if start_date and nav_date < start_date:
                    continue
                if end_date and nav_date > end_date:
                    continue

                result.append({
                    'fund_code': fund_code,
                    'nav_date': nav_date,
                    'nav': Decimal(str(r['n'])),
                    'growth': Decimal(str(r['y'])) * 100,
                })

            return result
        except Exception as e:
            logger.error(f'获取基金 {fund_code} 历史净值失败: {e}')
            return []

    # ─────────────────────────────────────────────
    # 持仓导入
    # ─────────────────────────────────────────────

    def fetch_holdings(self) -> List[Dict]:
        self._require_login()
        try:
            data = self._request('POST', '/yangji-api/api/get-hold-list', json=self._common_body())
            items = data.get('list', []) if data else []

            # 过滤 money=0
            valid_items = [x for x in items if x.get('money')]
            if not valid_items:
                return []

            # 批量获取净值用于推算份额
            codes = [x['code'] for x in valid_items]
            nav_list = self._get_optional_change_nav(codes)
            nav_map = {x['code']: Decimal(str(x['nav'])) for x in (nav_list or []) if x.get('nav')}

            result = []
            for item in valid_items:
                fund_code = item['code']
                money = Decimal(str(item['money']))
                earnings = Decimal(str(item.get('earnings', 0)))
                fund_name = item.get('data', {}).get('name', '')
                operation_date = date.fromisoformat(item['headDate'])

                nav = nav_map.get(fund_code, Decimal('0'))
                if nav and nav != 0:
                    share = (money / nav).quantize(Decimal('0.01'))
                    unit_cost = nav
                else:
                    logger.warning(f'基金 {fund_code} 无净值数据，份额设为 0')
                    share = Decimal('0')
                    unit_cost = Decimal('0')

                result.append({
                    'fund_code': fund_code,
                    'fund_name': fund_name,
                    'share': share,
                    'nav': unit_cost,
                    'amount': money,
                    'earnings': earnings,
                    'operation_date': operation_date,
                })

            return result
        except Exception as e:
            logger.error(f'获取持仓列表失败: {e}')
            raise

    # ─────────────────────────────────────────────
    # 其他必须实现的抽象方法
    # ─────────────────────────────────────────────

    def fetch_fund_list(self) -> list:
        raise NotImplementedError('小倍养基不支持基金列表查询')

    def fetch_index_holdings(self, fund_code: str) -> list:
        from .eastmoney import EastMoneySource
        return EastMoneySource().fetch_index_holdings(fund_code)
