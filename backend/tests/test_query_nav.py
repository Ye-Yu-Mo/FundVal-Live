"""
测试 query_nav 接口

测试点：
1. 15:00 前操作应查询 T-1 净值
2. 15:00 后操作应查询 T 净值
3. 基金不存在应返回 404
4. 未来日期应返回 400
5. 历史净值不存在时应 fallback 到 Fund.latest_nav
6. 历史净值和 latest_nav 都不存在应返回 404
"""
import pytest
from decimal import Decimal
from datetime import date
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from api.models import Fund, FundNavHistory

User = get_user_model()


@pytest.mark.django_db
class TestQueryNav:
    """测试 query_nav 接口"""

    @pytest.fixture
    def client(self):
        """创建 API 客户端"""
        return APIClient()

    @pytest.fixture
    def fund(self):
        """创建测试基金"""
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.5000'),
            latest_nav_date=date(2024, 1, 10),
        )

    @pytest.fixture
    def fund_without_latest_nav(self):
        """创建没有 latest_nav 的基金"""
        return Fund.objects.create(
            fund_code='000002',
            fund_name='测试基金2',
        )

    @pytest.fixture
    def nav_history(self, fund):
        """创建历史净值数据"""
        # 2024-01-02 是周二
        return FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 2),
            unit_nav=Decimal('1.2345'),
        )

    def test_query_nav_before_15(self, client, fund, nav_history):
        """15:00 前操作应查询 T-1 净值"""
        # 2024-01-03 是周三，15:00 前操作应查询 2024-01-02（周二）的净值
        response = client.post('/api/funds/query_nav/', {
            'fund_code': '000001',
            'operation_date': '2024-01-03',
            'before_15': True,
        }, format='json')

        assert response.status_code == 200
        assert response.data['fund_code'] == '000001'
        assert response.data['fund_name'] == '测试基金'
        assert Decimal(response.data['nav']) == Decimal('1.2345')
        assert response.data['nav_date'] == '2024-01-02'
        assert response.data['source'] == 'history'

    def test_query_nav_after_15(self, client, fund, nav_history):
        """15:00 后操作应查询 T 净值"""
        # 2024-01-02 是周二，15:00 后操作应查询 2024-01-02（当天）的净值
        response = client.post('/api/funds/query_nav/', {
            'fund_code': '000001',
            'operation_date': '2024-01-02',
            'before_15': False,
        }, format='json')

        assert response.status_code == 200
        assert response.data['fund_code'] == '000001'
        assert Decimal(response.data['nav']) == Decimal('1.2345')
        assert response.data['nav_date'] == '2024-01-02'
        assert response.data['source'] == 'history'

    def test_query_nav_weekend_before_15(self, client, fund, nav_history):
        """周末 15:00 前操作应查询上周五的净值"""
        from unittest.mock import patch

        # 2024-01-06 是周六，15:00 前应查询 2024-01-05（周五）
        # 但我们的测试数据只有 2024-01-02，没有 2024-01-05
        # 所以应该 fallback 到 Fund.latest_nav

        # Mock sync_nav_history 避免实际同步修改 fund 数据
        with patch('api.services.nav_history.sync_nav_history', return_value=0):
            response = client.post('/api/funds/query_nav/', {
                'fund_code': '000001',
                'operation_date': '2024-01-06',
                'before_15': True,
            }, format='json')

        assert response.status_code == 200
        # 应该 fallback 到 Fund.latest_nav
        assert response.data['nav_date'] == '2024-01-10'
        assert response.data['source'] == 'latest'

    def test_query_nav_fund_not_found(self, client):
        """基金不存在应返回 404"""
        response = client.post('/api/funds/query_nav/', {
            'fund_code': '999999',
            'operation_date': '2024-01-02',
            'before_15': True,
        }, format='json')

        assert response.status_code == 404

    def test_query_nav_future_date(self, client, fund):
        """未来日期应返回 400"""
        response = client.post('/api/funds/query_nav/', {
            'fund_code': '000001',
            'operation_date': '2099-12-31',
            'before_15': True,
        }, format='json')

        assert response.status_code == 400
        assert 'operation_date' in response.data

    def test_query_nav_fallback_to_latest(self, client, fund):
        """历史净值不存在时应 fallback 到 Fund.latest_nav"""
        from unittest.mock import patch

        # Mock sync_nav_history 避免实际同步修改 fund 数据
        with patch('api.services.nav_history.sync_nav_history', return_value=0):
            # 查询一个没有历史净值的日期
            response = client.post('/api/funds/query_nav/', {
                'fund_code': '000001',
                'operation_date': '2024-01-20',
                'before_15': True,
            }, format='json')

        assert response.status_code == 200
        assert response.data['fund_code'] == '000001'
        assert Decimal(response.data['nav']) == Decimal('1.5000')
        assert response.data['nav_date'] == '2024-01-10'
        assert response.data['source'] == 'latest'

    def test_query_nav_no_data(self, client, fund_without_latest_nav):
        """历史净值和 latest_nav 都不存在应返回 404"""
        response = client.post('/api/funds/query_nav/', {
            'fund_code': '000002',
            'operation_date': '2024-01-02',
            'before_15': True,
        }, format='json')

        assert response.status_code == 404
        assert 'error' in response.data

    def test_query_nav_missing_parameters(self, client):
        """缺少必填参数应返回 400"""
        # 缺少 fund_code
        response = client.post('/api/funds/query_nav/', {
            'operation_date': '2024-01-02',
            'before_15': True,
        }, format='json')
        assert response.status_code == 400

        # 缺少 operation_date
        response = client.post('/api/funds/query_nav/', {
            'fund_code': '000001',
            'before_15': True,
        }, format='json')
        assert response.status_code == 400

        # 缺少 before_15
        response = client.post('/api/funds/query_nav/', {
            'fund_code': '000001',
            'operation_date': '2024-01-02',
        }, format='json')
        assert response.status_code == 400
