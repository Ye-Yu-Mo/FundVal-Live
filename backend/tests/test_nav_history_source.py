"""
测试 EastMoneySource 历史净值获取
"""
import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import patch, MagicMock

from api.sources.eastmoney import EastMoneySource


@pytest.mark.django_db
class TestEastMoneySourceNavHistory:
    """测试 EastMoneySource 历史净值获取"""

    def test_fetch_nav_history_success(self):
        """测试成功获取历史净值"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            # Mock 返回数据
            mock_response = MagicMock()
            mock_response.text = '''
            var Data_netWorthTrend = [
                {"x":1704067200000,"y":1.2345,"equityReturn":0,"unitMoney":""},
                {"x":1704153600000,"y":1.2456,"equityReturn":0.9,"unitMoney":""},
                {"x":1704240000000,"y":1.2567,"equityReturn":0.89,"unitMoney":""}
            ];
            var Data_ACWorthTrend = [
                {"x":1704067200000,"y":2.3456,"equityReturn":0,"unitMoney":""},
                {"x":1704153600000,"y":2.3567,"equityReturn":0.47,"unitMoney":""},
                {"x":1704240000000,"y":2.3678,"equityReturn":0.47,"unitMoney":""}
            ];
            '''
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = source.fetch_nav_history('000001')

            assert len(result) == 3
            assert result[0]['nav_date'] == date(2024, 1, 1)
            assert result[0]['unit_nav'] == Decimal('1.2345')
            assert result[0]['accumulated_nav'] == Decimal('2.3456')
            assert result[0]['daily_growth'] == Decimal('0')

            assert result[1]['nav_date'] == date(2024, 1, 2)
            assert result[1]['unit_nav'] == Decimal('1.2456')
            assert result[1]['daily_growth'] == Decimal('0.9')

    def test_fetch_nav_history_with_date_range(self):
        """测试按日期范围过滤历史净值"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.text = '''
            var Data_netWorthTrend = [
                {"x":1704067200000,"y":1.2345,"equityReturn":0,"unitMoney":""},
                {"x":1704153600000,"y":1.2456,"equityReturn":0.9,"unitMoney":""},
                {"x":1704240000000,"y":1.2567,"equityReturn":0.89,"unitMoney":""},
                {"x":1704326400000,"y":1.2678,"equityReturn":0.88,"unitMoney":""}
            ];
            var Data_ACWorthTrend = [
                {"x":1704067200000,"y":2.3456,"equityReturn":0,"unitMoney":""},
                {"x":1704153600000,"y":2.3567,"equityReturn":0.47,"unitMoney":""},
                {"x":1704240000000,"y":2.3678,"equityReturn":0.47,"unitMoney":""},
                {"x":1704326400000,"y":2.3789,"equityReturn":0.47,"unitMoney":""}
            ];
            '''
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # 只获取 2024-01-02 到 2024-01-03 的数据
            result = source.fetch_nav_history(
                '000001',
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 3)
            )

            assert len(result) == 2
            assert result[0]['nav_date'] == date(2024, 1, 2)
            assert result[1]['nav_date'] == date(2024, 1, 3)

    def test_fetch_nav_history_no_accumulated_nav(self):
        """测试没有累计净值的情况"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            # 只有单位净值，没有累计净值
            mock_response.text = '''
            var Data_netWorthTrend = [
                {"x":1704067200000,"y":1.2345,"equityReturn":0,"unitMoney":""}
            ];
            '''
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = source.fetch_nav_history('000001')

            assert len(result) == 1
            assert result[0]['unit_nav'] == Decimal('1.2345')
            assert result[0]['accumulated_nav'] is None

    def test_fetch_nav_history_invalid_response(self):
        """测试无效响应格式"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.text = 'invalid response'
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = source.fetch_nav_history('000001')

            assert result == []

    def test_fetch_nav_history_network_error(self):
        """测试网络错误"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception('Network error')

            result = source.fetch_nav_history('000001')

            assert result == []

    def test_fetch_nav_history_empty_data(self):
        """测试空数据"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.text = '''
            var Data_netWorthTrend = [];
            var Data_ACWorthTrend = [];
            '''
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = source.fetch_nav_history('000001')

            assert result == []

    def test_fetch_nav_history_missing_fields(self):
        """测试缺少必需字段"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            # 缺少 y 字段（单位净值）
            mock_response.text = '''
            var Data_netWorthTrend = [
                {"x":1704067200000,"equityReturn":0,"unitMoney":""}
            ];
            var Data_ACWorthTrend = [
                {"x":1704067200000,"y":2.3456,"equityReturn":0,"unitMoney":""}
            ];
            '''
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = source.fetch_nav_history('000001')

            # 应该跳过缺少必需字段的记录
            assert result == []

    def test_fetch_nav_history_timestamp_conversion(self):
        """测试时间戳转换"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            # 使用不同的时间戳
            mock_response.text = '''
            var Data_netWorthTrend = [
                {"x":1577836800000,"y":1.0,"equityReturn":0,"unitMoney":""},
                {"x":1609459200000,"y":1.1,"equityReturn":10.0,"unitMoney":""},
                {"x":1640995200000,"y":1.2,"equityReturn":9.09,"unitMoney":""}
            ];
            var Data_ACWorthTrend = [];
            '''
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = source.fetch_nav_history('000001')

            assert len(result) == 3
            assert result[0]['nav_date'] == date(2020, 1, 1)
            assert result[1]['nav_date'] == date(2021, 1, 1)
            assert result[2]['nav_date'] == date(2022, 1, 1)

    def test_fetch_nav_history_decimal_precision(self):
        """测试 Decimal 精度处理"""
        source = EastMoneySource()

        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.text = '''
            var Data_netWorthTrend = [
                {"x":1704067200000,"y":1.23456789,"equityReturn":1.23456789,"unitMoney":""}
            ];
            var Data_ACWorthTrend = [
                {"x":1704067200000,"y":2.34567890,"equityReturn":0,"unitMoney":""}
            ];
            '''
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = source.fetch_nav_history('000001')

            assert len(result) == 1
            # Decimal 应该保持原始精度
            assert result[0]['unit_nav'] == Decimal('1.23456789')
            assert result[0]['accumulated_nav'] == Decimal('2.34567890')
            assert result[0]['daily_growth'] == Decimal('1.23456789')
