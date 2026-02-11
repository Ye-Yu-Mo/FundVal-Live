"""
测试 Position 和 PositionOperation 模型

测试点：
1. 持仓创建
2. 持仓操作流水
3. 持仓汇总计算
4. 建仓/加仓/减仓逻辑
"""
import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestPositionModel:
    """Position 模型测试"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user):
        from api.models import Account
        # 创建父账户
        parent = Account.objects.create(user=user, name='父账户')
        # 创建子账户（用于持仓）
        return Account.objects.create(user=user, name='测试账户', parent=parent)

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='华夏成长混合',
            latest_nav=Decimal('1.5000'),
        )

    def test_create_position(self, account, fund):
        """测试创建持仓"""
        from api.models import Position

        position = Position.objects.create(
            account=account,
            fund=fund,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        assert position.account == account
        assert position.fund == fund
        assert position.holding_share == Decimal('100')
        assert position.holding_cost == Decimal('1000')
        assert position.holding_nav == Decimal('10')

    def test_position_unique_per_account_fund(self, account, fund):
        """测试同一账户同一基金只能有一个持仓"""
        from api.models import Position
        from django.db import IntegrityError
        from django.core.exceptions import ValidationError

        Position.objects.create(
            account=account,
            fund=fund,
            holding_share=Decimal('100'),
        )

        # 重复创建应该报错
        with pytest.raises((IntegrityError, ValidationError)):
            Position.objects.create(
                account=account,
                fund=fund,
                holding_share=Decimal('200'),
            )


@pytest.mark.django_db
class TestPositionOperationModel:
    """PositionOperation 模型测试"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user):
        from api.models import Account
        # 创建父账户
        parent = Account.objects.create(user=user, name='父账户')
        # 创建子账户（用于持仓）
        return Account.objects.create(user=user, name='测试账户', parent=parent)

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='华夏成长混合',
        )

    def test_create_buy_operation(self, account, fund):
        """测试创建买入操作"""
        from api.models import PositionOperation

        operation = PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            before_15=True,
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        assert operation.operation_type == 'BUY'
        assert operation.amount == Decimal('1000')
        assert operation.share == Decimal('100')
        assert operation.nav == Decimal('10')
        assert operation.before_15 is True

    def test_create_sell_operation(self, account, fund):
        """测试创建卖出操作"""
        from api.models import PositionOperation

        operation = PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='SELL',
            operation_date=date(2024, 2, 11),
            before_15=False,
            amount=Decimal('500'),
            share=Decimal('50'),
            nav=Decimal('10'),
        )

        assert operation.operation_type == 'SELL'
        assert operation.before_15 is False

    def test_operations_ordering(self, account, fund):
        """测试操作按日期排序"""
        from api.models import PositionOperation

        op1 = PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 12),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        op2 = PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('500'),
            share=Decimal('50'),
            nav=Decimal('10'),
        )

        operations = list(PositionOperation.objects.all())
        # 应该按日期升序排列
        assert operations[0] == op2  # 2月11日
        assert operations[1] == op1  # 2月12日


@pytest.mark.django_db
class TestPositionCalculation:
    """持仓计算逻辑测试"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user):
        from api.models import Account
        # 创建父账户
        parent = Account.objects.create(user=user, name='父账户')
        # 创建子账户（用于持仓）
        return Account.objects.create(user=user, name='测试账户', parent=parent)

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='华夏成长混合',
            latest_nav=Decimal('1.5000'),
        )

    def test_single_buy_calculation(self, account, fund):
        """测试单次建仓计算"""
        from api.models import PositionOperation
        from api.services import recalculate_position

        # 建仓：1000元买入100份，净值10元
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        position = recalculate_position(account.id, fund.id)

        assert position.holding_share == Decimal('100')
        assert position.holding_cost == Decimal('1000')
        assert position.holding_nav == Decimal('10')

    def test_multiple_buy_calculation(self, account, fund):
        """测试多次加仓计算"""
        from api.models import PositionOperation
        from api.services import recalculate_position

        # 第一次：1000元买入100份，净值10元
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        # 第二次：1200元买入100份，净值12元
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 12),
            amount=Decimal('1200'),
            share=Decimal('100'),
            nav=Decimal('12'),
        )

        position = recalculate_position(account.id, fund.id)

        assert position.holding_share == Decimal('200')
        assert position.holding_cost == Decimal('2200')
        # 加权平均净值：(1000 + 1200) / 200 = 11
        assert position.holding_nav == Decimal('11')

    def test_buy_and_sell_calculation(self, account, fund):
        """测试买入后卖出计算"""
        from api.models import PositionOperation
        from api.services import recalculate_position

        # 买入：1000元买入100份
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        # 卖出：600元卖出50份
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='SELL',
            operation_date=date(2024, 2, 12),
            amount=Decimal('600'),
            share=Decimal('50'),
            nav=Decimal('12'),
        )

        position = recalculate_position(account.id, fund.id)

        assert position.holding_share == Decimal('50')
        # 成本按比例减少：1000 - (1000/100 * 50) = 500
        assert position.holding_cost == Decimal('500')
        assert position.holding_nav == Decimal('10')

    def test_sell_all_calculation(self, account, fund):
        """测试全部卖出计算"""
        from api.models import PositionOperation
        from api.services import recalculate_position

        # 买入
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        # 全部卖出
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='SELL',
            operation_date=date(2024, 2, 12),
            amount=Decimal('1200'),
            share=Decimal('100'),
            nav=Decimal('12'),
        )

        position = recalculate_position(account.id, fund.id)

        assert position.holding_share == Decimal('0')
        assert position.holding_cost == Decimal('0')
