"""
雪球基金（蛋卷基金）数据源实现

API 域名: danjuanfunds.com（旧域名 danjuanapp.com 已 301 跳转）
无官方 API，通过前端 AJAX 接口获取数据。
无需认证。

核心能力：
- 历史净值（/djapi/fund/nav/history/{code}）
- 基金详情 + 评级排名（/djapi/fund/{code}）
- 不支持实时估值
"""

import logging
import requests
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import Dict, Optional, List

from .base import BaseEstimateSource

logger = logging.getLogger(__name__)


class DanjuanSource(BaseEstimateSource):
    """雪球基金（蛋卷）数据源 — 净值补充 + 评级排名"""

    BASE_URL = "https://danjuanfunds.com"
    NAV_HISTORY_URL = f"{BASE_URL}/djapi/fund/nav/history/{{code}}"
    FUND_DETAIL_URL = f"{BASE_URL}/djapi/fund/{{code}}"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    # ─────────────────────────────────────────────
    # 基础属性
    # ─────────────────────────────────────────────

    def get_source_name(self) -> str:
        return "danjuan"

    def get_login_type(self) -> str:
        return "none"

    # ─────────────────────────────────────────────
    # 估值（不支持）
    # ─────────────────────────────────────────────

    def fetch_estimate(self, fund_code: str) -> Optional[Dict]:
        """蛋卷基金没有公开的实时估值 API，始终返回 None"""
        return None

    # ─────────────────────────────────────────────
    # 历史净值
    # ─────────────────────────────────────────────

    def fetch_nav_history(
        self,
        fund_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict]:
        """
        从蛋卷获取基金历史净值

        API: GET /djapi/fund/nav/history/{code}?size=200&page=1

        响应字段：
        - date: 净值日期 (YYYY-MM-DD)
        - nav: 单位净值
        - percentage: 涨跌幅（%），"--" 表示无数据
        - value: 同 nav（不单独使用）

        注意：蛋卷不返回累计净值。
        """
        try:
            params = {"size": 200, "page": 1}
            url = self.NAV_HISTORY_URL.format(code=fund_code)
            response = requests.get(
                url, params=params, headers=self.HEADERS, timeout=15
            )
            response.raise_for_status()
            payload = response.json()

            if not payload or payload.get("result_code") != 0:
                logger.warning(
                    f"蛋卷历史净值 API 返回异常：{fund_code}, "
                    f"result_code={payload.get('result_code') if payload else 'None'}"
                )
                return []

            data = payload.get("data")
            if not data:
                return []

            items = data.get("items", [])
            if not items:
                return []

            result = []
            for item in items:
                date_str = item.get("date")
                nav_str = item.get("nav")

                if not date_str or not nav_str:
                    continue

                try:
                    nav_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    continue

                # 日期过滤
                if start_date and nav_date < start_date:
                    continue
                if end_date and nav_date > end_date:
                    continue

                # 单位净值
                try:
                    unit_nav = Decimal(str(nav_str))
                except InvalidOperation:
                    continue

                # 涨跌幅：处理 "--" 等非数字值
                daily_growth = None
                percentage_str = item.get("percentage")
                if percentage_str and percentage_str != "--":
                    try:
                        daily_growth = Decimal(str(percentage_str))
                    except InvalidOperation:
                        pass

                result.append(
                    {
                        "nav_date": nav_date,
                        "unit_nav": unit_nav,
                        "accumulated_nav": None,  # 蛋卷不返回累计净值
                        "daily_growth": daily_growth,
                    }
                )

            return result

        except requests.RequestException as e:
            logger.warning(
                f"蛋卷历史净值获取失败（网络）：{fund_code}, 错误：{e}"
            )
            return []
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(
                f"蛋卷历史净值获取失败（解析）：{fund_code}, 错误：{e}"
            )
            return []
        except Exception as e:
            logger.warning(
                f"蛋卷历史净值获取失败（未知）：{fund_code}, 错误：{e}"
            )
            return []

    # ─────────────────────────────────────────────
    # 最新净值 + 当日净值
    # ─────────────────────────────────────────────

    def fetch_realtime_nav(self, fund_code: str) -> Optional[Dict]:
        """
        获取最新净值（从历史净值取最新一条）

        Returns:
            {'fund_code': str, 'nav': Decimal, 'nav_date': date} 或 None
        """
        try:
            history = self.fetch_nav_history(fund_code)
            if not history:
                return None

            latest = history[0]  # fetch_nav_history 返回按日期降序
            return {
                "fund_code": fund_code,
                "nav": latest["unit_nav"],
                "nav_date": latest["nav_date"],
            }
        except Exception as e:
            logger.warning(f"蛋卷获取最新净值失败：{fund_code}, 错误：{e}")
            return None

    def fetch_today_nav(self, fund_code: str) -> Optional[Dict]:
        """
        获取当日确认净值（日期校验）

        Returns:
            dict 或 None（净值日期不是今天或无数据）
        """
        try:
            history = self.fetch_nav_history(fund_code)
            if not history:
                return None

            latest = history[0]
            if latest["nav_date"] != date.today():
                return None

            return {
                "fund_code": fund_code,
                "nav": latest["unit_nav"],
                "nav_date": latest["nav_date"],
            }
        except Exception as e:
            logger.warning(f"蛋卷获取当日净值失败：{fund_code}, 错误：{e}")
            return None

    # ─────────────────────────────────────────────
    # 基金详情 + 评级排名（扩展方法）
    # ─────────────────────────────────────────────

    def fetch_fund_detail(self, fund_code: str) -> Optional[Dict]:
        """
        获取基金详情，含评级排名数据

        API: GET /djapi/fund/{code}

        这是蛋卷的差异化能力 — 同类排名百分位数据（srank）。
        其他三个数据源都不提供。

        Returns:
            {
                'fund_code': str,
                'fund_name': str,
                'fund_type': str,          # 1=股票 2=债券 3=混合 5=指数 11=QDII
                'risk_level': str | None,
                'manager_name': str | None,
                'company_name': str | None,
                'latest_nav': Decimal | None,
                'nav_date': date | None,
                'period_returns': {         # 各阶段涨跌幅（%）
                    '1m': Decimal, '3m': Decimal, '6m': Decimal,
                    '1y': Decimal, '3y': Decimal, '5y': Decimal,
                },
                'peer_ranking': {           # 同类排名（如 "995/5347"）
                    '1m': str, '3m': str, '6m': str,
                    '1y': str, '3y': str, '5y': str,
                },
            }
            失败返回 None
        """
        try:
            url = self.FUND_DETAIL_URL.format(code=fund_code)
            response = requests.get(url, headers=self.HEADERS, timeout=15)
            response.raise_for_status()
            payload = response.json()

            if not payload or payload.get("result_code") != 0:
                logger.warning(
                    f"蛋卷基金详情 API 返回异常：{fund_code}, "
                    f"result_code={payload.get('result_code') if payload else 'None'}"
                )
                return None

            data = payload.get("data")
            if not data:
                return None

            derived = data.get("fund_derived") or {}

            # 阶段收益
            period_keys = {
                "1m": "nav_grl1m",
                "3m": "nav_grl3m",
                "6m": "nav_grl6m",
                "1y": "nav_grl1y",
                "3y": "nav_grl3y",
                "5y": "nav_grl5y",
            }
            period_returns = {}
            for key, field in period_keys.items():
                val = derived.get(field)
                if val is not None:
                    try:
                        period_returns[key] = Decimal(str(val))
                    except InvalidOperation:
                        pass

            # 同类排名
            rank_keys = {
                "1m": "srank_l1m",
                "3m": "srank_l3m",
                "6m": "srank_l6m",
                "1y": "srank_l1y",
                "3y": "srank_l3y",
                "5y": "srank_l5y",
            }
            peer_ranking = {}
            for key, field in rank_keys.items():
                val = derived.get(field)
                if val:
                    peer_ranking[key] = str(val)

            # 最新净值
            latest_nav = None
            nav_date = None
            unit_nav_str = derived.get("unit_nav")
            end_date_str = derived.get("end_date")
            if unit_nav_str:
                try:
                    latest_nav = Decimal(str(unit_nav_str))
                except InvalidOperation:
                    pass
            if end_date_str:
                try:
                    nav_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    pass

            return {
                "fund_code": data.get("fd_code", fund_code),
                "fund_name": data.get("fd_name", ""),
                "fund_type": data.get("fd_type"),
                "risk_level": data.get("risk_level"),
                "manager_name": data.get("manager_name"),
                "company_name": data.get("keeper_name"),
                "latest_nav": latest_nav,
                "nav_date": nav_date,
                "period_returns": period_returns,
                "peer_ranking": peer_ranking,
            }

        except requests.RequestException as e:
            logger.warning(f"蛋卷基金详情获取失败（网络）：{fund_code}, 错误：{e}")
            return None
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"蛋卷基金详情获取失败（解析）：{fund_code}, 错误：{e}")
            return None
        except Exception as e:
            logger.warning(f"蛋卷基金详情获取失败（未知）：{fund_code}, 错误：{e}")
            return None

    # ─────────────────────────────────────────────
    # 其他必须实现的抽象方法
    # ─────────────────────────────────────────────

    def fetch_fund_list(self) -> list:
        """蛋卷不提供全量基金列表 API"""
        raise NotImplementedError(
            "蛋卷基金不支持全量基金列表查询"
        )

    def fetch_index_holdings(self, fund_code: str) -> list:
        """蛋卷没有成分股接口，委托给东方财富"""
        from .eastmoney import EastMoneySource

        return EastMoneySource().fetch_index_holdings(fund_code)
