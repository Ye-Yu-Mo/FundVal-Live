"""
交易日判断工具

使用 chinese_calendar 库判断中国股市交易日
"""

from datetime import date, timedelta
import chinese_calendar as calendar


def is_trading_day(d: date) -> bool:
    """
    判断是否是交易日

    交易日定义：
    - 周一至周五
    - 不是法定节假日
    - 不是调休的工作日（周末调休也不是交易日）

    Args:
        d: 要判断的日期

    Returns:
        bool: True 表示是交易日，False 表示不是
    """
    # 使用 chinese_calendar 判断是否是工作日
    # is_workday() 会考虑节假日和调休
    return calendar.is_workday(d)


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
