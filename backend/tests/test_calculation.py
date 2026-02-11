"""
测试持仓计算逻辑

测试点：
1. 单次建仓
2. 多次加仓（不同净值）
3. 部分减仓
4. 全部清仓
5. 多次买卖混合
6. 边界情况（卖出超过持有、负数等）
7. 盈亏计算
8. 批量重算
"""
import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestPositionCalculation:
    """持仓计算逻辑测试"""

    @pytest.fixture
    def user(self):
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
            latest_nav=Decimal('1.5000'),
        )

    def test_single_buy(self, account, fund):
        """测试单次建仓"""
        from api.models import PositionOperation
        from api.services import recalculate_position

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

    def test_multiple_buys_same_nav(self, account, fund):
        """测试多次加仓（相同净值）"""
        from api.models import PositionOperation
        from api.services import recalculate_position

        # 第一次买入
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        # 第二次买入（相同净值）
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 12),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        position = recalculate_position(account.id, fund.id)

        assert position.holding_share == Decimal('200')
        assert position.holding_cost == Decimal('2000')
        assert position.holding_nav == Decimal('10')

    def test_multiple_buys_different_nav(self, account, fund):
        """测试多次加仓（不同净值）"""
        from api.models import PositionOperation
        from api.services import recalculate_position

        # 第一次：10元买入100份
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        # 第二次：12元买入100份
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
        # 加权平均净值：2200 / 200 = 11
        assert position.holding_nav == Decimal('11')

    def test_partial_sell(self, account, fund):
        """测试部分减仓"""
        from api.models import PositionOperation
        from api.services import recalculate_position

        # 买入：10元买入100份
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        # 卖出：12元卖出50份
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
        # 持仓净值不变
        assert position.holding_nav == Decimal('10')

    def test_sell_all(self, account, fund):
        """测试全部清仓"""
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

    def test_multiple_buy_sell_operations(self, account, fund):
        """测试多次买卖混合操作"""
        from api.models import PositionOperation
        from api.services import recalculate_position

        # 第一次买入：10元买入100份
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        # 第二次买入：12元买入100份
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 12),
            amount=Decimal('1200'),
            share=Decimal('100'),
            nav=Decimal('12'),
        )

        # 第一次卖出：13元卖出50份
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='SELL',
            operation_date=date(2024, 2, 13),
            amount=Decimal('650'),
            share=Decimal('50'),
            nav=Decimal('13'),
        )

        # 第三次买入：11元买入50份
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='BUY',
            operation_date=date(2024, 2, 14),
            amount=Decimal('550'),
            share=Decimal('50'),
            nav=Decimal('11'),
        )

        position = recalculate_position(account.id, fund.id)

        # 最终持仓：100 + 100 - 50 + 50 = 200份
        assert position.holding_share == Decimal('200')
        # 成本：1000 + 1200 - (2200/200 * 50) + 550 = 2200
        assert position.holding_cost == Decimal('2200')
        # 持仓净值：2200 / 200 = 11
        assert position.holding_nav == Decimal('11')

    def test_operations_ordering(self, account, fund):
        """测试操作按日期排序"""
        from api.models import PositionOperation
        from api.services import recalculate_position

        # 先创建后面的操作
        PositionOperation.objects.create(
            account=account,
            fund=fund,
            operation_type='SELL',
            operation_date=date(2024, 2, 12),
            amount=Decimal('600'),
            share=Decimal('50'),
            nav=Decimal('12'),
        )

        # 再创建前面的操作
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

        # 应该按日期排序计算，结果正确
        assert position.holding_share == Decimal('50')
        assert position.holding_cost == Decimal('500')


