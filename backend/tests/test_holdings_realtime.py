"""
测试基金持仓穿透 API

测试点：
1. holdings-realtime 返回持仓加权 + 行情数据
2. 无持仓数据时返回空数组
3. contribution 计算正确
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import Client
from api.models import Fund


@pytest.mark.django_db
class TestHoldingsRealtime:
    def test_returns_holdings_with_quotes(self):
        fund = Fund.objects.create(fund_code='159915', fund_name='易方达创业板ETF')
        client = Client()

        mock_holdings = [
            {'stock_code': '300750', 'stock_name': '宁德时代', 'weight': Decimal('10.5')},
            {'stock_code': '300059', 'stock_name': '东方财富', 'weight': Decimal('8.2')},
        ]
        mock_quote_1 = {
            'fund_code': '300750', 'market_price': Decimal('180.50'),
            'market_growth': Decimal('2.35'), 'market_time': '2026-06-04 14:30:00',
        }
        mock_quote_2 = {
            'fund_code': '300059', 'market_price': Decimal('15.80'),
            'market_growth': Decimal('-1.20'), 'market_time': '2026-06-04 14:30:00',
        }

        with patch('api.viewsets.SourceRegistry.get_source') as mock_get_source:
            mock_eastmoney = MagicMock()
            mock_eastmoney.fetch_index_holdings.return_value = mock_holdings
            mock_sina = MagicMock()
            mock_sina.fetch_market_quote.side_effect = lambda code: (
                mock_quote_1 if code == '300750' else mock_quote_2
            )

            def get_source_side_effect(name):
                if name == 'eastmoney':
                    return mock_eastmoney
                if name == 'sina':
                    return mock_sina
                return None
            mock_get_source.side_effect = get_source_side_effect

            resp = client.get('/api/funds/159915/holdings-realtime/')
            assert resp.status_code == 200
            data = resp.json()
            assert data['fund_code'] == '159915'
            assert len(data['holdings']) == 2

            h1 = data['holdings'][0]
            assert h1['stock_code'] == '300750'
            assert h1['stock_name'] == '宁德时代'
            assert h1['weight'] == '10.5'
            assert h1['price'] == '180.50'
            assert h1['change_percent'] == '2.35'

    def test_empty_holdings(self):
        fund = Fund.objects.create(fund_code='000001', fund_name='主动型基金')
        client = Client()

        with patch('api.viewsets.SourceRegistry.get_source') as mock_get_source:
            mock_source = MagicMock()
            mock_source.fetch_index_holdings.return_value = []
            mock_get_source.return_value = mock_source

            resp = client.get('/api/funds/000001/holdings-realtime/')
            assert resp.status_code == 200
            data = resp.json()
            assert data['fund_code'] == '000001'
            assert data['holdings'] == []

    def test_contribution_calculation(self):
        fund = Fund.objects.create(fund_code='510050', fund_name='上证50ETF')
        client = Client()

        mock_holdings = [
            {'stock_code': '600519', 'stock_name': '贵州茅台', 'weight': Decimal('15.0')},
        ]
        mock_quote = {
            'fund_code': '600519', 'market_price': Decimal('1800.00'),
            'market_growth': Decimal('3.00'), 'market_time': '2026-06-04 14:30:00',
        }

        with patch('api.viewsets.SourceRegistry.get_source') as mock_get_source:
            mock_eastmoney = MagicMock()
            mock_eastmoney.fetch_index_holdings.return_value = mock_holdings
            mock_sina = MagicMock()
            mock_sina.fetch_market_quote.return_value = mock_quote

            def get_source_side_effect(name):
                if name == 'eastmoney':
                    return mock_eastmoney
                if name == 'sina':
                    return mock_sina
                return None
            mock_get_source.side_effect = get_source_side_effect

            resp = client.get('/api/funds/510050/holdings-realtime/')
            assert resp.status_code == 200
            h = resp.json()['holdings'][0]
            # contribution = weight × change_percent / 100 = 15.0 × 3.00 / 100 = 0.45
            assert h['contribution'] == '0.4500'
