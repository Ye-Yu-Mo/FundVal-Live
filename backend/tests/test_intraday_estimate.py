"""
测试当日实时估值曲线 API + 模型

测试点：
1. EstimateSnapshot 模型创建和查询
2. estimate-intraday API 返回今日快照
3. 按数据源过滤
"""
import pytest
from datetime import datetime, timedelta
from django.test import Client
from django.utils import timezone
from api.models import Fund, EstimateSnapshot


@pytest.mark.django_db
class TestEstimateSnapshotModel:
    def test_create_snapshot(self):
        fund = Fund.objects.create(fund_code='000001', fund_name='Test')
        snap = EstimateSnapshot.objects.create(
            fund=fund,
            source='eastmoney',
            timestamp=timezone.now(),
            estimate_nav='1.2345',
            estimate_growth='0.50',
        )
        assert snap.id is not None
        assert snap.source == 'eastmoney'
        assert str(snap.estimate_nav) == '1.2345'

    def test_today_filter(self):
        fund = Fund.objects.create(fund_code='000001', fund_name='Test')
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        EstimateSnapshot.objects.create(fund=fund, source='eastmoney', timestamp=now, estimate_nav='1.0', estimate_growth='0.1')
        EstimateSnapshot.objects.create(fund=fund, source='eastmoney', timestamp=yesterday, estimate_nav='0.9', estimate_growth='-0.1')

        today_snaps = EstimateSnapshot.objects.filter(
            fund=fund,
            timestamp__date=now.date()
        )
        assert today_snaps.count() == 1


@pytest.mark.django_db
class TestIntradayAPI:
    def test_returns_today_snapshots(self):
        fund = Fund.objects.create(fund_code='000001', fund_name='Test')
        now = timezone.now()
        EstimateSnapshot.objects.create(fund=fund, source='eastmoney', timestamp=now, estimate_nav='1.20', estimate_growth='0.30')
        EstimateSnapshot.objects.create(fund=fund, source='eastmoney', timestamp=now + timedelta(minutes=5), estimate_nav='1.21', estimate_growth='0.35')

        client = Client()
        resp = client.get('/api/funds/000001/estimate-intraday/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['fund_code'] == '000001'
        assert len(data['snapshots']) == 2
        assert data['snapshots'][0]['estimate_nav'] is not None

    def test_source_filter(self):
        fund = Fund.objects.create(fund_code='000001', fund_name='Test')
        now = timezone.now()
        EstimateSnapshot.objects.create(fund=fund, source='eastmoney', timestamp=now, estimate_nav='1.20', estimate_growth='0.30')
        EstimateSnapshot.objects.create(fund=fund, source='yangjibao', timestamp=now, estimate_nav='1.19', estimate_growth='0.28')

        client = Client()
        resp = client.get('/api/funds/000001/estimate-intraday/?source=eastmoney')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['snapshots']) == 1
        assert data['snapshots'][0]['source'] == 'eastmoney'

    def test_empty_returns_empty_list(self):
        Fund.objects.create(fund_code='000001', fund_name='Test')
        client = Client()
        resp = client.get('/api/funds/000001/estimate-intraday/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['snapshots'] == []
