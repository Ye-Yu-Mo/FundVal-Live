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

    def test_sync_funds_raises_not_implemented(self):
        """M1: sync_funds 调用 fetch_fund_list 抛 NotImplementedError"""
        out = StringIO()
        with pytest.raises(NotImplementedError, match="基金列表.*akshare"):
            call_command("sync_funds", stdout=out)

    def test_sync_funds_update_existing_raises_not_implemented(self):
        """M1: 已存在基金的同步同样抛 NotImplementedError"""
        from api.models import Fund

        Fund.objects.create(
            fund_code="000001", fund_name="旧名称", fund_type="旧类型",
        )

        out = StringIO()
        with pytest.raises(NotImplementedError, match="基金列表.*akshare"):
            call_command("sync_funds", stdout=out)

    def test_sync_funds_api_error(self):
        """M1: sync_funds 因为 fetch_fund_list 不可用而抛 NotImplementedError"""
        out = StringIO()
        with pytest.raises(NotImplementedError):
            call_command("sync_funds", stdout=out)


@pytest.mark.django_db
class TestUpdateNavCommand:
    """测试更新净值命令"""

    @pytest.fixture
    def fund(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
        )

    @patch("api.management.commands.update_nav._fetch_batch_nav")
    def test_update_nav_success(self, mock_fetch_batch, fund):
        """M1: 批量更新净值成功（通过 Mobile API 批量接口）"""
        mock_fetch_batch.return_value = {
            "000001": {"nav": Decimal("1.1490"), "nav_date": date(2026, 2, 10)},
        }

        out = StringIO()
        call_command("update_nav", stdout=out)

        fund.refresh_from_db()
        assert fund.latest_nav == Decimal("1.1490")
        assert fund.latest_nav_date == date(2026, 2, 10)

    @patch("requests.get")
    def test_update_nav_single_fund(self, mock_get, fund):
        """M1: 单基金更新净值（通过 Mobile API）"""
        from unittest.mock import MagicMock

        # Mock Mobile API (FundMNFInfo) 响应
        mock = MagicMock()
        mock.json.return_value = {
            "Datas": [
                {"FCODE": "000001", "ACCNAV": "1.1490", "PDATE": "2026-02-10"},
            ]
        }
        mock.raise_for_status = MagicMock()
        mock_get.return_value = mock

        out = StringIO()
        call_command("update_nav", fund_code="000001", stdout=out)

        fund.refresh_from_db()
        assert fund.latest_nav == Decimal("1.1490")

    @patch("api.management.commands.update_nav._fetch_batch_nav")
    def test_update_nav_api_error(self, mock_fetch_batch, fund):
        """M1: 批量 API 返回空数据时净值不更新"""
        mock_fetch_batch.return_value = {}

        out = StringIO()
        call_command("update_nav", stdout=out)

        fund.refresh_from_db()
        assert fund.latest_nav is None


