"""
天天基金数据源实现
"""
import re
import json
import requests
import logging
from decimal import Decimal
from datetime import datetime, date
from typing import Dict, Optional, List

from .base import BaseEstimateSource

logger = logging.getLogger(__name__)


class EastMoneySource(BaseEstimateSource):
    """天天基金数据源"""

    ESTIMATE_URL = 'http://fundgz.1234567.com.cn/js/{code}.js'
    FUND_LIST_URL = 'http://fund.eastmoney.com/js/fundcode_search.js'
    HISTORY_URL = 'http://fund.eastmoney.com/pingzhongdata/{code}.js'
    FUND_HOLDINGS_URL = 'https://fundmobapi.eastmoney.com/FundMNewApi/FundMNInverstPosition'
    STOCK_QUOTE_URL = 'http://push2.eastmoney.com/api/qt/ulist.np/get'

    def get_source_name(self) -> str:
        return 'eastmoney'

    def fetch_estimate(self, fund_code: str) -> Optional[Dict]:
        """
        从天天基金获取估值

        API 返回格式：
        jsonpgz({"fundcode":"000001","name":"华夏成长混合","jzrq":"2026-02-10",
                 "dwjz":"1.1490","gsz":"1.1370","gszzl":"-1.05","gztime":"2026-02-11 15:00"});

        字段说明：
        - fundcode: 基金代码
        - name: 基金名称
        - jzrq: 净值日期（昨日）
        - dwjz: 单位净值（昨日净值）
        - gsz: 估算净值
        - gszzl: 估算增长率
        - gztime: 估值时间
        """
        try:
            url = self.ESTIMATE_URL.format(code=fund_code)
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # 解析 JSONP：jsonpgz({...});
            text = response.text
            match = re.search(r'jsonpgz\((.*)\);?', text)
            if not match:
                logger.warning(f'无法解析估值数据：{fund_code}，响应格式不正确')
                return None

            json_str = match.group(1)
            data = json.loads(json_str)

            # 验证必需字段
            required_fields = ['fundcode', 'name', 'gsz', 'gszzl', 'gztime']
            for field in required_fields:
                if field not in data:
                    logger.warning(f'估值数据缺少字段 {field}：{fund_code}')
                    return None

            return {
                'fund_code': data['fundcode'],
                'fund_name': data['name'],
                'estimate_nav': Decimal(data['gsz']),
                'estimate_growth': Decimal(data['gszzl']),
                'estimate_time': datetime.strptime(data['gztime'], '%Y-%m-%d %H:%M'),
            }

        except requests.RequestException as e:
            logger.error(f'获取估值失败（网络错误）：{fund_code}, 错误：{e}')
            return None
        except json.JSONDecodeError as e:
            logger.error(f'获取估值失败（JSON 解析错误）：{fund_code}, 错误：{e}')
            return None
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f'获取估值失败（数据格式错误）：{fund_code}, 错误：{e}')
            return None
        except Exception as e:
            logger.error(f'获取估值失败（未知错误）：{fund_code}, 错误：{e}')
            return None

    def fetch_realtime_nav(self, fund_code: str) -> Optional[Dict]:
        """
        从天天基金获取实际净值

        使用同一个 API，但只取昨日净值
        """
        try:
            url = self.ESTIMATE_URL.format(code=fund_code)
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            text = response.text
            match = re.search(r'jsonpgz\((.*)\);?', text)
            if not match:
                logger.warning(f'无法解析净值数据：{fund_code}，响应格式不正确')
                return None

            json_str = match.group(1)
            data = json.loads(json_str)

            # 验证必需字段
            required_fields = ['fundcode', 'dwjz', 'jzrq']
            for field in required_fields:
                if field not in data:
                    logger.warning(f'净值数据缺少字段 {field}：{fund_code}')
                    return None

            return {
                'fund_code': data['fundcode'],
                'nav': Decimal(data['dwjz']),
                'nav_date': datetime.strptime(data['jzrq'], '%Y-%m-%d').date(),
            }

        except requests.RequestException as e:
            logger.error(f'获取净值失败（网络错误）：{fund_code}, 错误：{e}')
            return None
        except json.JSONDecodeError as e:
            logger.error(f'获取净值失败（JSON 解析错误）：{fund_code}, 错误：{e}')
            return None
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f'获取净值失败（数据格式错误）：{fund_code}, 错误：{e}')
            return None
        except Exception as e:
            logger.error(f'获取净值失败（未知错误）：{fund_code}, 错误：{e}')
            return None

    def fetch_fund_list(self) -> list:
        """
        从天天基金获取基金列表

        API 返回格式：
        var r = [["000001","HXCZHH","华夏成长混合","混合型-灵活","HUAXIACHENGZHANGHUNHE"], ...];

        数组字段：
        [0] 基金代码
        [1] 拼音缩写
        [2] 基金名称
        [3] 基金类型
        [4] 全拼
        """
        response = requests.get(self.FUND_LIST_URL, timeout=30)
        response.raise_for_status()

        # 解析 JS 变量：var r = [[...], ...];
        text = response.text
        json_str = re.search(r'var r = (\[.*\]);?', text).group(1)
        data = json.loads(json_str)

        funds = []
        for item in data:
            funds.append({
                'fund_code': item[0],
                'fund_name': item[2],
                'fund_type': item[3],
            })

        return funds

    def fetch_today_nav(self, fund_code: str) -> Optional[Dict]:
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
                logger.warning(f'获取当日净值失败：{fund_code}，历史净值数据为空')
                return None

            # 取最后一条记录（最新净值）
            latest = history[-1]

            return {
                'fund_code': fund_code,
                'nav': latest['unit_nav'],
                'nav_date': latest['nav_date'],
            }

        except Exception as e:
            logger.error(f'获取当日净值失败：{fund_code}, 错误：{e}')
            return None

    def get_qrcode(self) -> Optional[Dict]:
        """天天基金不需要登录，返回 None"""
        return None

    def check_qrcode_state(self, qr_id: str) -> Optional[Dict]:
        """天天基金不需要登录，返回 None"""
        return None

    def logout(self):
        """天天基金不需要登录，无操作"""
        pass

    def fetch_nav_history(
        self,
        fund_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict]:
        """
        获取基金历史净值

        API 返回格式：
        var Data_netWorthTrend = [
            {"x":1704067200000,"y":1.2345,"equityReturn":0.9,"unitMoney":""}
        ];
        var Data_ACWorthTrend = [
            {"x":1704067200000,"y":2.3456,"equityReturn":0,"unitMoney":""}
        ];

        字段说明：
        - x: 时间戳（毫秒）
        - y: 净值
        - equityReturn: 日增长率（%）
        - Data_netWorthTrend: 单位净值走势
        - Data_ACWorthTrend: 累计净值走势

        Args:
            fund_code: 基金代码
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            历史净值列表
        """
        try:
            url = self.HISTORY_URL.format(code=fund_code)
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            text = response.text

            # 解析单位净值数据
            unit_nav_match = re.search(r'var Data_netWorthTrend = (\[.*?\]);', text, re.DOTALL)
            if not unit_nav_match:
                logger.warning(f'无法解析历史净值数据：{fund_code}')
                return []

            try:
                unit_nav_data = json.loads(unit_nav_match.group(1))
                logger.info(f'解析单位净值数据成功：{fund_code}, 数据类型：{type(unit_nav_data)}, 长度：{len(unit_nav_data) if isinstance(unit_nav_data, list) else "N/A"}')
                if unit_nav_data and isinstance(unit_nav_data, list):
                    logger.info(f'第一个元素类型：{type(unit_nav_data[0])}, 内容：{unit_nav_data[0]}')
            except Exception as e:
                logger.error(f'解析单位净值数据失败：{fund_code}, 错误：{e}')
                return []

            # 调试：检查数据类型
            if not isinstance(unit_nav_data, list):
                logger.error(f'单位净值数据不是列表：{fund_code}, 类型：{type(unit_nav_data)}, 数据：{unit_nav_data}')
                return []

            if unit_nav_data and not isinstance(unit_nav_data[0], dict):
                logger.error(f'单位净值数据元素不是字典：{fund_code}, 类型：{type(unit_nav_data[0])}, 数据：{unit_nav_data[0]}')
                return []

            # 解析累计净值数据（可选）
            acc_nav_match = re.search(r'var Data_ACWorthTrend = (\[.*?\]);', text, re.DOTALL)
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
                    acc_nav_dict[item['x']] = item
                elif isinstance(item, list) and len(item) >= 2:
                    # 二维数组格式：[timestamp, value]
                    acc_nav_dict[item[0]] = {'x': item[0], 'y': item[1]}

            # 转换数据格式
            result = []
            for item in unit_nav_data:
                # 验证必需字段
                if 'x' not in item or 'y' not in item:
                    continue

                # 转换时间戳（毫秒 -> 秒）
                timestamp = item['x'] / 1000
                nav_date = datetime.fromtimestamp(timestamp).date()

                # 日期过滤
                if start_date and nav_date < start_date:
                    continue
                if end_date and nav_date > end_date:
                    continue

                # 获取累计净值
                acc_nav_item = acc_nav_dict.get(item['x'])
                accumulated_nav = None
                if acc_nav_item and 'y' in acc_nav_item:
                    accumulated_nav = Decimal(str(acc_nav_item['y']))

                result.append({
                    'nav_date': nav_date,
                    'unit_nav': Decimal(str(item['y'])),
                    'accumulated_nav': accumulated_nav,
                    'daily_growth': Decimal(str(item['equityReturn'])) if item.get('equityReturn') is not None else None,
                })

            return result

        except requests.RequestException as e:
            logger.error(f'获取历史净值失败（网络错误）：{fund_code}, 错误：{e}')
            return []
        except json.JSONDecodeError as e:
            logger.error(f'获取历史净值失败（JSON 解析错误）：{fund_code}, 错误：{e}')
            return []
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f'获取历史净值失败（数据格式错误）：{fund_code}, 错误：{e}')
            return []
        except Exception as e:
            logger.error(f'获取历史净值失败（未知错误）：{fund_code}, 错误：{e}')
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
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/91.0.4472.120 Mobile Safari/537.36',
                'Referer': 'https://fundmobapi.eastmoney.com/',
            }
            resp = requests.get(
                self.FUND_HOLDINGS_URL,
                params={
                    'FCODE': fund_code,
                    'deviceid': 'x',
                    'plat': 'Android',
                    'product': 'EFund',
                    'version': '1.0.0',
                },
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get('Success') or not data.get('Datas'):
                return []

            stocks = data['Datas'].get('fundStocks', [])
            if not stocks:
                return []

            # Step 2: 批量查询实时行情
            # NEWTEXCH: 0=深市, 1=沪市（push2 接口格式）
            secids = [f"{s['NEWTEXCH']}.{s['GPDM']}" for s in stocks]
            quote_resp = requests.get(
                self.STOCK_QUOTE_URL,
                params={
                    'secids': ','.join(secids),
                    'fields': 'f12,f14,f2,f3',
                    'fltt': '2',
                },
                timeout=10,
            )
            quote_resp.raise_for_status()
            quote_data = quote_resp.json()

            # 构建行情字典 {stock_code: {price, change_percent}}
            quotes = {}
            for item in quote_data.get('data', {}).get('diff', []):
                quotes[item['f12']] = {
                    'price': Decimal(str(item['f2'])) if item.get('f2') not in (None, '-') else None,
                    'change_percent': Decimal(str(item['f3'])) if item.get('f3') not in (None, '-') else None,
                }

            # Step 3: 合并结果
            result = []
            for s in stocks:
                code = s['GPDM']
                q = quotes.get(code, {})
                result.append({
                    'stock_code': code,
                    'stock_name': s['GPJC'],
                    'weight': Decimal(str(s['JZBL'])),
                    'price': q.get('price'),
                    'change_percent': q.get('change_percent'),
                })

            return result

        except requests.RequestException as e:
            logger.error(f'获取基金持仓失败（网络错误）：{fund_code}, 错误：{e}')
            return []
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f'获取基金持仓失败（数据格式错误）：{fund_code}, 错误：{e}')
            return []
        except Exception as e:
            logger.error(f'获取基金持仓失败（未知错误）：{fund_code}, 错误：{e}')
            return []
