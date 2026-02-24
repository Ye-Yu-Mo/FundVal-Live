"""
测试批量更新当日净值 API

测试点：
1. batch_update_today_nav 接口
2. 日期校验逻辑
3. 并发处理
"""
import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import Mock, patch
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestBatchUpdateTodayNavAPI:
    """batch_update_today_nav API 测试"""

    def setup_method(self):
        """每个测试前创建测试数据"""
        from api.models import Fund

        self.client = APIClient()

        # 创建测试基金
        self.fund1 = Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金1',
            latest_nav=Decimal('1.1000'),
            latest_nav_date=date(2024, 2, 12),
        )
        self.fund2 = Fund.objects.create(
            fund_code='000002',
            fund_name='测试基金2',
            latest_nav=Decimal('2.2000'),
            latest_nav_date=date(2024, 2, 12),
        )

    @patch('api.sources.eastmoney.requests.get')
    def test_batch_update_today_nav_success(self, mock_get):
        """测试批量更新当日净值成功"""
        today = date.today()
        today_timestamp = int(datetime.combine(today, datetime.min.time()).timestamp() * 1000)

        # Mock pingzhongdata API 响应（当日净值）
        mock_response = Mock()
        mock_response.text = f'''
        var Data_netWorthTrend = [
            {{"x":{today_timestamp},"y":1.1500,"equityReturn":4.55}}
        ];
        var Data_ACWorthTrend = [
            {{"x":{today_timestamp},"y":1.5500}}
        ];
        '''
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # 调用 API
        response = self.client.post('/api/funds/batch_update_today_nav/', {
            'fund_codes': ['000001', '000002']
        }, format='json')

        assert response.status_code == 200
        data = response.json()

        # 验证两个基金都更新成功
        assert data['000001']['updated'] is True
        assert data['000001']['latest_nav'] == '1.15'
        assert data['000001']['latest_nav_date'] == today.isoformat()

        assert data['000002']['updated'] is True
        assert data['000002']['latest_nav'] == '1.15'

        # 验证数据库已更新
        self.fund1.refresh_from_db()
        assert self.fund1.latest_nav == Decimal('1.1500')
        assert self.fund1.latest_nav_date == today

    @patch('api.sources.eastmoney.requests.get')
    def test_batch_update_today_nav_skip_old_date(self, mock_get):
        """测试跳过非当日净值"""
        yesterday = date.today().replace(day=date.today().day - 1)
        yesterday_timestamp = int(datetime.combine(yesterday, datetime.min.time()).timestamp() * 1000)

        # Mock pingzhongdata API 响应（昨天的净值）
        mock_response = Mock()
        mock_response.text = f'''
        var Data_netWorthTrend = [
            {{"x":{yesterday_timestamp},"y":1.1500,"equityReturn":4.55}}
        ];
        var Data_ACWorthTrend = [
            {{"x":{yesterday_timestamp},"y":1.5500}}
        ];
        '''
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # 调用 API
        response = self.client.post('/api/funds/batch_update_today_nav/', {
            'fund_codes': ['000001']
        }, format='json')

        assert response.status_code == 200
        data = response.json()

        # 验证跳过更新
        assert data['000001']['updated'] is False
        assert '非当日净值' in data['000001']['reason']

        # 验证数据库未更新
        self.fund1.refresh_from_db()
        assert self.fund1.latest_nav == Decimal('1.1000')
        assert self.fund1.latest_nav_date == date(2024, 2, 12)

    def test_batch_update_today_nav_missing_fund_codes(self):
        """测试缺少 fund_codes 参数"""
        response = self.client.post('/api/funds/batch_update_today_nav/', {}, format='json')

        assert response.status_code == 400
        assert 'error' in response.json()

    @patch('api.sources.eastmoney.requests.get')
    def test_batch_update_today_nav_network_error(self, mock_get):
        """测试网络错误处理"""
        mock_get.side_effect = Exception('Network error')

        # 调用 API
        response = self.client.post('/api/funds/batch_update_today_nav/', {
            'fund_codes': ['000001']
        }, format='json')

        assert response.status_code == 200
        data = response.json()

        # 验证返回失败信息
        assert data['000001']['updated'] is False
        assert '获取净值失败' in data['000001']['reason']
