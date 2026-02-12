"""
天天基金数据源实现
"""
import re
import json
import requests
import logging
from decimal import Decimal
from datetime import datetime
from typing import Dict, Optional

from .base import BaseEstimateSource

logger = logging.getLogger(__name__)


class EastMoneySource(BaseEstimateSource):
    """天天基金数据源"""

    ESTIMATE_URL = 'http://fundgz.1234567.com.cn/js/{code}.js'
    FUND_LIST_URL = 'http://fund.eastmoney.com/js/fundcode_search.js'

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
