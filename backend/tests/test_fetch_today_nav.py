"""
测试当日净值获取功能 (M1 更新)

M1 后 fetch_nav_history() 直接调用 Mobile API (FundMNHisNetList JSON)，
fetch_realtime_nav() 直接调用 Mobile API (FundMNFInfo JSON)。
所有 mock 使用 Mobile API 响应格式。
"""

from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command


def _make_mobile_nav_response(items):
    """构造 FundMNHisNetList 的 mock 响应"""
    mock = MagicMock()
    mock.json.return_value = {"Datas": items}
    mock.raise_for_status = MagicMock()
    return mock


def _make_mobile_realtime_response(items):
    """构造 FundMNFInfo 的 mock 响应"""
    mock = MagicMock()
    mock.json.return_value = {"Datas": items}
    mock.raise_for_status = MagicMock()
    return mock


class TestBaseEstimateSourceTodayNav:
    """BaseEstimateSource.fetch_today_nav 抽象方法测试"""

    def test_abstract_method_exists(self):
        """测试抽象方法存在"""
        from api.sources.base import BaseEstimateSource

        # 检查抽象方法是否定义
        assert hasattr(BaseEstimateSource, "fetch_today_nav")

        # 验证不能实例化抽象类
        with pytest.raises(TypeError):
            BaseEstimateSource()


class TestEastMoneySourceTodayNav:
    """EastMoneySource.fetch_today_nav 实现测试 (M1: Mobile API)"""

    @patch("requests.get")
    def test_fetch_today_nav_success(self, mock_get):
        """测试获取当日净值成功（通过 Mobile API）"""
        from api.sources.eastmoney import EastMoneySource

        mock_get.return_value = _make_mobile_nav_response(
            [
                {"FSRQ": "2024-02-11", "DWJZ": "1.1234", "LJJZ": "1.5234", "JZZZL": "0.50"},
                {"FSRQ": "2024-02-12", "DWJZ": "1.1345", "LJJZ": "1.5345", "JZZZL": "1.00"},
                {"FSRQ": "2024-02-13", "DWJZ": "1.1456", "LJJZ": "1.5456", "JZZZL": "0.98"},
            ]
        )

        source = EastMoneySource()
        result = source.fetch_today_nav("000001")

        # 验证返回最后一条记录（最新日期）
        assert result is not None
        assert result["fund_code"] == "000001"
        assert result["nav"] == Decimal("1.1456")
        assert isinstance(result["nav_date"], date)
        assert result["nav_date"] == date(2024, 2, 13)

    @patch("requests.get")
    def test_fetch_today_nav_empty_data(self, mock_get):
        """测试历史净值数据为空"""
        from api.sources.eastmoney import EastMoneySource

        mock_get.return_value = _make_mobile_nav_response([])

        source = EastMoneySource()
        result = source.fetch_today_nav("000001")

        # 空数据应返回 None
        assert result is None

    @patch("requests.get")
    def test_fetch_today_nav_network_error(self, mock_get):
        """测试网络错误处理"""
        from api.sources.eastmoney import EastMoneySource

        mock_get.side_effect = Exception("Network error")

        source = EastMoneySource()
        result = source.fetch_today_nav("000001")

        # 网络错误应返回 None
        assert result is None


