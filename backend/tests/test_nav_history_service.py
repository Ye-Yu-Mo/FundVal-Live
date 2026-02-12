"""
测试历史净值同步服务
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from api.models import Fund, FundNavHistory
from api.services.nav_history import sync_nav_history, batch_sync_nav_history


@pytest.mark.django_db
class TestNavHistoryService:
    """测试历史净值同步服务"""

    @pytest.fixture
    def fund(self):
        """创建测试基金"""
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
        )

    def test_sync_nav_history_success(self, fund):
        """测试成功同步历史净值"""
        mock_data = [
            {
                'nav_date': date(2024, 1, 1),
                'unit_nav': Decimal('1.2345'),
                'accumulated_nav': Decimal('2.3456'),
                'daily_growth': Decimal('0.9'),
            },
            {
                'nav_date': date(2024, 1, 2),
                'unit_nav': Decimal('1.2456'),
                'accumulated_nav': Decimal('2.3567'),
                'daily_growth': Decimal('0.89'),
            },
        ]

        with patch('api.services.nav_history.SourceRegistry.get_source') as mock_get_source:
            mock_source = MagicMock()
            mock_source.fetch_nav_history.return_value = mock_data
            mock_get_source.return_value = mock_source

            count = sync_nav_history('000001')

            assert count == 2
            assert FundNavHistory.objects.filter(fund=fund).count() == 2

            # 验证数据正确性
            nav1 = FundNavHistory.objects.get(fund=fund, nav_date=date(2024, 1, 1))
            assert nav1.unit_nav == Decimal('1.2345')
            assert nav1.accumulated_nav == Decimal('2.3456')
            assert nav1.daily_growth == Decimal('0.9')

    def test_sync_nav_history_fund_not_exist(self):
        """测试基金不存在"""
        with pytest.raises(ValueError, match='基金不存在'):
            sync_nav_history('999999')

    def test_sync_nav_history_incremental_update(self, fund):
        """测试增量更新：从最后一条记录开始"""
        # 先创建一些历史记录
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal('1.2345'),
        )
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 2),
            unit_nav=Decimal('1.2456'),
        )

        # Mock 新数据（从 2024-01-03 开始）
        mock_data = [
            {
                'nav_date': date(2024, 1, 3),
                'unit_nav': Decimal('1.2567'),
                'accumulated_nav': None,
                'daily_growth': Decimal('0.89'),
            },
        ]

        with patch('api.services.nav_history.SourceRegistry.get_source') as mock_get_source:
            mock_source = MagicMock()
            mock_source.fetch_nav_history.return_value = mock_data
            mock_get_source.return_value = mock_source

            count = sync_nav_history('000001')

            # 验证调用参数：start_date 应该是 2024-01-03（最后一条记录 + 1 天）
            mock_source.fetch_nav_history.assert_called_once()
            call_args = mock_source.fetch_nav_history.call_args
            assert call_args[0][0] == '000001'
            assert call_args[0][1] == date(2024, 1, 3)  # start_date

            assert count == 1
            assert FundNavHistory.objects.filter(fund=fund).count() == 3

    def test_sync_nav_history_force_full_sync(self, fund):
        """测试强制全量同步"""
        # 先创建一些历史记录
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal('1.2345'),
        )

        mock_data = [
            {
                'nav_date': date(2024, 1, 1),
                'unit_nav': Decimal('1.2346'),  # 更新值
                'accumulated_nav': Decimal('2.3456'),
                'daily_growth': Decimal('0.9'),
            },
            {
                'nav_date': date(2024, 1, 2),
                'unit_nav': Decimal('1.2456'),
                'accumulated_nav': None,
                'daily_growth': None,
            },
        ]

        with patch('api.services.nav_history.SourceRegistry.get_source') as mock_get_source:
            mock_source = MagicMock()
            mock_source.fetch_nav_history.return_value = mock_data
            mock_get_source.return_value = mock_source

            count = sync_nav_history('000001', force=True)

            # 强制同步，start_date 应该是 None
            call_args = mock_source.fetch_nav_history.call_args
            assert call_args[0][1] is None  # start_date

            # 只新增了 1 条（2024-01-01 是更新）
            assert count == 1
            assert FundNavHistory.objects.filter(fund=fund).count() == 2

            # 验证 2024-01-01 的数据被更新
            nav1 = FundNavHistory.objects.get(fund=fund, nav_date=date(2024, 1, 1))
            assert nav1.unit_nav == Decimal('1.2346')
            assert nav1.accumulated_nav == Decimal('2.3456')

    def test_sync_nav_history_with_date_range(self, fund):
        """测试指定日期范围同步"""
        mock_data = [
            {
                'nav_date': date(2024, 1, 15),
                'unit_nav': Decimal('1.2345'),
                'accumulated_nav': None,
                'daily_growth': None,
            },
        ]

        with patch('api.services.nav_history.SourceRegistry.get_source') as mock_get_source:
            mock_source = MagicMock()
            mock_source.fetch_nav_history.return_value = mock_data
            mock_get_source.return_value = mock_source

            count = sync_nav_history(
                '000001',
                start_date=date(2024, 1, 10),
                end_date=date(2024, 1, 20)
            )

            # 验证调用参数
            call_args = mock_source.fetch_nav_history.call_args
            assert call_args[0][1] == date(2024, 1, 10)
            assert call_args[0][2] == date(2024, 1, 20)

            assert count == 1

    def test_sync_nav_history_no_new_data(self, fund):
        """测试没有新数据"""
        with patch('api.services.nav_history.SourceRegistry.get_source') as mock_get_source:
            mock_source = MagicMock()
            mock_source.fetch_nav_history.return_value = []
            mock_get_source.return_value = mock_source

            count = sync_nav_history('000001')

            assert count == 0
            assert FundNavHistory.objects.filter(fund=fund).count() == 0

    def test_batch_sync_nav_history_success(self):
        """测试批量同步成功"""
        fund1 = Fund.objects.create(fund_code='000001', fund_name='基金1')
        fund2 = Fund.objects.create(fund_code='000002', fund_name='基金2')

        mock_data = [
            {
                'nav_date': date(2024, 1, 1),
                'unit_nav': Decimal('1.2345'),
                'accumulated_nav': None,
                'daily_growth': None,
            },
        ]

        with patch('api.services.nav_history.SourceRegistry.get_source') as mock_get_source:
            mock_source = MagicMock()
            mock_source.fetch_nav_history.return_value = mock_data
            mock_get_source.return_value = mock_source

            results = batch_sync_nav_history(['000001', '000002'])

            assert results['000001']['success'] is True
            assert results['000001']['count'] == 1
            assert results['000002']['success'] is True
            assert results['000002']['count'] == 1

    def test_batch_sync_nav_history_partial_failure(self):
        """测试批量同步部分失败"""
        fund1 = Fund.objects.create(fund_code='000001', fund_name='基金1')
        # 000002 不存在

        mock_data = [
            {
                'nav_date': date(2024, 1, 1),
                'unit_nav': Decimal('1.2345'),
                'accumulated_nav': None,
                'daily_growth': None,
            },
        ]

        with patch('api.services.nav_history.SourceRegistry.get_source') as mock_get_source:
            mock_source = MagicMock()
            mock_source.fetch_nav_history.return_value = mock_data
            mock_get_source.return_value = mock_source

            results = batch_sync_nav_history(['000001', '000002'])

            assert results['000001']['success'] is True
            assert results['000001']['count'] == 1
            assert results['000002']['success'] is False
            assert '基金不存在' in results['000002']['error']

    def test_sync_nav_history_update_existing(self, fund):
        """测试更新已存在的记录"""
        # 先创建一条记录
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal('1.2345'),
            accumulated_nav=None,
            daily_growth=None,
        )

        # 同步相同日期但不同值的数据
        mock_data = [
            {
                'nav_date': date(2024, 1, 1),
                'unit_nav': Decimal('1.2346'),
                'accumulated_nav': Decimal('2.3456'),
                'daily_growth': Decimal('0.9'),
            },
        ]

        with patch('api.services.nav_history.SourceRegistry.get_source') as mock_get_source:
            mock_source = MagicMock()
            mock_source.fetch_nav_history.return_value = mock_data
            mock_get_source.return_value = mock_source

            count = sync_nav_history('000001', force=True)

            # 更新不算新增
            assert count == 0
            assert FundNavHistory.objects.filter(fund=fund).count() == 1

            # 验证数据被更新
            nav = FundNavHistory.objects.get(fund=fund, nav_date=date(2024, 1, 1))
            assert nav.unit_nav == Decimal('1.2346')
            assert nav.accumulated_nav == Decimal('2.3456')
            assert nav.daily_growth == Decimal('0.9')
