"""
测试当日净值获取功能

测试点：
1. BaseEstimateSource.fetch_today_nav 抽象方法
2. EastMoneySource.fetch_today_nav 实现
3. update_nav --today 命令
4. update_fund_today_nav Celery 任务
"""
import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import Mock, patch, call
from io import StringIO
from django.core.management import call_command


class TestBaseEstimateSourceTodayNav:
    """BaseEstimateSource.fetch_today_nav 抽象方法测试"""

    def test_abstract_method_exists(self):
        """测试抽象方法存在"""
        from api.sources.base import BaseEstimateSource

        # 检查抽象方法是否定义
        assert hasattr(BaseEstimateSource, 'fetch_today_nav')

        # 验证不能实例化抽象类
        with pytest.raises(TypeError):
            BaseEstimateSource()


class TestEastMoneySourceTodayNav:
    """EastMoneySource.fetch_today_nav 实现测试"""

    @patch('requests.get')
    def test_fetch_today_nav_success(self, mock_get):
        """测试获取当日净值成功"""
        from api.sources.eastmoney import EastMoneySource

        # Mock pingzhongdata API 响应
        mock_response = Mock()
        mock_response.text = '''
        var Data_netWorthTrend = [
            {"x":1707580800000,"y":1.1234,"equityReturn":0.5},
            {"x":1707667200000,"y":1.1345,"equityReturn":1.0},
            {"x":1707753600000,"y":1.1456,"equityReturn":0.98}
        ];
        var Data_ACWorthTrend = [
            {"x":1707580800000,"y":1.5234},
            {"x":1707667200000,"y":1.5345},
            {"x":1707753600000,"y":1.5456}
        ];
        '''
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        source = EastMoneySource()
        result = source.fetch_today_nav('000001')

        # 验证返回最后一条记录
        assert result is not None
        assert result['fund_code'] == '000001'
        assert result['nav'] == Decimal('1.1456')
        assert isinstance(result['nav_date'], date)
        assert result['nav_date'] == date(2024, 2, 12)  # 1707753600000 对应的日期

    @patch('requests.get')
    def test_fetch_today_nav_empty_data(self, mock_get):
        """测试历史净值数据为空"""
        from api.sources.eastmoney import EastMoneySource

        mock_response = Mock()
        mock_response.text = '''
        var Data_netWorthTrend = [];
        var Data_ACWorthTrend = [];
        '''
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        source = EastMoneySource()
        result = source.fetch_today_nav('000001')

        # 空数据应返回 None
        assert result is None

    @patch('requests.get')
    def test_fetch_today_nav_network_error(self, mock_get):
        """测试网络错误处理"""
        from api.sources.eastmoney import EastMoneySource

        mock_get.side_effect = Exception('Network error')

        source = EastMoneySource()
        result = source.fetch_today_nav('000001')

        # 网络错误应返回 None
        assert result is None


@pytest.mark.django_db
class TestUpdateNavCommandWithToday:
    """update_nav --today 命令测试"""

    @patch('api.sources.eastmoney.requests.get')
    def test_update_nav_today_success(self, mock_get):
        """测试 --today 参数成功更新当日净值"""
        from api.models import Fund

        # 创建测试基金
        fund = Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.1000'),
            latest_nav_date=date(2024, 2, 12),
        )

        # Mock pingzhongdata API 响应（当日净值）
        today = date.today()
        today_timestamp = int(datetime.combine(today, datetime.min.time()).timestamp() * 1000)

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

        # 执行命令
        out = StringIO()
        call_command('update_nav', '--today', stdout=out)

        # 验证净值已更新
        fund.refresh_from_db()
        assert fund.latest_nav == Decimal('1.1500')
        assert fund.latest_nav_date == today

    @patch('api.sources.eastmoney.requests.get')
    def test_update_nav_today_skip_old_date(self, mock_get):
        """测试 --today 参数跳过非当日净值"""
        from api.models import Fund

        # 创建测试基金
        fund = Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.1000'),
            latest_nav_date=date(2024, 2, 12),
        )

        # Mock pingzhongdata API 响应（昨天的净值）
        yesterday = date.today().replace(day=date.today().day - 1)
        yesterday_timestamp = int(datetime.combine(yesterday, datetime.min.time()).timestamp() * 1000)

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

        # 执行命令
        out = StringIO()
        call_command('update_nav', '--today', stdout=out)

        # 验证净值未更新（因为不是今天的）
        fund.refresh_from_db()
        assert fund.latest_nav == Decimal('1.1000')
        assert fund.latest_nav_date == date(2024, 2, 12)

    @patch('api.sources.eastmoney.requests.get')
    def test_update_nav_today_specific_fund(self, mock_get):
        """测试 --today 参数指定基金代码"""
        from api.models import Fund

        # 创建两个基金
        fund1 = Fund.objects.create(
            fund_code='000001',
            fund_name='基金1',
            latest_nav=Decimal('1.1000'),
            latest_nav_date=date(2024, 2, 12),
        )
        fund2 = Fund.objects.create(
            fund_code='000002',
            fund_name='基金2',
            latest_nav=Decimal('2.2000'),
            latest_nav_date=date(2024, 2, 12),
        )

        # Mock pingzhongdata API 响应
        today = date.today()
        today_timestamp = int(datetime.combine(today, datetime.min.time()).timestamp() * 1000)

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

        # 执行命令（只更新 fund1）
        out = StringIO()
        call_command('update_nav', '--today', '--fund_code', '000001', stdout=out)

        # 验证只有 fund1 被更新
        fund1.refresh_from_db()
        fund2.refresh_from_db()
        assert fund1.latest_nav == Decimal('1.1500')
        assert fund1.latest_nav_date == today
        assert fund2.latest_nav == Decimal('2.2000')  # 未更新
        assert fund2.latest_nav_date == date(2024, 2, 12)


@pytest.mark.django_db
class TestUpdateFundTodayNavTask:
    """update_fund_today_nav Celery 任务测试"""

    @patch('api.tasks.call_command')
    def test_task_calls_command(self, mock_call_command):
        """测试任务调用 update_nav --today 命令"""
        from api.tasks import update_fund_today_nav

        # 执行任务
        result = update_fund_today_nav()

        # 验证调用了正确的命令
        mock_call_command.assert_called_once_with('update_nav', '--today')
        assert result == '当日净值更新完成'

    @patch('api.tasks.call_command')
    def test_task_handles_error(self, mock_call_command):
        """测试任务错误处理"""
        from api.tasks import update_fund_today_nav

        # Mock 命令抛出异常
        mock_call_command.side_effect = Exception('Command failed')

        # 执行任务应该抛出异常
        with pytest.raises(Exception, match='Command failed'):
            update_fund_today_nav()


@pytest.mark.django_db
class TestCelerySchedule:
    """Celery 定时任务配置测试"""

    def test_today_nav_schedule_exists(self):
        """测试当日净值定时任务配置存在"""
        from fundval.celery import app

        schedule = app.conf.beat_schedule

        # 验证 21:30 任务
        assert 'update-fund-today-nav-evening' in schedule
        evening_task = schedule['update-fund-today-nav-evening']
        assert evening_task['task'] == 'api.tasks.update_fund_today_nav'
        assert 21 in evening_task['schedule'].hour
        assert 30 in evening_task['schedule'].minute

        # 验证 23:00 任务
        assert 'update-fund-today-nav-night' in schedule
        night_task = schedule['update-fund-today-nav-night']
        assert night_task['task'] == 'api.tasks.update_fund_today_nav'
        assert 23 in night_task['schedule'].hour
        assert 0 in night_task['schedule'].minute