@pytest.mark.django_db
class TestCalculateAccuracyCommand:
    """测试计算准确率命令"""

    @pytest.fixture
    def fund(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
        )

    @pytest.fixture
    def accuracy_record(self, fund):
        from api.models import EstimateAccuracy

        yesterday = date.today() - timedelta(days=1)
        return EstimateAccuracy.objects.create(
            source_name="eastmoney",
            fund=fund,
            estimate_date=yesterday,
            estimate_nav=Decimal("1.1370"),
        )

    @patch("requests.get")
    def test_calculate_accuracy_success(self, mock_get, accuracy_record):
        """M1: 计算准确率成功（通过 Mobile API FundMNFInfo）"""
        from unittest.mock import MagicMock

        estimate_date = accuracy_record.estimate_date
        date_str = estimate_date.strftime("%Y-%m-%d")

        # Mock Mobile API (FundMNFInfo) 响应 — fetch_realtime_nav 走这个
        mock = MagicMock()
        mock.json.return_value = {
            "Datas": [
                {"FCODE": "000001", "ACCNAV": "1.1490", "PDATE": date_str},
            ]
        }
        mock.raise_for_status = MagicMock()
        mock_get.return_value = mock

        out = StringIO()
        call_command("calculate_accuracy", stdout=out)

        accuracy_record.refresh_from_db()
        assert accuracy_record.actual_nav == Decimal("1.1490")
        assert accuracy_record.error_rate is not None
        # 误差率 = (1.1370 - 1.1490) / 1.1490 ≈ -0.010444
        assert abs(accuracy_record.error_rate - Decimal("-0.010444")) < Decimal(
            "0.000001"
        )

    def test_calculate_accuracy_skip_completed(self, accuracy_record):
        """测试跳过已计算的记录"""
        # 设置已有实际净值
        accuracy_record.actual_nav = Decimal("1.1490")
        accuracy_record.error_rate = Decimal("0.010444")
        accuracy_record.save()

        # 执行命令
        out = StringIO()
        call_command("calculate_accuracy", stdout=out)

        # 验证记录没有变化
        accuracy_record.refresh_from_db()
        assert accuracy_record.actual_nav == Decimal("1.1490")

    @patch("api.sources.eastmoney.requests.get")
    def test_calculate_accuracy_api_error(self, mock_get, accuracy_record):
        """测试 API 错误时继续处理其他记录"""
        mock_get.side_effect = Exception("Network error")

        # 执行命令应该不报错，只是记录日志
        out = StringIO()
        call_command("calculate_accuracy", stdout=out)

        # 准确率应该没有更新
        accuracy_record.refresh_from_db()
        assert accuracy_record.actual_nav is None

    @patch("requests.get")
    def test_calculate_accuracy_specific_date(self, mock_get, fund):
        """M1: 计算指定日期的准确率（通过 Mobile API FundMNFInfo）"""
        from api.models import EstimateAccuracy
        from unittest.mock import MagicMock

        target_date = date(2024, 2, 11)
        record = EstimateAccuracy.objects.create(
            source_name="eastmoney",
            fund=fund,
            estimate_date=target_date,
            estimate_nav=Decimal("1.1370"),
        )

        mock = MagicMock()
        mock.json.return_value = {
            "Datas": [
                {"FCODE": "000001", "ACCNAV": "1.1490", "PDATE": "2024-02-11"},
            ]
        }
        mock.raise_for_status = MagicMock()
        mock_get.return_value = mock

        out = StringIO()
        call_command("calculate_accuracy", date="2024-02-11", stdout=out)

        record.refresh_from_db()
        assert record.actual_nav == Decimal("1.1490")


@pytest.mark.django_db
class TestRecalculatePositionsCommand:
    """测试重算持仓命令"""

    @pytest.fixture
    def user(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def account(self, user, create_child_account):
        return create_child_account(user, "测试账户")

    @pytest.fixture
    def fund(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
        )

    def test_recalculate_all_positions(self, account, fund):
        """测试重算所有持仓"""
        from api.models import PositionOperation, Position

        # 创建操作
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type="BUY",
            operation_date=date(2024, 2, 11),
            amount=Decimal("1000"),
            share=Decimal("100"),
            nav=Decimal("10"),
        )

        # 执行命令
        out = StringIO()
        call_command("recalculate_positions", stdout=out)

        # 验证持仓已创建
        assert Position.objects.count() == 1
        position = Position.objects.first()
        assert position.holding_share == Decimal("100")

    def test_recalculate_account_positions(self, user, fund, create_child_account):
        """测试重算指定账户的持仓"""
        from api.models import Account, PositionOperation, Position

        account1 = create_child_account(user, "账户1")
        account2 = create_child_account(user, "账户2")

        # 创建两个账户的操作
        PositionOperation.objects.create(
            account=account1,
            fund=fund,
            operation_type="BUY",
            operation_date=date(2024, 2, 11),
            amount=Decimal("1000"),
            share=Decimal("100"),
            nav=Decimal("10"),
        )

        PositionOperation.objects.create(
            account=account2,
            fund=fund,
            operation_type="BUY",
            operation_date=date(2024, 2, 11),
            amount=Decimal("2000"),
            share=Decimal("200"),
            nav=Decimal("10"),
        )

        # 创建操作后会自动创建持仓，先删除账户2的持仓来模拟需要重算的场景
        Position.objects.filter(account=account2).delete()

        # 执行命令（只重算账户1）
        out = StringIO()
        call_command("recalculate_positions", account_id=str(account1.id), stdout=out)

        # 验证只有账户1的持仓被创建
        assert Position.objects.filter(account=account1).count() == 1
        assert Position.objects.filter(account=account2).count() == 0