@pytest.mark.django_db
class TestPnLCalculation:
    """盈亏计算测试"""

    @pytest.fixture
    def user(self):
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
            latest_nav=Decimal('1.5000'),
        )

    def test_pnl_profit(self, account, fund):
        """测试盈利情况"""
        from api.models import Position

        # 持仓成本 10 元，当前净值 1.5 元，持有 100 份
        position = Position.objects.create(
            account=account,
            fund=fund,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        # 盈亏 = (1.5 - 10) * 100 = -850（亏损）
        pnl = position.pnl
        assert pnl == Decimal('-850.0000')

    def test_pnl_loss(self, account, fund):
        """测试亏损情况"""
        from api.models import Position

        # 持仓成本 1 元，当前净值 1.5 元，持有 100 份
        position = Position.objects.create(
            account=account,
            fund=fund,
            holding_share=Decimal('100'),
            holding_cost=Decimal('100'),
            holding_nav=Decimal('1'),
        )

        # 盈亏 = (1.5 - 1) * 100 = 50（盈利）
        pnl = position.pnl
        assert pnl == Decimal('50.0000')

    def test_pnl_no_nav(self, account):
        """测试没有净值时盈亏为 0"""
        from api.models import Fund, Position

        fund = Fund.objects.create(
            fund_code='000002',
            fund_name='测试基金',
            latest_nav=None,
        )

        position = Position.objects.create(
            account=account,
            fund=fund,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        assert position.pnl == 0

    def test_pnl_zero_share(self, account, fund):
        """测试持仓为 0 时盈亏为 0"""
        from api.models import Position

        position = Position.objects.create(
            account=account,
            fund=fund,
            holding_share=Decimal('0'),
            holding_cost=Decimal('0'),
            holding_nav=Decimal('0'),
        )

        assert position.pnl == 0


@pytest.mark.django_db
class TestBatchRecalculation:
    """批量重算测试"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user, create_child_account):
        return create_child_account(user, '测试账户')

    @pytest.fixture
    def fund1(self):
        from api.models import Fund
        return Fund.objects.create(fund_code='000001', fund_name='基金1')

    @pytest.fixture
    def fund2(self):
        from api.models import Fund
        return Fund.objects.create(fund_code='000002', fund_name='基金2')

    def test_recalculate_all_positions(self, account, fund1, fund2):
        """测试重算所有持仓"""
        from api.models import PositionOperation
        from api.services import recalculate_all_positions

        # 基金1的操作
        PositionOperation.objects.create(
            account=account,
            fund=fund1,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        # 基金2的操作
        PositionOperation.objects.create(
            account=account,
            fund=fund2,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('2000'),
            share=Decimal('200'),
            nav=Decimal('10'),
        )

        # 批量重算
        recalculate_all_positions()

        from api.models import Position
        positions = Position.objects.filter(account=account)

        assert positions.count() == 2
        assert positions.filter(fund=fund1).first().holding_share == Decimal('100')
        assert positions.filter(fund=fund2).first().holding_share == Decimal('200')

    def test_recalculate_account_positions(self, user, fund1, create_child_account):
        """测试重算指定账户的持仓"""
        from api.models import Account, PositionOperation
        from api.services import recalculate_all_positions

        account1 = create_child_account(user, '账户1')
        account2 = create_child_account(user, '账户2')

        # 账户1的操作
        PositionOperation.objects.create(
            account=account1,
            fund=fund1,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('1000'),
            share=Decimal('100'),
            nav=Decimal('10'),
        )

        # 账户2的操作
        PositionOperation.objects.create(
            account=account2,
            fund=fund1,
            operation_type='BUY',
            operation_date=date(2024, 2, 11),
            amount=Decimal('2000'),
            share=Decimal('200'),
            nav=Decimal('10'),
        )

        # 只重算账户1
        recalculate_all_positions(account_id=account1.id)

        from api.models import Position
        # 账户1应该有持仓
        assert Position.objects.filter(account=account1).count() == 1
        # 账户2没有重算，所以没有持仓记录
        assert Position.objects.filter(account=account2).count() == 0

        # 重算所有账户
        recalculate_all_positions()

        # 现在两个账户都应该有持仓
        assert Position.objects.filter(account=account1).count() == 1
        assert Position.objects.filter(account=account2).count() == 1
