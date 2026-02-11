"""
测试定时任务（Management Commands）

测试点：
1. 同步基金列表
2. 更新基金净值
3. 计算估值准确率
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import Mock, patch
from io import StringIO
from django.core.management import call_command


@pytest.mark.django_db
class TestSyncFundsCommand:
    """测试同步基金列表命令"""

    @patch('api.sources.eastmoney.requests.get')
    def test_sync_funds_success(self, mock_get):
        """测试同步基金列表成功"""
        from api.models import Fund

        # Mock API 响应
        mock_response = Mock()
        mock_response.text = 'var r = [["000001","HXCZHH","华夏成长混合","混合型-灵活","HUAXIACHENGZHANGHUNHE"],["000002","HXCZHH","华夏成长混合(后端)","混合型-灵活","HUAXIACHENGZHANGHUNHE"]];'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # 执行命令
        out = StringIO()
        call_command('sync_funds', stdout=out)

        # 验证基金已创建
        assert Fund.objects.count() == 2
        fund1 = Fund.objects.get(fund_code='000001')
        assert fund1.fund_name == '华夏成长混合'
        assert fund1.fund_type == '混合型-灵活'

    @patch('api.sources.eastmoney.requests.get')
    def test_sync_funds_update_existing(self, mock_get):
        """测试更新已存在的基金"""
        from api.models import Fund

        # 先创建一个基金
        Fund.objects.create(
            fund_code='000001',
            fund_name='旧名称',
            fund_type='旧类型',
        )

        # Mock API 响应
        mock_response = Mock()
        mock_response.text = 'var r = [["000001","HXCZHH","华夏成长混合","混合型-灵活","HUAXIACHENGZHANGHUNHE"]];'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # 执行命令
        call_command('sync_funds', stdout=StringIO())

        # 验证基金已更新
        fund = Fund.objects.get(fund_code='000001')
        assert fund.fund_name == '华夏成长混合'
        assert fund.fund_type == '混合型-灵活'

    @patch('api.sources.eastmoney.requests.get')
    def test_sync_funds_api_error(self, mock_get):
        """测试 API 错误处理"""
        mock_get.side_effect = Exception('Network error')

        # 执行命令应该不报错，只是记录日志
        out = StringIO()
        with pytest.raises(Exception):
            call_command('sync_funds', stdout=out)


@pytest.mark.django_db
class TestUpdateNavCommand:
    """测试更新净值命令"""

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='华夏成长混合',
        )

    @patch('api.sources.eastmoney.requests.get')
    def test_update_nav_success(self, mock_get, fund):
        """测试更新净值成功"""
        # Mock API 响应
        mock_response = Mock()
        mock_response.text = 'jsonpgz({"fundcode":"000001","jzrq":"2026-02-10","dwjz":"1.1490"});'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # 执行命令
        out = StringIO()
        call_command('update_nav', stdout=out)

        # 验证净值已更新
        fund.refresh_from_db()
        assert fund.latest_nav == Decimal('1.1490')
        assert fund.latest_nav_date == date(2026, 2, 10)

    @patch('api.sources.eastmoney.requests.get')
    def test_update_nav_single_fund(self, mock_get, fund):
        """测试更新单个基金净值"""
        # Mock API 响应
        mock_response = Mock()
        mock_response.text = 'jsonpgz({"fundcode":"000001","jzrq":"2026-02-10","dwjz":"1.1490"});'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # 执行命令（指定基金代码）
        out = StringIO()
        call_command('update_nav', fund_code='000001', stdout=out)

        # 验证净值已更新
        fund.refresh_from_db()
        assert fund.latest_nav == Decimal('1.1490')

    @patch('api.sources.eastmoney.requests.get')
    def test_update_nav_api_error(self, mock_get, fund):
        """测试 API 错误时继续处理其他基金"""
        mock_get.side_effect = Exception('Network error')

        # 执行命令应该不报错，只是记录日志
        out = StringIO()
        call_command('update_nav', stdout=out)

        # 净值应该没有更新
        fund.refresh_from_db()
        assert fund.latest_nav is None


@pytest.mark.django_db
class TestCalculateAccuracyCommand:
    """测试计算准确率命令"""

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='华夏成长混合',
        )

    @pytest.fixture
    def accuracy_record(self, fund):
        from api.models import EstimateAccuracy
        yesterday = date.today() - timedelta(days=1)
        return EstimateAccuracy.objects.create(
            source_name='eastmoney',
            fund=fund,
            estimate_date=yesterday,
            estimate_nav=Decimal('1.1370'),
        )

    @patch('api.sources.eastmoney.requests.get')
    def test_calculate_accuracy_success(self, mock_get, accuracy_record):
        """测试计算准确率成功"""
        # Mock API 响应
        mock_response = Mock()
        mock_response.text = 'jsonpgz({"fundcode":"000001","jzrq":"2026-02-10","dwjz":"1.1490"});'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # 执行命令
        out = StringIO()
        call_command('calculate_accuracy', stdout=out)

        # 验证准确率已计算
        accuracy_record.refresh_from_db()
        assert accuracy_record.actual_nav == Decimal('1.1490')
        assert accuracy_record.error_rate is not None
        # 误差率 = |1.1370 - 1.1490| / 1.1490 ≈ 0.010444
        assert abs(accuracy_record.error_rate - Decimal('0.010444')) < Decimal('0.000001')

    def test_calculate_accuracy_skip_completed(self, accuracy_record):
        """测试跳过已计算的记录"""
        # 设置已有实际净值
        accuracy_record.actual_nav = Decimal('1.1490')
        accuracy_record.error_rate = Decimal('0.010444')
        accuracy_record.save()

        # 执行命令
        out = StringIO()
        call_command('calculate_accuracy', stdout=out)

        # 验证记录没有变化
        accuracy_record.refresh_from_db()
        assert accuracy_record.actual_nav == Decimal('1.1490')

    @patch('api.sources.eastmoney.requests.get')
    def test_calculate_accuracy_api_error(self, mock_get, accuracy_record):
        """测试 API 错误时继续处理其他记录"""
        mock_get.side_effect = Exception('Network error')

        # 执行命令应该不报错，只是记录日志
        out = StringIO()
        call_command('calculate_accuracy', stdout=out)

        # 准确率应该没有更新
        accuracy_record.refresh_from_db()
        assert accuracy_record.actual_nav is None

    @patch('api.sources.eastmoney.requests.get')
    def test_calculate_accuracy_specific_date(self, mock_get, fund):
        """测试计算指定日期的准确率"""
        from api.models import EstimateAccuracy

        # 创建指定日期的记录
        target_date = date(2024, 2, 11)
        record = EstimateAccuracy.objects.create(
            source_name='eastmoney',
            fund=fund,
            estimate_date=target_date,
            estimate_nav=Decimal('1.1370'),
        )

        # Mock API 响应
        mock_response = Mock()
        mock_response.text = 'jsonpgz({"fundcode":"000001","jzrq":"2024-02-11","dwjz":"1.1490"});'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # 执行命令（指定日期）
        out = StringIO()
        call_command('calculate_accuracy', date='2024-02-11', stdout=out)

        # 验证准确率已计算
        record.refresh_from_db()
        assert record.actual_nav == Decimal('1.1490')


@pytest.mark.django_db
class TestRecalculatePositionsCommand:
    """测试重算持仓命令"""

    @pytest.fixture
    def user(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user, create_child_account):
        return create_child_account(user, '测试账户')

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='华夏成长混合',
        )

    def test_recalculate_all_positions(self, account, fund):
        """测试重算所有持仓"""
        from api.models import PositionOperation, Position

        # 创建操作
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        # 执行命令
        out = StringIO()
        call_command('recalculate_positions', stdout=out)

        # 验证持仓已创建
        assert Position.objects.count() == 1
        position = Position.objects.first()
        assert position.holding_share == Decimal('100')

    def test_recalculate_account_positions(self, user, fund, create_child_account):
        """测试重算指定账户的持仓"""
        from api.models import Account, PositionOperation, Position

        account1 = create_child_account(user, '账户1')
        account2 = create_child_account(user, '账户2')

        # 创建两个账户的操作
        PositionOperation.objects.create(
            account=account1,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        PositionOperation.objects.create(
            account=account2,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('2000'),
            share=Decimal('200'),
            nav=Decimal('10'),
        )

        # 执行命令（只重算账户1）
        out = StringIO()
        call_command('recalculate_positions', account_id=str(account1.id), stdout=out)

        # 验证只有账户1的持仓被创建
        assert Position.objects.filter(account=account1).count() == 1
        assert Position.objects.filter(account=account2).count() == 0