@pytest.mark.django_db
class TestUpdateNavCommandWithToday:
    """update_nav --today 命令测试 (M1: 使用 Mobile API)"""

    @patch("api.management.commands.update_nav._fetch_batch_nav")
    def test_update_nav_today_success(self, mock_fetch_batch):
        """测试 --today 参数成功更新当日净值"""
        from api.models import Fund

        today = date.today()

        # 创建测试基金
        fund = Fund.objects.create(
            fund_code="000001",
            fund_name="测试基金",
            latest_nav=Decimal("1.1000"),
            latest_nav_date=date(2024, 2, 12),
        )

        # Mock 批量获取返回今日净值
        mock_fetch_batch.return_value = {
            "000001": {"nav": Decimal("1.1500"), "nav_date": today},
        }

        out = StringIO()
        call_command("update_nav", "--today", stdout=out)

        fund.refresh_from_db()
        assert fund.latest_nav == Decimal("1.1500")
        assert fund.latest_nav_date == today

    @patch("api.management.commands.update_nav._fetch_batch_nav")
    def test_update_nav_today_skip_old_date(self, mock_fetch_batch):
        """测试 --today 参数跳过非当日净值"""
        from api.models import Fund

        # 创建测试基金
        fund = Fund.objects.create(
            fund_code="000001",
            fund_name="测试基金",
            latest_nav=Decimal("1.1000"),
            latest_nav_date=date(2024, 2, 12),
        )

        # Mock 批量获取返回昨天的净值（不是今天）
        yesterday = date.today().replace(day=max(1, date.today().day - 1))
        mock_fetch_batch.return_value = {
            "000001": {"nav": Decimal("1.1500"), "nav_date": yesterday},
        }

        out = StringIO()
        call_command("update_nav", "--today", stdout=out)

        # 验证净值未更新（因为不是今天的）
        fund.refresh_from_db()
        assert fund.latest_nav == Decimal("1.1000")
        assert fund.latest_nav_date == date(2024, 2, 12)

    @patch("api.management.commands.update_nav._fetch_batch_nav")
    def test_update_nav_today_specific_fund(self, mock_fetch_batch):
        """测试 --today 参数指定基金代码（单基金模式走多源 fallback）"""
        from api.models import Fund

        today = date.today()

        # 创建两个基金
        fund1 = Fund.objects.create(
            fund_code="000001",
            fund_name="基金1",
            latest_nav=Decimal("1.1000"),
            latest_nav_date=date(2024, 2, 12),
        )
        fund2 = Fund.objects.create(
            fund_code="000002",
            fund_name="基金2",
            latest_nav=Decimal("2.2000"),
            latest_nav_date=date(2024, 2, 12),
        )

        # 单基金模式 (_fetch_batch_nav 被 --fund_code 分支跳过，走多源 fallback)
        # mock fetch_today_nav 的底层 Mobile API
        with patch("requests.get") as mock_get:
            mock_get.return_value = _make_mobile_nav_response(
                [
                    {
                        "FSRQ": today.isoformat(),
                        "DWJZ": "1.1500",
                        "LJJZ": "1.5500",
                        "JZZZL": "4.55",
                    },
                ]
            )

            out = StringIO()
            call_command("update_nav", "--today", "--fund_code", "000001", stdout=out)

        # 验证只有 fund1 被更新
        fund1.refresh_from_db()
        fund2.refresh_from_db()
        assert fund1.latest_nav == Decimal("1.1500")
        assert fund1.latest_nav_date == today
        assert fund2.latest_nav == Decimal("2.2000")  # 未更新
        assert fund2.latest_nav_date == date(2024, 2, 12)


@pytest.mark.django_db
class TestUpdateFundTodayNavTask:
    """update_fund_today_nav Celery 任务测试"""

    @patch("api.tasks.call_command")
    def test_task_calls_command(self, mock_call_command):
        """测试任务调用 update_nav --today 命令"""
        from api.tasks import update_fund_today_nav

        # 执行任务
        result = update_fund_today_nav()

        # 验证调用了正确的命令
        mock_call_command.assert_called_once_with("update_nav", "--today")
        assert result == "当日净值更新完成"

    @patch("api.tasks.call_command")
    def test_task_handles_error(self, mock_call_command):
        """测试任务错误处理"""
        from api.tasks import update_fund_today_nav

        # Mock 命令抛出异常
        mock_call_command.side_effect = Exception("Command failed")

        # 执行任务应该抛出异常
        with pytest.raises(Exception, match="Command failed"):
            update_fund_today_nav()


@pytest.mark.django_db
class TestCelerySchedule:
    """Celery 定时任务配置测试"""

    def test_today_nav_schedule_exists(self):
        """测试当日净值定时任务配置存在"""
        from fundval.celery import app

        schedule = app.conf.beat_schedule

        # 验证 update-fund-today-nav-task 任务存在（21:30 和 23:00）
        assert "update-fund-today-nav-task" in schedule
        task = schedule["update-fund-today-nav-task"]
        assert task["task"] == "api.tasks.update_fund_today_nav"
        # 验证调度时间包含 21 和 23 点
        assert 21 in task["schedule"].hour or 23 in task["schedule"].hour
        assert 30 in task["schedule"].minute or 0 in task["schedule"].minute
