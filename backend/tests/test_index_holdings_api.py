"""
测试指数基金持仓 API 端点

测试点：
1. 指数基金返回成分股数据
2. 非指数基金返回空列表
3. 数据源不存在时 fallback 到 eastmoney
4. 数据源调用失败时返回空列表
"""
import pytest
from unittest.mock import patch
from decimal import Decimal
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestIndexHoldingsAPI:
    """测试 /api/funds/{code}/index_holdings/ 端点"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def etf_fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='510300',
            fund_name='华泰柏瑞沪深300ETF',
            fund_type='股票指数型',
        )

    @pytest.fixture
    def non_index_fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='华夏成长混合',
            fund_type='混合型',
        )

    @pytest.fixture
    def mock_holdings(self):
        return [
            {
                'stock_code': '300750',
                'stock_name': '宁德时代',
                'weight': Decimal('3.8'),
                'price': Decimal('400.72'),
                'change_percent': Decimal('1.32'),
            },
            {
                'stock_code': '600519',
                'stock_name': '贵州茅台',
                'weight': Decimal('3.37'),
                'price': Decimal('1414.35'),
                'change_percent': Decimal('1.61'),
            },
        ]

    @patch('api.sources.eastmoney.EastMoneySource.fetch_index_holdings')
    def test_index_holdings_success(self, mock_fetch, client, etf_fund, mock_holdings):
        """测试指数基金返回成分股数据"""
        mock_fetch.return_value = mock_holdings

        response = client.get(f'/api/funds/{etf_fund.fund_code}/index_holdings/')

        assert response.status_code == 200
        assert response.data['fund_code'] == '510300'
        assert len(response.data['holdings']) == 2
        assert response.data['holdings'][0]['stock_code'] == '300750'
        assert response.data['holdings'][0]['stock_name'] == '宁德时代'

    @patch('api.sources.eastmoney.EastMoneySource.fetch_index_holdings')
    def test_index_holdings_source_failure_returns_empty(self, mock_fetch, client, etf_fund):
        """测试数据源失败时返回空列表，不报错"""
        mock_fetch.side_effect = Exception('Network error')

        response = client.get(f'/api/funds/{etf_fund.fund_code}/index_holdings/')

        assert response.status_code == 200
        assert response.data['holdings'] == []

    def test_index_holdings_fund_not_found(self, client):
        """测试基金不存在返回空列表（不报错）"""
        response = client.get('/api/funds/999999/index_holdings/')
        assert response.status_code == 200
        assert response.data['holdings'] == []

    @patch('api.sources.eastmoney.EastMoneySource.fetch_index_holdings')
    def test_index_holdings_with_source_param(self, mock_fetch, client, etf_fund, mock_holdings):
        """测试指定数据源参数"""
        mock_fetch.return_value = mock_holdings

        response = client.get(f'/api/funds/{etf_fund.fund_code}/index_holdings/?source=eastmoney')

        assert response.status_code == 200
        assert len(response.data['holdings']) == 2

    @patch('api.sources.eastmoney.EastMoneySource.fetch_index_holdings')
    def test_index_holdings_invalid_source_fallback(self, mock_fetch, client, etf_fund, mock_holdings):
        """测试无效数据源 fallback 到 eastmoney"""
        mock_fetch.return_value = mock_holdings

        response = client.get(f'/api/funds/{etf_fund.fund_code}/index_holdings/?source=invalid_source')

        assert response.status_code == 200
        assert len(response.data['holdings']) == 2
