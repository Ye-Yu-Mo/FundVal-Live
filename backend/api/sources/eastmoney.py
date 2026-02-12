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

            unit_nav_data = json.loads(unit_nav_match.group(1))

            # 解析累计净值数据（可选）
            acc_nav_match = re.search(r'var Data_ACWorthTrend = (\[.*?\]);', text, re.DOTALL)
            acc_nav_data = []
            if acc_nav_match:
                try:
                    acc_nav_data = json.loads(acc_nav_match.group(1))
                except json.JSONDecodeError:
                    pass

            # 构建累计净值字典（按时间戳索引）
            acc_nav_dict = {item['x']: item for item in acc_nav_data}

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
