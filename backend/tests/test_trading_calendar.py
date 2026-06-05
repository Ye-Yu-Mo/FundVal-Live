"""
测试交易日判断逻辑

测试点：
1. 周一至周五是交易日
2. 周六日不是交易日
3. 节假日不是交易日
4. 获取最近的交易日
"""

import pytest
from datetime import date, timedelta
from api.utils.trading_calendar import is_trading_day, get_last_trading_day


class TestTradingCalendar:
    """交易日判断测试"""

    def test_is_trading_day_weekday(self):
        """周一至周五应该是交易日（非节假日）"""
        # 2024-01-02 是周二，不是节假日
        assert is_trading_day(date(2024, 1, 2)) is True
        # 2024-01-03 是周三
        assert is_trading_day(date(2024, 1, 3)) is True
        # 2024-01-04 是周四
        assert is_trading_day(date(2024, 1, 4)) is True
        # 2024-01-05 是周五
        assert is_trading_day(date(2024, 1, 5)) is True

    def test_is_trading_day_weekend(self):
        """周六日不是交易日"""
        # 2024-01-06 是周六
        assert is_trading_day(date(2024, 1, 6)) is False
        # 2024-01-07 是周日
        assert is_trading_day(date(2024, 1, 7)) is False

    def test_is_trading_day_holiday(self):
        """节假日不是交易日"""
        # 2024-01-01 是元旦
        assert is_trading_day(date(2024, 1, 1)) is False
        # 2024-02-10 是春节（2024年春节是2月10日）
        assert is_trading_day(date(2024, 2, 10)) is False
        # 2024-10-01 是国庆节
        assert is_trading_day(date(2024, 10, 1)) is False

    def test_get_last_trading_day_same_day(self):
        """如果当天是交易日，返回当天"""
        # 2024-01-02 是周二，是交易日
        assert get_last_trading_day(date(2024, 1, 2)) == date(2024, 1, 2)

    def test_get_last_trading_day_weekend(self):
        """周末应该返回上周五"""
        # 2024-01-06 是周六，应该返回 2024-01-05（周五）
        assert get_last_trading_day(date(2024, 1, 6)) == date(2024, 1, 5)
        # 2024-01-07 是周日，应该返回 2024-01-05（周五）
        assert get_last_trading_day(date(2024, 1, 7)) == date(2024, 1, 5)

    def test_get_last_trading_day_after_holiday(self):
        """节假日后第一天应该返回节假日前最后一个交易日"""
        # 2024-01-01 是元旦（周一），应该返回 2023-12-29（周五）
        assert get_last_trading_day(date(2024, 1, 1)) == date(2023, 12, 29)

    def test_get_last_trading_day_monday_after_weekend(self):
        """周一应该返回周一（如果不是节假日）"""
        # 2024-01-08 是周一，不是节假日
        assert get_last_trading_day(date(2024, 1, 8)) == date(2024, 1, 8)

    def test_get_last_trading_day_long_holiday(self):
        """长假期间应该能正确往前找"""
        # 2024-02-12 是春节假期（2月10-17日），应该返回 2024-02-09（周五）
        assert get_last_trading_day(date(2024, 2, 12)) == date(2024, 2, 9)
