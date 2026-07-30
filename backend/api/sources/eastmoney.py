"""
天天基金数据源实现
"""

import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal

import requests

from .base import BaseEstimateSource

logger = logging.getLogger(__name__)


class EastMoneySource(BaseEstimateSource):
    """天天基金数据源"""

    # DEPRECATED: 2026-07-29 起 fundgz.1234567.com.cn 返回 HTML 而非 JSONP，
    # 估值接口已不可用。保留常量以备后续恢复。
    ESTIMATE_URL = "http://fundgz.1234567.com.cn/js/{code}.js"
    # DEPRECATED: 2026-07-29 起 fund.eastmoney.com/js/fundcode_search.js 返回空响应，
    # 基金列表同步接口已不可用。保留常量以备后续恢复。
    FUND_LIST_URL = "http://fund.eastmoney.com/js/fundcode_search.js"
    # DEPRECATED: 2026-07-29 起 fund.eastmoney.com/pingzhongdata 返回空响应，
    # 历史净值 Web API 已不可用。保留常量以备后续恢复。
    HISTORY_URL = "http://fund.eastmoney.com/pingzhongdata/{code}.js"
    FUND_HOLDINGS_URL = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNInverstPosition"
    STOCK_QUOTE_URL = "http://push2.eastmoney.com/api/qt/ulist.np/get"

    # 移动端 API（作为 Web API 的 fallback，提升净值覆盖率）
    MOBILE_NAV_HISTORY_URL = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList"
    MOBILE_REALTIME_NAV_URL = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo"

    MOBILE_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_3 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
            "eastmoney/6.2.8"
        ),
    }

    def get_source_name(self) -> str:
        return "eastmoney"

    def __init__(self):
        super().__init__()
        # M2: 估值引擎（lazy init，避免循环导入）
        self._estimate_engine = None
        # M3: 穿透估算引擎（lazy init）
        self._penetration_engine = None

    def _get_estimate_engine(self):
        """懒加载 akshare 估值引擎"""
        if self._estimate_engine is None:
            from .akshare_estimate import AkshareEstimateEngine

            self._estimate_engine = AkshareEstimateEngine()
        return self._estimate_engine

    def _get_penetration_engine(self):
        """懒加载穿透估算引擎（M3）"""
        if self._penetration_engine is None:
            from .penetration_engine import PenetrationEngine

            self._penetration_engine = PenetrationEngine()
        return self._penetration_engine

    def is_available(self) -> bool:
        """
        检查东方财富 Mobile API 连通性

        M1: 使用 FundMNFInfo 端点做轻量健康检查。
        查询 000001（华夏成长混合），只判断能否获取到数据。
        """
        try:
            response = requests.get(
                self.MOBILE_REALTIME_NAV_URL,
                params={
                    "Fcodes": "000001",
                    "pageIndex": "1",
                    "pageSize": "1",
                    "Sort": "",
                    "SortColumn": "",
                    "IsShowSE": "false",
                    "P": "F",
                    "deviceid": "3EA024C2-7F22-408B-95E4-383D38160FB3",
                    "plat": "Iphone",
                    "product": "EFund",
                    "version": "6.2.8",
                },
                headers=self.MOBILE_HEADERS,
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            if data and data.get("Datas"):
                return True
            return False
        except Exception:
            return False

    def fetch_estimate(self, fund_code: str) -> dict | None:
        """
        获取基金实时估值

        M3 fallback 链: akshare → 穿透估算 → None (unavailable)
        - akshare 是第一优先级（官方估值源）
        - 穿透估算是第二优先级（akshare 失败时兜底）
        - 都失败返回 None → API 返回 unavailable: true

        原 fundgz JSONP 解析代码保留在下方注释中，以备将来参考。
        """
        fund_type = None  # 穿透估算需要类型判断

        # 1. 尝试 akshare（主估值源）
        try:
            engine = self._get_estimate_engine()
            result = engine.get_estimate(fund_code)
            if result is not None:
                result["estimate_source"] = "akshare"
                return result
        except Exception as e:
            logger.debug(f"akshare 估值失败 ({fund_code}): {e}")

        # 2. 尝试穿透估算（M3 新增）
        try:
            # 查询基金类型用于穿透估算的适用性判断
            if fund_type is None:
                try:
                    from api.models import Fund

                    fund = Fund.objects.filter(fund_code=fund_code).first()
                    if fund:
                        fund_type = fund.fund_type
                except Exception:
                    pass

            pen_engine = self._get_penetration_engine()
            result, reason = pen_engine.estimate(fund_code, fund_type)
            if result is not None:
                result["estimate_source"] = "penetration"
                return result
            if reason == "not_applicable":
                logger.debug(f"穿透估算法不适用于 {fund_code}")
            elif reason == "no_holdings":
                logger.debug(f"{fund_code} 无持仓数据")
        except Exception as e:
            logger.warning(f"穿透估算失败 ({fund_code}): {e}")

        return None  # → API 返回 unavailable

        # ── 以下为原 fundgz JSONP 估值解析逻辑，保留以备 API 恢复 ──
        # try:
        #     url = self.ESTIMATE_URL.format(code=fund_code)
        #     response = requests.get(url, timeout=10)
        #     response.raise_for_status()
        #
        #     text = response.text
        #     match = re.search(r"jsonpgz\((.*)\);?", text)
        #     if not match:
        #         logger.warning(f"无法解析估值数据：{fund_code}，响应格式不正确")
        #         return None
        #
        #     json_str = match.group(1)
        #     data = json.loads(json_str)
        #
        #     required_fields = ["fundcode", "name", "gsz", "gszzl", "gztime"]
        #     for field in required_fields:
        #         if field not in data:
        #             logger.warning(f"估值数据缺少字段 {field}：{fund_code}")
        #             return None
        #
        #     estimate_nav = Decimal(data["gsz"])
        #     estimate_growth = Decimal(data["gszzl"])
        #     estimate_time = datetime.strptime(data["gztime"], "%Y-%m-%d %H:%M")
        #
        #     # QDII / 净值延迟: 如果 fundgz 的基准净值日期过期，
        #     # 用 Mobile API 取最新净值重新计算涨跌幅
        #     jzrq_str = data.get("jzrq")
        #     if jzrq_str:
        #         try:
        #             jzrq_date = datetime.strptime(jzrq_str, "%Y-%m-%d").date()
        #             latest = self._fetch_realtime_nav_mobile(fund_code)
        #             if latest and latest["nav_date"] > jzrq_date:
        #                 old_nav = latest["nav"]
        #                 if old_nav and old_nav > 0:
        #                     estimate_growth = (
        #                         (estimate_nav - old_nav) / old_nav * 100
        #                     )
        #                     logger.info(
        #                         f"QDII 净值校正: {fund_code} "
        #                         f"jzrq={jzrq_date}→{latest['nav_date']} "
        #                         f"growth={data['gszzl']}%→{estimate_growth:.2f}%"
        #                     )
        #         except (ValueError, TypeError):
        #             pass
        #
        #     return {
        #         "fund_code": data["fundcode"],
        #         "fund_name": data["name"],
        #         "estimate_nav": estimate_nav,
        #         "estimate_growth": estimate_growth,
        #         "estimate_time": estimate_time,
        #     }
        #
        # except requests.RequestException as e:
        #     logger.error(f"获取估值失败（网络错误）：{fund_code}, 错误：{e}")
        #     return None
        # except json.JSONDecodeError as e:
        #     logger.error(f"获取估值失败（JSON 解析错误）：{fund_code}, 错误：{e}")
        #     return None
        # except (KeyError, ValueError, TypeError) as e:
        #     logger.error(f"获取估值失败（数据格式错误）：{fund_code}, 错误：{e}")
        #     return None
        # except Exception as e:
        #     logger.error(f"获取估值失败（未知错误）：{fund_code}, 错误：{e}")
        #     return None

    def fetch_realtime_nav(self, fund_code: str) -> dict | None:
        """
        从天天基金获取实际净值

        M1 (2026-07-29): Web API (fundgz JSONP) 已失效，直接使用移动端 API。
        原 Web API 的 dwjz/jzrq 解析逻辑保留在下方注释中，以备恢复。
        """
        # Web API (fundgz.1234567.com.cn) 于 2026-07-29 起返回 HTML 而非 JSONP，
        # dwjz/jzrq 字段不可解析。直接使用 Mobile API。
        # 如需恢复 Web API 主路径:
        #   取消下方注释代码，将 self._fetch_realtime_nav_mobile() 移至 fallback 位置。
        #
        # try:
        #     url = self.ESTIMATE_URL.format(code=fund_code)
        #     response = requests.get(url, timeout=10)
        #     response.raise_for_status()
        #     text = response.text
        #     match = re.search(r"jsonpgz\((.*)\);?", text)
        #     if match:
        #         json_str = match.group(1)
        #         data = json.loads(json_str)
        #         if all(k in data for k in ["fundcode", "dwjz", "jzrq"]):
        #             return {
        #                 "fund_code": data["fundcode"],
        #                 "nav": Decimal(data["dwjz"]),
        #                 "nav_date": datetime.strptime(
        #                     data["jzrq"], "%Y-%m-%d"
        #                 ).date(),
        #             }
        # except Exception:
        #     pass
        # return self._fetch_realtime_nav_mobile(fund_code)
        return self._fetch_realtime_nav_mobile(fund_code)

    def _fetch_realtime_nav_mobile(self, fund_code: str) -> dict | None:
        """
        从东方财富移动端 API 获取最新净值（作为 Web API 的 fallback）

        使用 FundMNFInfo 批量接口，取单只基金的最新净值。

        Returns:
            dict: {'fund_code': str, 'nav': Decimal, 'nav_date': date}
            失败返回 None
        """
        try:
            params = {
                "Fcodes": fund_code,
                "pageIndex": "1",
                "pageSize": "1",
                "Sort": "",
                "SortColumn": "",
                "IsShowSE": "false",
                "P": "F",
                "deviceid": "3EA024C2-7F22-408B-95E4-383D38160FB3",
                "plat": "Iphone",
                "product": "EFund",
                "version": "6.2.8",
            }
            response = requests.get(
                self.MOBILE_REALTIME_NAV_URL,
                params=params,
                headers=self.MOBILE_HEADERS,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            if not data or not data.get("Datas"):
                logger.warning(f"移动端净值查询无数据（FundMNFInfo）：{fund_code}")
                return None

            items = data["Datas"]
            if not items:
                return None

            item = items[0]
            nav_str = item.get("ACCNAV")
            date_str = item.get("PDATE")

            if not nav_str or not date_str:
                logger.warning(f"移动端净值数据缺少字段（ACCNAV/PDATE）：{fund_code}")
                return None

            return {
                "fund_code": fund_code,
                "nav": Decimal(str(nav_str)),
                "nav_date": datetime.strptime(date_str, "%Y-%m-%d").date(),
            }

        except requests.RequestException as e:
            logger.warning(f"移动端净值查询失败（网络）：{fund_code}, 错误：{e}")
            return None
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning(f"移动端净值查询失败（解析）：{fund_code}, 错误：{e}")
            return None
        except Exception as e:
            logger.warning(f"移动端净值查询失败（未知）：{fund_code}, 错误：{e}")
            return None

    def fetch_fund_list(self) -> list:
        """
        从天天基金获取基金列表

        M2 (2026-07-29): 通过 ak.fund_name_em() 获取全量基金列表。
        M1 中 fundcode_search.js 已失效，此处恢复功能。

        原 Web API (fundcode_search.js) 解析代码保留在下方注释中。

        ak.fund_name_em() 返回 DataFrame，列包括:
        - 基金代码, 基金简称, 基金类型, 拼音全称, 拼音缩写
        """
        try:
            import akshare as ak

            df = ak.fund_name_em()
            if df is None or df.empty:
                logger.warning("ak.fund_name_em() 返回空数据")
                return []

            # 列名兼容性检查
            code_col = None
            name_col = None
            type_col = None
            for col in df.columns:
                if "代码" in str(col):
                    code_col = col
                elif "简称" in str(col) or "名称" in str(col):
                    name_col = col
                elif "类型" in str(col):
                    type_col = col

            if code_col is None:
                logger.warning("ak.fund_name_em() 缺少基金代码列")
                return []

            funds = []
            for _, row in df.iterrows():
                try:
                    fund_code = str(row[code_col]).zfill(6)
                    fund_name = str(row[name_col]) if name_col and row.get(name_col) else ""
                    fund_type = str(row[type_col]) if type_col and row.get(type_col) else ""
                    funds.append(
                        {
                            "fund_code": fund_code,
                            "fund_name": fund_name,
                            "fund_type": fund_type,
                        }
                    )
                except Exception:
                    continue

            return funds

        except Exception as e:
            logger.error(f"akshare 获取基金列表失败: {e}")
            return []

        # ── 以下为原 fundcode_search.js 解析逻辑，保留以备 API 恢复 ──
        # response = requests.get(self.FUND_LIST_URL, timeout=30)
        # response.raise_for_status()
        #
        # text = response.text
        # json_str = re.search(r"var r = (\[.*\]);?", text).group(1)
        # data = json.loads(json_str)
        #
        # funds = []
        # for item in data:
        #     funds.append(
        #         {
        #             "fund_code": item[0],
        #             "fund_name": item[2],
        #             "fund_type": item[3],
        #         }
        #     )
        # return funds

    def fetch_today_nav(self, fund_code: str) -> dict | None:
        """
        获取当日确认净值（从历史净值接口取最新一条）

        使用 pingzhongdata 接口获取历史净值，取最后一条记录作为当日净值。
        当日净值通常在 20:00-22:00 公布后出现在历史数据中。

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
        try:
            # 调用 fetch_nav_history 获取历史净值（不限制日期范围）
            history = self.fetch_nav_history(fund_code)

            if not history:
                logger.warning(f"获取当日净值失败：{fund_code}，历史净值数据为空")
                return None

            # 取最后一条记录（最新净值）
            latest = history[-1]

            return {
                "fund_code": fund_code,
                "nav": latest["unit_nav"],
                "nav_date": latest["nav_date"],
            }

        except Exception as e:
            logger.error(f"获取当日净值失败：{fund_code}, 错误：{e}")
            return None

    def get_login_type(self) -> str:
        return "none"

    def fetch_nav_history(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """
        获取基金历史净值

        M1 (2026-07-29): Web API (pingzhongdata JSONP) 已失效，直接使用移动端 API。

        Args:
            fund_code: 基金代码
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            历史净值列表
        """
        # Web API (pingzhongdata/{code}.js) 于 2026-07-29 起返回空响应，已不可用。
        # 直接使用 Mobile API，不再尝试 Web API fallback 链。
        # 如需恢复 Web API: 取消下面两行注释，将 Mobile 调用移至 fallback 位置。
        # result = self._try_web_nav_history(fund_code, start_date, end_date)
        # if not result:
        #     result = self._fetch_nav_history_mobile(fund_code, start_date, end_date)
        return self._fetch_nav_history_mobile(fund_code, start_date, end_date)

    def _try_web_nav_history(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """Web API 历史净值获取（内部方法）"""
        try:
            url = self.HISTORY_URL.format(code=fund_code)
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            text = response.text

            # 解析单位净值数据
            unit_nav_match = re.search(r"var Data_netWorthTrend = (\[.*?\]);", text, re.DOTALL)
            if not unit_nav_match:
                logger.warning(f"无法解析历史净值数据：{fund_code}")
                return []

            try:
                unit_nav_data = json.loads(unit_nav_match.group(1))
                logger.info(
                    f"解析单位净值数据成功：{fund_code}, 数据类型：{type(unit_nav_data)}, 长度：{len(unit_nav_data) if isinstance(unit_nav_data, list) else 'N/A'}"
                )
                if unit_nav_data and isinstance(unit_nav_data, list):
                    logger.info(
                        f"第一个元素类型：{type(unit_nav_data[0])}, 内容：{unit_nav_data[0]}"
                    )
            except Exception as e:
                logger.error(f"解析单位净值数据失败：{fund_code}, 错误：{e}")
                return []

            # 调试：检查数据类型
            if not isinstance(unit_nav_data, list):
                logger.error(
                    f"单位净值数据不是列表：{fund_code}, 类型：{type(unit_nav_data)}, 数据：{unit_nav_data}"
                )
                return []

            if unit_nav_data and not isinstance(unit_nav_data[0], dict):
                logger.error(
                    f"单位净值数据元素不是字典：{fund_code}, 类型：{type(unit_nav_data[0])}, 数据：{unit_nav_data[0]}"
                )
                return []

            # 解析累计净值数据（可选）
            acc_nav_match = re.search(r"var Data_ACWorthTrend = (\[.*?\]);", text, re.DOTALL)
            acc_nav_data = []
            if acc_nav_match:
                try:
                    acc_nav_data = json.loads(acc_nav_match.group(1))
                except json.JSONDecodeError:
                    pass

            # 构建累计净值字典（按时间戳索引）
            # Data_ACWorthTrend 可能是字典数组或二维数组
            acc_nav_dict = {}
            for item in acc_nav_data:
                if isinstance(item, dict):
                    # 字典格式：{"x": timestamp, "y": value}
                    acc_nav_dict[item["x"]] = item
                elif isinstance(item, list) and len(item) >= 2:
                    # 二维数组格式：[timestamp, value]
                    acc_nav_dict[item[0]] = {"x": item[0], "y": item[1]}

            # 转换数据格式
            result = []
            for item in unit_nav_data:
                # 验证必需字段
                if "x" not in item or "y" not in item:
                    continue

                # 转换时间戳（毫秒 -> 秒）
                timestamp = item["x"] / 1000
                nav_date = datetime.fromtimestamp(timestamp).date()

                # 日期过滤
                if start_date and nav_date < start_date:
                    continue
                if end_date and nav_date > end_date:
                    continue

                # 获取累计净值
                acc_nav_item = acc_nav_dict.get(item["x"])
                accumulated_nav = None
                if acc_nav_item and "y" in acc_nav_item:
                    accumulated_nav = Decimal(str(acc_nav_item["y"]))

                result.append(
                    {
                        "nav_date": nav_date,
                        "unit_nav": Decimal(str(item["y"])),
                        "accumulated_nav": accumulated_nav,
                        "daily_growth": (
                            Decimal(str(item["equityReturn"]))
                            if item.get("equityReturn") is not None
                            else None
                        ),
                    }
                )

            return result

        except requests.RequestException as e:
            logger.error(f"获取历史净值失败（网络错误）：{fund_code}, 错误：{e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"获取历史净值失败（JSON 解析错误）：{fund_code}, 错误：{e}")
            return []
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"获取历史净值失败（数据格式错误）：{fund_code}, 错误：{e}")
            return []
        except Exception as e:
            logger.error(f"获取历史净值失败（未知错误）：{fund_code}, 错误：{e}")
            return []

    def _fetch_nav_history_mobile(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """
        从东方财富移动端 API 获取历史净值（作为 Web API 的 fallback）

        使用 FundMNHisNetList 接口，返回 JSON 而非 JSONP。

        Returns:
            与 fetch_nav_history 相同格式的列表
            失败返回空列表
        """
        try:
            params = {
                "FCODE": fund_code,
                "IsShareNet": "true",
                "MobileKey": "1",
                "appType": "ttjj",
                "appVersion": "6.2.8",
                "cToken": "1",
                "deviceid": "1",
                "pageIndex": "1",
                "pageSize": "100000",
                "plat": "Iphone",
                "product": "EFund",
                "serverVersion": "6.2.8",
                "uToken": "1",
                "userId": "1",
                "version": "6.2.8",
            }
            response = requests.get(
                self.MOBILE_NAV_HISTORY_URL,
                params=params,
                headers=self.MOBILE_HEADERS,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if not data or not data.get("Datas"):
                logger.warning(f"移动端历史净值无数据（FundMNHisNetList）：{fund_code}")
                return []

            items = data["Datas"]
            if not items:
                return []

            result = []
            for item in items:
                # 必需字段：FSRQ（日期）和 DWJZ（单位净值）
                date_str = item.get("FSRQ")
                nav_str = item.get("DWJZ")
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

                accumulated_nav = None
                ljjz_str = item.get("LJJZ")
                if ljjz_str:
                    try:
                        accumulated_nav = Decimal(str(ljjz_str))
                    except Exception:
                        pass

                daily_growth = None
                jzzzl_str = item.get("JZZZL")
                if jzzzl_str:
                    try:
                        daily_growth = Decimal(str(jzzzl_str))
                    except Exception:
                        pass

                result.append(
                    {
                        "nav_date": nav_date,
                        "unit_nav": Decimal(str(nav_str)),
                        "accumulated_nav": accumulated_nav,
                        "daily_growth": daily_growth,
                    }
                )

            return result

        except requests.RequestException as e:
            logger.warning(f"移动端历史净值获取失败（网络）：{fund_code}, 错误：{e}")
            return []
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning(f"移动端历史净值获取失败（解析）：{fund_code}, 错误：{e}")
            return []
        except Exception as e:
            logger.warning(f"移动端历史净值获取失败（未知）：{fund_code}, 错误：{e}")
            return []

    def fetch_index_holdings(self, fund_code: str) -> list:
        """
        获取基金持仓成分股（含实时行情）

        先从 FundMNInverstPosition 获取持仓权重，
        再批量查询 ulist.np 获取实时价格和涨跌幅。

        Returns:
            list of dict: [
                {
                    'stock_code': str,
                    'stock_name': str,
                    'weight': Decimal,       # 持仓占比 %
                    'price': Decimal,        # 当前价格
                    'change_percent': Decimal,  # 涨跌幅 %
                }
            ]
            失败时返回空列表。
        """
        try:
            # Step 1: 获取持仓权重
            headers = {
                "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/91.0.4472.120 Mobile Safari/537.36",
                "Referer": "https://fundmobapi.eastmoney.com/",
            }
            resp = requests.get(
                self.FUND_HOLDINGS_URL,
                params={
                    "FCODE": fund_code,
                    "deviceid": "x",
                    "plat": "Android",
                    "product": "EFund",
                    "version": "1.0.0",
                },
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("Success") or not data.get("Datas"):
                return []

            stocks = data["Datas"].get("fundStocks", [])
            if not stocks:
                return []

            # Step 2: 批量查询实时行情（失败不影响持仓数据返回）
            quotes = {}
            try:
                secids = [f"{s['NEWTEXCH']}.{s['GPDM']}" for s in stocks]
                quote_resp = requests.get(
                    self.STOCK_QUOTE_URL,
                    params={
                        "secids": ",".join(secids),
                        "fields": "f12,f14,f2,f3",
                        "fltt": "2",
                    },
                    timeout=10,
                )
                quote_resp.raise_for_status()
                quote_data = quote_resp.json()

                for item in quote_data.get("data", {}).get("diff", []):
                    quotes[item["f12"]] = {
                        "price": (
                            Decimal(str(item["f2"])) if item.get("f2") not in (None, "-") else None
                        ),
                        "change_percent": (
                            Decimal(str(item["f3"])) if item.get("f3") not in (None, "-") else None
                        ),
                    }
            except Exception as e:
                logger.warning(f"获取个股行情失败：{fund_code}, 错误：{e}")

            # Step 3: 合并结果
            result = []
            for s in stocks:
                code = s["GPDM"]
                q = quotes.get(code, {})
                result.append(
                    {
                        "stock_code": code,
                        "stock_name": s["GPJC"],
                        "weight": Decimal(str(s["JZBL"])),
                        "price": q.get("price"),
                        "change_percent": q.get("change_percent"),
                    }
                )

            return result

        except requests.RequestException as e:
            logger.error(f"获取基金持仓失败（网络错误）：{fund_code}, 错误：{e}")
            return []
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"获取基金持仓失败（数据格式错误）：{fund_code}, 错误：{e}")
            return []
        except Exception as e:
            logger.error(f"获取基金持仓失败（未知错误）：{fund_code}, 错误：{e}")
            return []
