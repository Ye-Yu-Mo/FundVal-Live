"""
测试指数基金持仓数据源

测试点：
1. EastMoneySource.fetch_index_holdings 成功
2. EastMoneySource.fetch_index_holdings 失败处理
3. YangJiBaoSource fallback 到 EastMoneySource
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch


class TestEastMoneyIndexHoldings:
    """EastMoneySource.fetch_index_holdings 测试"""

    @patch('requests.get')
    def test_fetch_index_holdings_success(self, mock_get):
        """测试获取成分股成功"""
        from api.sources.eastmoney import EastMoneySource

        # Mock 持仓接口响应
        holdings_response = Mock()
        holdings_response.status_code = 200
        holdings_response.json.return_value = {
            'Success': True,
            'Datas': {
                'fundStocks': [
                    {
                        'GPDM': '300750',
                        'GPJC': '宁德时代',
                        'JZBL': '3.8',
                        'TEXCH': '2',
                        'NEWTEXCH': '0',
                    },
                    {
                        'GPDM': '600519',
                        'GPJC': '贵州茅台',
                        'JZBL': '3.37',
                        'TEXCH': '1',
                        'NEWTEXCH': '1',
                    },
                ]
            }
        }

        # Mock 行情接口响应
        quote_response = Mock()
        quote_response.status_code = 200
        quote_response.json.return_value = {
            'data': {
                'diff': [
                    {'f12': '300750', 'f2': 400.72, 'f3': 1.32},
                    {'f12': '600519', 'f2': 1414.35, 'f3': 1.61},
                ]
            }
        }

        mock_get.side_effect = [holdings_response, quote_response]

        source = EastMoneySource()
        result = source.fetch_index_holdings('510300')

        assert len(result) == 2
        assert result[0]['stock_code'] == '300750'
        assert result[0]['stock_name'] == '宁德时代'
        assert result[0]['weight'] == Decimal('3.8')
        assert result[0]['price'] == Decimal('400.72')
        assert result[0]['change_percent'] == Decimal('1.32')

        assert result[1]['stock_code'] == '600519'
        assert result[1]['stock_name'] == '贵州茅台'
        assert result[1]['weight'] == Decimal('3.37')
        assert result[1]['price'] == Decimal('1414.35')
        assert result[1]['change_percent'] == Decimal('1.61')

    @patch('requests.get')
    def test_fetch_index_holdings_no_data(self, mock_get):
        """测试基金无持仓数据"""
        from api.sources.eastmoney import EastMoneySource

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'Success': False,
            'Datas': None,
        }
        mock_get.return_value = mock_response

        source = EastMoneySource()
        result = source.fetch_index_holdings('000001')

        assert result == []

    @patch('requests.get')
    def test_fetch_index_holdings_network_error(self, mock_get):
        """测试网络错误"""
        from api.sources.eastmoney import EastMoneySource

        mock_get.side_effect = Exception('Network error')

        source = EastMoneySource()
        result = source.fetch_index_holdings('510300')

        assert result == []

    @patch('requests.get')
    def test_fetch_index_holdings_empty_stocks(self, mock_get):
        """测试持仓列表为空"""
        from api.sources.eastmoney import EastMoneySource

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'Success': True,
            'Datas': {
                'fundStocks': []
            }
        }
        mock_get.return_value = mock_response

        source = EastMoneySource()
        result = source.fetch_index_holdings('510300')

        assert result == []

    @patch('requests.get')
    def test_fetch_index_holdings_quote_missing(self, mock_get):
        """测试行情数据缺失"""
        from api.sources.eastmoney import EastMoneySource

        holdings_response = Mock()
        holdings_response.status_code = 200
        holdings_response.json.return_value = {
            'Success': True,
            'Datas': {
                'fundStocks': [
                    {
                        'GPDM': '300750',
                        'GPJC': '宁德时代',
                        'JZBL': '3.8',
                        'TEXCH': '2',
                        'NEWTEXCH': '0',
                    },
                ]
            }
        }

        quote_response = Mock()
        quote_response.status_code = 200
        quote_response.json.return_value = {
            'data': {
                'diff': []  # 行情数据为空
            }
        }

        mock_get.side_effect = [holdings_response, quote_response]

        source = EastMoneySource()
        result = source.fetch_index_holdings('510300')

        # 应该返回持仓数据，但价格和涨跌幅为 None
        assert len(result) == 1
        assert result[0]['stock_code'] == '300750'
        assert result[0]['stock_name'] == '宁德时代'
        assert result[0]['weight'] == Decimal('3.8')
        assert result[0]['price'] is None
        assert result[0]['change_percent'] is None


class TestYangJiBaoIndexHoldings:
    """YangJiBaoSource.fetch_index_holdings 测试"""

    @patch('api.sources.eastmoney.EastMoneySource.fetch_index_holdings')
    def test_yangjibao_fallback_to_eastmoney(self, mock_fetch):
        """测试养基宝 fallback 到东方财富"""
        from api.sources.yangjibao import YangJiBaoSource

        mock_fetch.return_value = [
            {
                'stock_code': '300750',
                'stock_name': '宁德时代',
                'weight': Decimal('3.8'),
                'price': Decimal('400.72'),
                'change_percent': Decimal('1.32'),
            }
        ]

        source = YangJiBaoSource()
        result = source.fetch_index_holdings('510300')

        mock_fetch.assert_called_once_with('510300')
        assert len(result) == 1
        assert result[0]['stock_code'] == '300750'
