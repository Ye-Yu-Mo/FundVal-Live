"""
测试账户历史市值计算

测试点：
1. 基本场景：有操作、有净值
2. 无操作流水
3. 无净值数据（fallback 到 Fund.latest_nav）
4. 多个基金
5. 买入卖出混合
6. 成本计算正确性
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestPositionHistory:
    """账户历史市值计算测试"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def account(self, user, create_child_account):
        return create_child_account(user, "测试账户")

    @pytest.fixture
    def fund1(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
            latest_nav=Decimal("1.5000"),
        )

    @pytest.fixture
    def fund2(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000002",
            fund_name="易方达蓝筹",
            latest_nav=Decimal("2.0000"),
        )

    def test_calculate_account_history_no_operations(self, account):
        """无操作流水，返回空列表"""
        from api.services.position_history import calculate_account_history

        result = calculate_account_history(account.id, days=30)

        assert result == []

    def test_calculate_account_history_basic(self, account, fund1):
        """基本场景：有操作、有净值"""
        from api.models import PositionOperation, FundNavHistory

        # 创建操作：10 天前买入 1000 元，净值 1.0，份额 1000
        op_date = date.today() - timedelta(days=10)
        PositionOperation.objects.create(
            account=account,
            fund=fund1,
            operation_type="BUY",
            operation_date=op_date,
            amount=Decimal("1000.00"),
            share=Decimal("1000.0000"),
            nav=Decimal("1.0000"),
            before_15=True,
        )

        # 创建历史净值：过去 15 天，净值从 1.0 涨到 1.5
        for i in range(15):
            nav_date = date.today() - timedelta(days=14 - i)
            nav_value = Decimal("1.0000") + Decimal(str(i * 0.05))
            FundNavHistory.objects.create(
                fund=fund1,
                nav_date=nav_date,
                unit_nav=nav_value,
            )

        # 计算历史市值
        from api.services.position_history import calculate_account_history

        result = calculate_account_history(account.id, days=15)

        # 验证结果
        assert len(result) == 16  # 15 天 + 今天
        assert result[0]["date"] == (date.today() - timedelta(days=15)).isoformat()
        assert result[-1]["date"] == date.today().isoformat()

        # 验证市值变化
        # 买入前（前 5 天）市值和成本都应该是 0
        for i in range(5):
            assert result[i]["value"] == 0
            assert result[i]["cost"] == 0

        # 买入后（第 6 天开始，因为买入是 10 天前，查询范围是 15 天）
        # 成本应该是 1000
        for i in range(5, len(result)):
            assert result[i]["cost"] == 1000.00
            # 市值应该 >= 成本（因为净值在涨）
            if result[i]["value"] > 0:  # 有净值数据
                assert result[i]["value"] >= 1000.00

    def test_calculate_account_history_no_nav(self, account, fund1):
        """无净值数据，使用 Fund.latest_nav"""
        from api.models import PositionOperation

        # 创建操作：5 天前买入
        op_date = date.today() - timedelta(days=5)
        PositionOperation.objects.create(
            account=account,
            fund=fund1,
            operation_type="BUY",
            operation_date=op_date,
            amount=Decimal("1000.00"),
            share=Decimal("1000.0000"),
            nav=Decimal("1.0000"),
            before_15=True,
        )

        # 不创建历史净值，应该 fallback 到 Fund.latest_nav (1.5000)

        # 计算历史市值
        from api.services.position_history import calculate_account_history

        result = calculate_account_history(account.id, days=10)

        # 验证结果
        assert len(result) == 11  # 10 天 + 今天

        # 买入后的市值应该使用 latest_nav
        for i in range(5, len(result)):
            # 市值 = 1000 份额 × 1.5 净值 = 1500
            assert result[i]["value"] == 1500.00
            assert result[i]["cost"] == 1000.00

    def test_calculate_account_history_multiple_funds(self, account, fund1, fund2):
        """多个基金，计算正确"""
        from api.models import PositionOperation, FundNavHistory

        # 基金1：10 天前买入 1000 元
        op_date1 = date.today() - timedelta(days=10)
        PositionOperation.objects.create(
            account=account,
            fund=fund1,
            operation_type="BUY",
            operation_date=op_date1,
            amount=Decimal("1000.00"),
            share=Decimal("1000.0000"),
            nav=Decimal("1.0000"),
            before_15=True,
        )

        # 基金2：5 天前买入 2000 元
        op_date2 = date.today() - timedelta(days=5)
        PositionOperation.objects.create(
            account=account,
            fund=fund2,
            operation_type="BUY",
            operation_date=op_date2,
            amount=Decimal("2000.00"),
            share=Decimal("1000.0000"),
            nav=Decimal("2.0000"),
            before_15=True,
        )

        # 创建历史净值
        for i in range(15):
            nav_date = date.today() - timedelta(days=14 - i)
            # 基金1 净值 1.0 -> 1.5
            FundNavHistory.objects.create(
                fund=fund1,
                nav_date=nav_date,
                unit_nav=Decimal("1.0000") + Decimal(str(i * 0.05)),
            )
            # 基金2 净值 2.0 -> 2.5
            FundNavHistory.objects.create(
                fund=fund2,
                nav_date=nav_date,
                unit_nav=Decimal("2.0000") + Decimal(str(i * 0.05)),
            )

        # 计算历史市值
        from api.services.position_history import calculate_account_history

        result = calculate_account_history(account.id, days=15)

        # 验证结果
        assert len(result) == 16

        # 买入基金1后，买入基金2前（第 5-9 天）
        # 成本 = 1000，市值 = 1000 × nav1
        for i in range(5, 10):
            assert result[i]["cost"] == 1000.00

        # 买入基金2后（第 10 天开始）
        # 成本 = 1000 + 2000 = 3000
        for i in range(10, len(result)):
            assert result[i]["cost"] == 3000.00

    def test_calculate_account_history_buy_sell(self, account, fund1):
        """买入卖出，成本计算正确"""
        from api.models import PositionOperation, FundNavHistory

        # 10 天前买入 1000 元，份额 1000
        op_date1 = date.today() - timedelta(days=10)
        PositionOperation.objects.create(
            account=account,
            fund=fund1,
            operation_type="BUY",
            operation_date=op_date1,
            amount=Decimal("1000.00"),
            share=Decimal("1000.0000"),
            nav=Decimal("1.0000"),
            before_15=True,
        )

        # 5 天前卖出 500 份额（一半）
        op_date2 = date.today() - timedelta(days=5)
        PositionOperation.objects.create(
            account=account,
            fund=fund1,
            operation_type="SELL",
            operation_date=op_date2,
            amount=Decimal("600.00"),  # 卖出金额
            share=Decimal("500.0000"),  # 卖出份额
            nav=Decimal("1.2000"),
            before_15=True,
        )

        # 创建历史净值
        for i in range(15):
            nav_date = date.today() - timedelta(days=14 - i)
            FundNavHistory.objects.create(
                fund=fund1,
                nav_date=nav_date,
                unit_nav=Decimal("1.0000") + Decimal(str(i * 0.05)),
            )

        # 计算历史市值
        from api.services.position_history import calculate_account_history

        result = calculate_account_history(account.id, days=15)

        # 验证结果
        assert len(result) == 16

        # 买入后，卖出前（第 5-9 天）
        # 成本 = 1000
        for i in range(5, 10):
            assert result[i]["cost"] == 1000.00

        # 卖出后（第 10 天开始）
        # 成本 = 1000 × 50% = 500（卖出一半，成本减半）
        for i in range(10, len(result)):
            assert result[i]["cost"] == 500.00

    def test_calculate_account_history_custom_days(self, account, fund1):
        """自定义天数，返回正确数量"""
        from api.models import PositionOperation

        # 创建操作
        op_date = date.today() - timedelta(days=50)
        PositionOperation.objects.create(
            account=account,
            fund=fund1,
            operation_type="BUY",
            operation_date=op_date,
            amount=Decimal("1000.00"),
            share=Decimal("1000.0000"),
            nav=Decimal("1.0000"),
            before_15=True,
        )

        # 测试不同天数
        from api.services.position_history import calculate_account_history

        result_30 = calculate_account_history(account.id, days=30)
        assert len(result_30) == 31  # 30 天 + 今天

        result_90 = calculate_account_history(account.id, days=90)
        assert len(result_90) == 91  # 90 天 + 今天

        result_7 = calculate_account_history(account.id, days=7)
        assert len(result_7) == 8  # 7 天 + 今天
