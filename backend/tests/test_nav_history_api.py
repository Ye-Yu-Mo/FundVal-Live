"""
测试基金历史净值 API
"""
import pytest
from decimal import Decimal
from datetime import date
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from unittest.mock import patch

from api.models import Fund, FundNavHistory

User = get_user_model()


@pytest.mark.django_db
class TestFundNavHistoryAPI:
    """测试基金历史净值 API"""

    @pytest.fixture
    def client(self):
        """创建 API 客户端"""
        return APIClient()

    @pytest.fixture
    def admin_user(self):
        """创建管理员用户"""
        return User.objects.create_user(
            username='admin',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )

    @pytest.fixture
    def admin_client(self, admin_user):
        """创建已认证的管理员客户端"""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        return client

    @pytest.fixture
    def fund(self):
        """创建测试基金"""
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
        )

    @pytest.fixture
    def nav_history(self, fund):
        """创建测试历史净值数据"""
        navs = []
        for i in range(1, 6):
            nav = FundNavHistory.objects.create(
                fund=fund,
                nav_date=date(2024, 1, i),
                unit_nav=Decimal(f'1.{i:04d}'),
                accumulated_nav=Decimal(f'2.{i:04d}'),
                daily_growth=Decimal(f'{i}.00'),
            )
            navs.append(nav)
        return navs

    def test_list_nav_history(self, client, nav_history):
        """测试查询历史净值列表"""
        response = client.get('/api/nav-history/')

        assert response.status_code == 200
        assert len(response.data) == 5

        # 验证排序（倒序）
        assert response.data[0]['nav_date'] == '2024-01-05'
        assert response.data[4]['nav_date'] == '2024-01-01'

    def test_list_nav_history_filter_by_fund_code(self, client, nav_history):
        """测试按基金代码过滤"""
        # 创建另一个基金的数据
        fund2 = Fund.objects.create(fund_code='000002', fund_name='基金2')
        FundNavHistory.objects.create(
            fund=fund2,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal('3.0000'),
        )

        response = client.get('/api/nav-history/', {'fund_code': '000001'})

        assert response.status_code == 200
        assert len(response.data) == 5
        # 所有记录都是 000001
        for item in response.data:
            assert item['fund_code'] == '000001'

    def test_list_nav_history_filter_by_date_range(self, client, nav_history):
        """测试按日期范围过滤"""
        response = client.get('/api/nav-history/', {
            'fund_code': '000001',
            'start_date': '2024-01-02',
            'end_date': '2024-01-04',
        })

        assert response.status_code == 200
        assert len(response.data) == 3
        assert response.data[0]['nav_date'] == '2024-01-04'
        assert response.data[2]['nav_date'] == '2024-01-02'

    def test_list_nav_history_filter_by_start_date(self, client, nav_history):
        """测试只指定开始日期"""
        response = client.get('/api/nav-history/', {
            'fund_code': '000001',
            'start_date': '2024-01-03',
        })

        assert response.status_code == 200
        assert len(response.data) == 3
        assert response.data[0]['nav_date'] == '2024-01-05'
        assert response.data[2]['nav_date'] == '2024-01-03'

    def test_list_nav_history_filter_by_end_date(self, client, nav_history):
        """测试只指定结束日期"""
        response = client.get('/api/nav-history/', {
            'fund_code': '000001',
            'end_date': '2024-01-03',
        })

        assert response.status_code == 200
        assert len(response.data) == 3
        assert response.data[0]['nav_date'] == '2024-01-03'
        assert response.data[2]['nav_date'] == '2024-01-01'

    def test_retrieve_nav_history(self, client, nav_history):
        """测试获取单条历史净值"""
        nav = nav_history[0]
        response = client.get(f'/api/nav-history/{nav.id}/')

        assert response.status_code == 200
        assert response.data['fund_code'] == '000001'
        assert response.data['fund_name'] == '测试基金'
        assert response.data['nav_date'] == '2024-01-01'
        assert response.data['unit_nav'] == '1.0001'
        assert response.data['accumulated_nav'] == '2.0001'
        assert response.data['daily_growth'] == '1.0000'  # 4 位小数

    def test_batch_query_nav_history(self, client, nav_history):
        """测试批量查询历史净值"""
        # 创建第二个基金的数据
        fund2 = Fund.objects.create(fund_code='000002', fund_name='基金2')
        FundNavHistory.objects.create(
            fund=fund2,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal('3.0000'),
        )

        response = client.post('/api/nav-history/batch_query/', {
            'fund_codes': ['000001', '000002'],
        }, format='json')

        assert response.status_code == 200
        assert '000001' in response.data
        assert '000002' in response.data
        assert len(response.data['000001']) == 5
        assert len(response.data['000002']) == 1

    def test_batch_query_with_date_range(self, client, nav_history):
        """测试批量查询指定日期范围"""
        response = client.post('/api/nav-history/batch_query/', {
            'fund_codes': ['000001'],
            'start_date': '2024-01-02',
            'end_date': '2024-01-04',
        }, format='json')

        assert response.status_code == 200
        assert len(response.data['000001']) == 3

    def test_batch_query_single_date(self, client, nav_history):
        """测试批量查询单日数据"""
        response = client.post('/api/nav-history/batch_query/', {
            'fund_codes': ['000001'],
            'nav_date': '2024-01-03',
        }, format='json')

        assert response.status_code == 200
        assert len(response.data['000001']) == 1
        assert response.data['000001'][0]['nav_date'] == '2024-01-03'

    def test_batch_query_missing_fund_codes(self, client):
        """测试批量查询缺少 fund_codes 参数"""
        response = client.post('/api/nav-history/batch_query/', {}, format='json')

        assert response.status_code == 400
        assert 'error' in response.data
        assert '缺少 fund_codes 参数' in response.data['error']

    def test_batch_query_nonexistent_fund(self, client):
        """测试批量查询不存在的基金"""
        response = client.post('/api/nav-history/batch_query/', {
            'fund_codes': ['999999'],
        }, format='json')

        assert response.status_code == 200
        assert response.data['999999'] == []

    def test_sync_nav_history(self, admin_client, fund):
        """测试同步历史净值"""
        mock_data = [
            {
                'nav_date': date(2024, 1, 1),
                'unit_nav': Decimal('1.2345'),
                'accumulated_nav': Decimal('2.3456'),
                'daily_growth': Decimal('0.9'),
            },
        ]

        with patch('api.services.nav_history.SourceRegistry.get_source') as mock_get_source:
            mock_source = mock_get_source.return_value
            mock_source.fetch_nav_history.return_value = mock_data

            response = admin_client.post('/api/nav-history/sync/', {
                'fund_codes': ['000001'],
            }, format='json')

            assert response.status_code == 200
            assert response.data['000001']['success'] is True
            assert response.data['000001']['count'] == 1

            # 验证数据已保存
            assert FundNavHistory.objects.filter(fund=fund).count() == 1

    def test_sync_nav_history_with_date_range(self, admin_client, fund):
        """测试同步指定日期范围"""
        mock_data = [
            {
                'nav_date': date(2024, 1, 15),
                'unit_nav': Decimal('1.2345'),
                'accumulated_nav': None,
                'daily_growth': None,
            },
        ]

        with patch('api.services.nav_history.SourceRegistry.get_source') as mock_get_source:
            mock_source = mock_get_source.return_value
            mock_source.fetch_nav_history.return_value = mock_data

            response = admin_client.post('/api/nav-history/sync/', {
                'fund_codes': ['000001'],
                'start_date': '2024-01-10',
                'end_date': '2024-01-20',
            }, format='json')

            assert response.status_code == 200
            assert response.data['000001']['success'] is True

    def test_sync_nav_history_missing_fund_codes(self, admin_client):
        """测试同步缺少 fund_codes 参数"""
        response = admin_client.post('/api/nav-history/sync/', {}, format='json')

        assert response.status_code == 400
        assert 'error' in response.data

    def test_sync_nav_history_nonexistent_fund(self, admin_client):
        """测试同步不存在的基金"""
        response = admin_client.post('/api/nav-history/sync/', {
            'fund_codes': ['999999'],
        }, format='json')

        assert response.status_code == 200
        assert response.data['999999']['success'] is False
        assert '基金不存在' in response.data['999999']['error']

    def test_nav_history_readonly(self, client, nav_history):
        """测试历史净值 API 是只读的"""
        nav = nav_history[0]

        # 测试 POST（创建）
        response = client.post('/api/nav-history/', {
            'fund': nav.fund.id,
            'nav_date': '2024-01-10',
            'unit_nav': '1.5000',
        }, format='json')
        assert response.status_code == 405  # Method Not Allowed

        # 测试 PUT（更新）
        response = client.put(f'/api/nav-history/{nav.id}/', {
            'unit_nav': '1.5000',
        }, format='json')
        assert response.status_code == 405

        # 测试 PATCH（部分更新）
        response = client.patch(f'/api/nav-history/{nav.id}/', {
            'unit_nav': '1.5000',
        }, format='json')
        assert response.status_code == 405

        # 测试 DELETE（删除）
        response = client.delete(f'/api/nav-history/{nav.id}/')
        assert response.status_code == 405

    def test_serializer_fields(self, client, nav_history):
        """测试序列化器字段"""
        nav = nav_history[0]
        response = client.get(f'/api/nav-history/{nav.id}/')

        assert response.status_code == 200
        data = response.data

        # 验证所有字段都存在
        assert 'id' in data
        assert 'fund_code' in data
        assert 'fund_name' in data
        assert 'nav_date' in data
        assert 'unit_nav' in data
        assert 'accumulated_nav' in data
        assert 'daily_growth' in data
        assert 'created_at' in data
        assert 'updated_at' in data

    def test_empty_result(self, client):
        """测试空结果"""
        response = client.get('/api/nav-history/', {'fund_code': '999999'})

        assert response.status_code == 200
        assert response.data == []

    def test_batch_query_multiple_funds(self, client):
        """测试批量查询多个基金"""
        # 创建多个基金和数据
        for i in range(1, 4):
            fund = Fund.objects.create(
                fund_code=f'00000{i}',
                fund_name=f'基金{i}',
            )
            FundNavHistory.objects.create(
                fund=fund,
                nav_date=date(2024, 1, 1),
                unit_nav=Decimal(f'{i}.0000'),
            )

        response = client.post('/api/nav-history/batch_query/', {
            'fund_codes': ['000001', '000002', '000003'],
        }, format='json')

        assert response.status_code == 200
        assert len(response.data) == 3
        assert all(len(response.data[code]) == 1 for code in ['000001', '000002', '000003'])
