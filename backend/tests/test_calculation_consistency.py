"""
测试 Position 汇总和历史市值计算的一致性

确保两种计算方式得到相同的结果
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestCalculationConsistency:
    """测试计算一致性"""

    @pytest.fixture
    def user(self):
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
            latest_nav=Decimal("1.5000"),
        )

    def test_consistency_buy_sell(self, account, fund):
        """测试买入卖出后，Position 汇总和历史市值计算结果一致"""
        from api.models import PositionOperation, Position
        from api.services.position_history import calculate_account_history

        # 创建操作：买入 1000 元，卖出一半
        today = date.today()

        # 买入
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type="BUY",
            operation_date=today - timedelta(days=10),
            amount=Decimal("1000.00"),
            share=Decimal("1000.0000"),
            nav=Decimal("1.0000"),
            before_15=True,
        )

        # 卖出一半
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type="SELL",
            operation_date=today - timedelta(days=5),
            amount=Decimal("600.00"),
            share=Decimal("500.0000"),
            nav=Decimal("1.2000"),
            before_15=True,
        )

        # 获取 Position 汇总数据
        position = Position.objects.get(account=account, fund=fund)
        position_cost = float(position.holding_cost)

        # 获取历史市值数据（今天的成本）
        history = calculate_account_history(account.id, days=1)
        history_cost = history[-1]["cost"]  # 最后一天（今天）的成本

        # 验证两者一致
        assert (
            position_cost == history_cost
        ), f"Position 汇总成本 {position_cost} != 历史市值成本 {history_cost}"

    def test_consistency_multiple_operations(self, account, fund):
        """测试多次买卖后，计算结果一致"""
        from api.models import PositionOperation, Position
        from api.services.position_history import calculate_account_history

        today = date.today()

        # 多次操作
        operations = [
            (
                "BUY",
                today - timedelta(days=20),
                Decimal("1000.00"),
                Decimal("1000.0000"),
                Decimal("1.0000"),
            ),
            (
                "BUY",
                today - timedelta(days=15),
                Decimal("500.00"),
                Decimal("400.0000"),
                Decimal("1.2500"),
            ),
            (
                "SELL",
                today - timedelta(days=10),
                Decimal("420.00"),
                Decimal("300.0000"),
                Decimal("1.4000"),
            ),
            (
                "BUY",
                today - timedelta(days=5),
                Decimal("800.00"),
                Decimal("500.0000"),
                Decimal("1.6000"),
            ),
            (
                "SELL",
                today - timedelta(days=2),
                Decimal("480.00"),
                Decimal("300.0000"),
                Decimal("1.6000"),
            ),
        ]

        for op_type, op_date, amount, share, nav in operations:
            PositionOperation.objects.create(
                account=account,
                fund=fund,
                operation_type=op_type,
                operation_date=op_date,
                amount=amount,
                share=share,
                nav=nav,
                before_15=True,
            )

        # 获取 Position 汇总数据
        position = Position.objects.get(account=account, fund=fund)
        position_cost = float(position.holding_cost)
        position_share = float(position.holding_share)

        # 获取历史市值数据（今天的成本和份额）
        history = calculate_account_history(account.id, days=1)
        history_cost = history[-1]["cost"]

        # 验证成本一致
        assert (
            abs(position_cost - history_cost) < 0.01
        ), f"Position 汇总成本 {position_cost} != 历史市值成本 {history_cost}"

        print(f"✅ Position 汇总成本: {position_cost}")
        print(f"✅ 历史市值成本: {history_cost}")
        print(f"✅ Position 份额: {position_share}")
