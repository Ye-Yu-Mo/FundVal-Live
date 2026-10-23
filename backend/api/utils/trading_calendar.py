"""
交易日判断工具

使用 chinese_calendar 库判断中国股市交易日

注意：chinese_calendar 只覆盖 2004-2026。超出范围时退化为
“周一至周五即交易日”，并记录一次 warning。
"""

import logging
from datetime import date, timedelta

import chinese_calendar as calendar

logger = logging.getLogger(__name__)

_warned_years: set[int] = set()


def is_trading_day(d: date) -> bool:
    """
    判断是否是交易日

    交易日定义：
    - 周一至周五
    - 不是法定节假日
    - 周末调休上班日仍然不是交易日

    Args:
        d: 要判断的日期

    Returns:
        bool: True 表示是交易日，False 表示不是
    """
    # 周末一律不是交易日，包括调休上班的周末
    if d.weekday() >= 5:
        return False

    try:
        return not calendar.is_holiday(d)
    except NotImplementedError:
        if d.year not in _warned_years:
            logger.warning(
                "chinese-calendar 不支持 %s 年，按周一至周五近似判断交易日", d.year
            )
            _warned_years.add(d.year)
        return True


def get_last_trading_day(d: date) -> date:
    """
    获取最近的交易日（往前找）

    如果当天是交易日，返回当天
    如果当天不是交易日，往前找最近的交易日

    Args:
        d: 起始日期

    Returns:
        date: 最近的交易日
    """
    current = d

    # 最多往前找 30 天（避免无限循环）
    for _ in range(30):
        if is_trading_day(current):
            return current
        current -= timedelta(days=1)

    # 如果 30 天内都没有交易日，返回原日期（理论上不会发生）
    return d
