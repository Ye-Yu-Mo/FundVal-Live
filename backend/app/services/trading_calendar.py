# -*- coding: utf-8 -*-
"""
A股交易日历：15:00 前按当日净值，15:00 后按下一交易日净值。
仅考虑周末，节假日可后续扩展。
"""
from datetime import datetime, date, timedelta
from typing import Optional

# 15:00 为分界（同一日 15:00 整算当日）
CUTOFF_HOUR, CUTOFF_MINUTE = 15, 0


def is_trading_day(d: date) -> bool:
    """是否为交易日（先只排除周末）"""
    return d.weekday() < 5  # 0-4 周一到周五


def next_trading_day(d: date) -> date:
    """下一交易日"""
    n = d + timedelta(days=1)
    while not is_trading_day(n):
        n += timedelta(days=1)
    return n


def get_confirm_date(trade_ts: Optional[datetime] = None) -> date:
    """
    根据交易时间计算确认净值日期。
    - 交易日 15:00 前 -> 当日
    - 交易日 15:00 及以后 -> 下一交易日
    - 非交易日 -> 下一交易日
    使用服务器本地时间，若传入 trade_ts 则用该时间。
    """
    if trade_ts is None:
        trade_ts = datetime.now()
    if trade_ts.tzinfo:
        trade_ts = trade_ts.replace(tzinfo=None)  # 转为 naive 比较
    d = trade_ts.date()
    if not is_trading_day(d):
        return next_trading_day(d)
    if (trade_ts.hour, trade_ts.minute) >= (CUTOFF_HOUR, CUTOFF_MINUTE):
        return next_trading_day(d)
    return d


def confirm_date_to_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")
