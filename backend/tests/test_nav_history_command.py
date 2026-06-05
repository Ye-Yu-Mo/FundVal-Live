"""
测试历史净值同步管理命令
"""

import pytest
from decimal import Decimal
from datetime import date
from io import StringIO
from django.core.management import call_command
from unittest.mock import patch

from api.models import Fund, FundNavHistory


@pytest.mark.django_db
class TestSyncNavHistoryCommand:
    """测试 sync_nav_history 管理命令"""

    @pytest.fixture
    def fund(self):
        """创建测试基金"""
        return Fund.objects.create(
            fund_code="000001",
            fund_name="测试基金",
        )

    def test_sync_single_fund(self, fund):
        """测试同步单个基金"""
        mock_data = [
            {
                "nav_date": date(2024, 1, 1),
                "unit_nav": Decimal("1.2345"),
                "accumulated_nav": Decimal("2.3456"),
                "daily_growth": Decimal("0.9"),
            },
            {
                "nav_date": date(2024, 1, 2),
                "unit_nav": Decimal("1.2456"),
                "accumulated_nav": Decimal("2.3567"),
                "daily_growth": Decimal("0.89"),
            },
        ]

        with patch(
            "api.services.nav_history.SourceRegistry.get_source"
        ) as mock_get_source:
            mock_source = mock_get_source.return_value
            mock_source.fetch_nav_history.return_value = mock_data

            out = StringIO()
            call_command("sync_nav_history", "--fund-code", "000001", stdout=out)

            output = out.getvalue()
            assert "开始同步基金 000001" in output
            assert "同步完成" in output
            assert "新增/更新 2 条记录" in output

            # 验证数据已保存
            assert FundNavHistory.objects.filter(fund=fund).count() == 2

    def test_sync_all_funds(self):
        """测试同步所有基金"""
        fund1 = Fund.objects.create(fund_code="000001", fund_name="基金1")
        fund2 = Fund.objects.create(fund_code="000002", fund_name="基金2")

        mock_data = [
            {
                "nav_date": date(2024, 1, 1),
                "unit_nav": Decimal("1.2345"),
                "accumulated_nav": None,
                "daily_growth": None,
            },
        ]

        with patch(
            "api.services.nav_history.SourceRegistry.get_source"
        ) as mock_get_source:
            mock_source = mock_get_source.return_value
            mock_source.fetch_nav_history.return_value = mock_data

            out = StringIO()
            call_command("sync_nav_history", stdout=out)

            output = out.getvalue()
            assert "开始同步 2 个基金" in output
            assert "同步完成" in output
            assert "成功 2/2 个基金" in output
            assert "新增/更新 2 条记录" in output

            # 验证数据已保存
            assert FundNavHistory.objects.filter(fund=fund1).count() == 1
            assert FundNavHistory.objects.filter(fund=fund2).count() == 1

    def test_sync_with_date_range(self, fund):
        """测试指定日期范围同步"""
        mock_data = [
            {
                "nav_date": date(2024, 1, 15),
                "unit_nav": Decimal("1.2345"),
                "accumulated_nav": None,
                "daily_growth": None,
            },
        ]

        with patch(
            "api.services.nav_history.SourceRegistry.get_source"
        ) as mock_get_source:
            mock_source = mock_get_source.return_value
            mock_source.fetch_nav_history.return_value = mock_data

            out = StringIO()
            call_command(
                "sync_nav_history",
                "--fund-code",
                "000001",
                "--start-date",
                "2024-01-10",
                "--end-date",
                "2024-01-20",
                stdout=out,
            )

            output = out.getvalue()
            assert "同步完成" in output

            # 验证调用参数
            mock_source.fetch_nav_history.assert_called_once()
            call_args = mock_source.fetch_nav_history.call_args
            assert call_args[0][0] == "000001"
            assert call_args[0][1] == date(2024, 1, 10)
            assert call_args[0][2] == date(2024, 1, 20)

    def test_sync_with_force_flag(self, fund):
        """测试强制全量同步"""
        # 先创建一些历史记录
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
        )

        mock_data = [
            {
                "nav_date": date(2024, 1, 1),
                "unit_nav": Decimal("1.2346"),  # 更新值
                "accumulated_nav": Decimal("2.3456"),
                "daily_growth": Decimal("0.9"),
            },
            {
                "nav_date": date(2024, 1, 2),
                "unit_nav": Decimal("1.2456"),
                "accumulated_nav": None,
                "daily_growth": None,
            },
        ]

        with patch(
            "api.services.nav_history.SourceRegistry.get_source"
        ) as mock_get_source:
            mock_source = mock_get_source.return_value
            mock_source.fetch_nav_history.return_value = mock_data

            out = StringIO()
            call_command(
                "sync_nav_history", "--fund-code", "000001", "--force", stdout=out
            )

            output = out.getvalue()
            assert "同步完成" in output

            # 验证数据被更新
            nav = FundNavHistory.objects.get(fund=fund, nav_date=date(2024, 1, 1))
            assert nav.unit_nav == Decimal("1.2346")
            assert nav.accumulated_nav == Decimal("2.3456")

    def test_sync_nonexistent_fund(self):
        """测试同步不存在的基金"""
        out = StringIO()
        err = StringIO()

        with pytest.raises(ValueError, match="基金不存在"):
            call_command(
                "sync_nav_history", "--fund-code", "999999", stdout=out, stderr=err
            )

    def test_sync_no_new_data(self, fund):
        """测试没有新数据"""
        with patch(
            "api.services.nav_history.SourceRegistry.get_source"
        ) as mock_get_source:
            mock_source = mock_get_source.return_value
            mock_source.fetch_nav_history.return_value = []

            out = StringIO()
            call_command("sync_nav_history", "--fund-code", "000001", stdout=out)

            output = out.getvalue()
            assert "同步完成" in output
            assert "新增/更新 0 条记录" in output

    def test_sync_partial_failure(self):
        """测试批量同步部分失败"""
        fund1 = Fund.objects.create(fund_code="000001", fund_name="基金1")
        # 000002 不存在

        mock_data = [
            {
                "nav_date": date(2024, 1, 1),
                "unit_nav": Decimal("1.2345"),
                "accumulated_nav": None,
                "daily_growth": None,
            },
        ]

        with patch(
            "api.services.nav_history.SourceRegistry.get_source"
        ) as mock_get_source:
            mock_source = mock_get_source.return_value
            mock_source.fetch_nav_history.return_value = mock_data

            # 手动创建 000002 来测试
            Fund.objects.create(fund_code="000002", fund_name="基金2")

            out = StringIO()
            call_command("sync_nav_history", stdout=out)

            output = out.getvalue()
            assert "同步完成" in output
            assert "成功 2/2 个基金" in output

    def test_sync_with_start_date_only(self, fund):
        """测试只指定开始日期"""
        mock_data = [
            {
                "nav_date": date(2024, 1, 15),
                "unit_nav": Decimal("1.2345"),
                "accumulated_nav": None,
                "daily_growth": None,
            },
        ]

        with patch(
            "api.services.nav_history.SourceRegistry.get_source"
        ) as mock_get_source:
            mock_source = mock_get_source.return_value
            mock_source.fetch_nav_history.return_value = mock_data

            out = StringIO()
            call_command(
                "sync_nav_history",
                "--fund-code",
                "000001",
                "--start-date",
                "2024-01-10",
                stdout=out,
            )

            output = out.getvalue()
            assert "同步完成" in output

            # 验证调用参数
            call_args = mock_source.fetch_nav_history.call_args
            assert call_args[0][1] == date(2024, 1, 10)
            # end_date 会默认为今天，不是 None

    def test_sync_with_end_date_only(self, fund):
        """测试只指定结束日期"""
        mock_data = [
            {
                "nav_date": date(2024, 1, 5),
                "unit_nav": Decimal("1.2345"),
                "accumulated_nav": None,
                "daily_growth": None,
            },
        ]

        with patch(
            "api.services.nav_history.SourceRegistry.get_source"
        ) as mock_get_source:
            mock_source = mock_get_source.return_value
            mock_source.fetch_nav_history.return_value = mock_data

            out = StringIO()
            call_command(
                "sync_nav_history",
                "--fund-code",
                "000001",
                "--end-date",
                "2024-01-10",
                stdout=out,
            )

            output = out.getvalue()
            assert "同步完成" in output

            # 验证调用参数
            call_args = mock_source.fetch_nav_history.call_args
            assert call_args[0][1] is None  # start_date 为 None
            assert call_args[0][2] == date(2024, 1, 10)

    def test_sync_incremental_update(self, fund):
        """测试增量更新（不使用 force）"""
        # 先创建一些历史记录
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
        )
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 2),
            unit_nav=Decimal("1.2456"),
        )

        # Mock 新数据（从 2024-01-03 开始）
        mock_data = [
            {
                "nav_date": date(2024, 1, 3),
                "unit_nav": Decimal("1.2567"),
                "accumulated_nav": None,
                "daily_growth": None,
            },
        ]

        with patch(
            "api.services.nav_history.SourceRegistry.get_source"
        ) as mock_get_source:
            mock_source = mock_get_source.return_value
            mock_source.fetch_nav_history.return_value = mock_data

            out = StringIO()
            call_command("sync_nav_history", "--fund-code", "000001", stdout=out)

            output = out.getvalue()
            assert "同步完成" in output
            assert "新增/更新 1 条记录" in output

            # 验证总共有 3 条记录
            assert FundNavHistory.objects.filter(fund=fund).count() == 3

    def test_command_help(self):
        """测试命令帮助信息"""
        # --help 会导致 SystemExit，需要捕获
        with pytest.raises(SystemExit) as exc_info:
            out = StringIO()
            call_command("sync_nav_history", "--help", stdout=out)

        # 验证退出码为 0（正常退出）
        assert exc_info.value.code == 0

    def test_invalid_date_format(self, fund):
        """测试无效的日期格式"""
        out = StringIO()
        err = StringIO()

        with pytest.raises(ValueError):
            call_command(
                "sync_nav_history",
                "--fund-code",
                "000001",
                "--start-date",
                "invalid-date",
                stdout=out,
                stderr=err,
            )
