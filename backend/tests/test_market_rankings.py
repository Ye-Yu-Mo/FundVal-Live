"""
测试大盘指数 + 排行 API

测试点：
1. market-indices 返回多指数行情
2. rankings gain 返回涨幅排序
3. rankings popular 返回人气排序
"""
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from django.test import Client
from api.models import Fund, Position, Account


@pytest.mark.django_db
class TestMarketIndices:
    def test_returns_indices(self):
        client = Client()
        mock_body = 'var hq_str_test="测试指数,3200.00,3180.50,3200.50,3210.00,3170.00,0,0,1000000,5000000,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2026-06-04,14:30:00,00";'
        mock_resp = MagicMock()
        mock_resp.text = mock_body
        mock_resp.encoding = 'gbk'
        with patch('api.viewsets.req.get', return_value=mock_resp):
            resp = client.get('/api/funds/market-indices/')
            assert resp.status_code == 200
            data = resp.json()['indices']
            assert len(data) == 4
            codes = [d['code'] for d in data]
            assert 'sh000001' in codes
            assert 'sz399006' in codes


@pytest.mark.django_db
class TestRankingsAPI:
    def test_gain_ranking(self):
        Fund.objects.create(fund_code='F1', fund_name='涨最多', estimate_growth='3.5')
        Fund.objects.create(fund_code='F2', fund_name='涨第二', estimate_growth='2.1')
        Fund.objects.create(fund_code='F3', fund_name='跌最多', estimate_growth='-1.5')

        client = Client()
        resp = client.get('/api/funds/rankings/?type=gain')
        assert resp.status_code == 200
        data = resp.json()['results']
        assert len(data) >= 2
        assert data[0]['fund_code'] == 'F1'

    def test_popular_ranking(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        u = User.objects.create_user(username='testuser', password='pass1')
        f1 = Fund.objects.create(fund_code='F1', fund_name='热门基金')
        f2 = Fund.objects.create(fund_code='F2', fund_name='冷门基金')
        parent = Account.objects.create(user=u, name='账户', parent=None, is_default=False)
        child = Account.objects.create(user=u, name='子账户', parent=parent)
        Position.objects.create(account=child, fund=f1, holding_share='100', holding_cost='100', holding_nav='1')
        Position.objects.create(account=child, fund=f2, holding_share='100', holding_cost='100', holding_nav='1')

        client = Client()
        resp = client.get('/api/funds/rankings/?type=popular')
        assert resp.status_code == 200
        data = resp.json()['results']
        assert len(data) >= 1
        assert data[0]['fund_code'] == 'F1'

    def test_category_filter(self):
        Fund.objects.create(fund_code='F1', fund_name='白酒基金', fund_type='股票型', estimate_growth='3.0')
        Fund.objects.create(fund_code='F2', fund_name='债券基金', fund_type='债券型', estimate_growth='0.5')

        client = Client()
        resp = client.get('/api/funds/rankings/?type=gain&category=债券型')
        data = resp.json()['results']
        assert len(data) == 1
        assert data[0]['fund_code'] == 'F2'
