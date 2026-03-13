"""
测试账户汇总逻辑（阶段二）

测试点：
1. 子账户汇总字段计算
2. 无持仓子账户返回 0
3. 缺失估值数据返回 null
4. 父账户汇总 = 所有子账户之和
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestChildAccountSummary:
    """测试子账户汇总字段"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def parent_account(self, user):
        from api.models import Account
        return Account.objects.create(user=user, name='父账户')

    @pytest.fixture
    def child_account(self, user, parent_account):
        from api.models import Account
        return Account.objects.create(user=user, name='子账户', parent=parent_account)

    @pytest.fixture
    def fund_with_estimate(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.5000'),
            estimate_nav=Decimal('1.6000'),
        )

    @pytest.fixture
    def fund_without_estimate(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000002',
            fund_name='无估值基金',
            latest_nav=Decimal('2.0000'),
        )

    def test_child_account_with_single_position(self, child_account, fund_with_estimate):
        """测试子账户单个持仓的汇总"""
        from api.models import Position

        # 创建持仓：100份，成本1000元，持仓净值10元
        Position.objects.create(
            account=child_account,
            fund=fund_with_estimate,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        # 测试基础汇总字段
        assert child_account.holding_cost == Decimal('1000')
        assert child_account.holding_value == Decimal('150')  # 100 * 1.5
        assert child_account.pnl == Decimal('-850')  # 150 - 1000
        assert child_account.pnl_rate == Decimal('-0.85')  # -850 / 1000

        # 测试估值相关字段
        assert child_account.estimate_value == Decimal('160')  # 100 * 1.6
        assert child_account.estimate_pnl == Decimal('-840')  # 160 - 1000
        assert child_account.estimate_pnl_rate == Decimal('-0.84')  # -840 / 1000

        # 测试今日盈亏
        assert child_account.today_pnl == Decimal('10')  # 100 * (1.6 - 1.5)
        assert child_account.today_pnl_rate == Decimal('0.0667')  # 10 / 150

    def test_child_account_with_multiple_positions(self, child_account, fund_with_estimate, fund_without_estimate):
        """测试子账户多个持仓的汇总"""
        from api.models import Position

        # 持仓1：100份，成本1000元
        Position.objects.create(
            account=child_account,
            fund=fund_with_estimate,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        # 持仓2：50份，成本1000元
        Position.objects.create(
            account=child_account,
            fund=fund_without_estimate,
            holding_share=Decimal('50'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('20'),
        )

        # 测试汇总
        assert child_account.holding_cost == Decimal('2000')  # 1000 + 1000
        assert child_account.holding_value == Decimal('250')  # 100*1.5 + 50*2.0
        assert child_account.pnl == Decimal('-1750')  # 250 - 2000
        assert child_account.pnl_rate == Decimal('-0.875')  # -1750 / 2000

    def test_child_account_without_positions(self, child_account):
        """测试无持仓子账户返回 0"""
        assert child_account.holding_cost == Decimal('0')
        assert child_account.holding_value == Decimal('0')
        assert child_account.pnl == Decimal('0')
        assert child_account.pnl_rate is None  # 无持仓时收益率为 None
        assert child_account.estimate_value == Decimal('0')
        assert child_account.estimate_pnl == Decimal('0')
        assert child_account.estimate_pnl_rate is None
        assert child_account.today_pnl == Decimal('0')
        assert child_account.today_pnl_rate is None

    def test_child_account_missing_estimate_nav(self, child_account, fund_without_estimate):
        """测试全部持仓缺失估值时，估值相关字段返回 0"""
        from api.models import Position

        Position.objects.create(
            account=child_account,
            fund=fund_without_estimate,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        # 基础字段正常
        assert child_account.holding_cost == Decimal('1000')
        assert child_account.holding_value == Decimal('200')  # 100 * 2.0

        # 全部持仓缺失估值，估值相关字段返回 0（不影响显示，前端显示 '-'）
        assert child_account.estimate_value == Decimal('0')
        assert child_account.today_pnl == Decimal('0')

    def test_child_account_partial_estimate_data(self, child_account, fund_with_estimate, fund_without_estimate):
        """测试部分持仓缺失估值数据"""
        from api.models import Position

        # 持仓1：有估值
        Position.objects.create(
            account=child_account,
            fund=fund_with_estimate,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        # 持仓2：无估值
        Position.objects.create(
            account=child_account,
            fund=fund_without_estimate,
            holding_share=Decimal('50'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('20'),
        )

        # 基础字段正常
        assert child_account.holding_cost == Decimal('2000')
        assert child_account.holding_value == Decimal('250')

        # 部分持仓缺失估值，只汇总有估值的部分
        # fund_with_estimate: 100份 * 1.6 = 160，today_pnl = 100 * (1.6 - 1.5) = 10
        assert child_account.estimate_value == Decimal('160')
        assert child_account.today_pnl == Decimal('10')


@pytest.mark.django_db
class TestParentAccountSummary:
    """测试父账户汇总字段"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def parent_account(self, user):
        from api.models import Account
        return Account.objects.create(user=user, name='父账户')

    @pytest.fixture
    def child1(self, user, parent_account):
        from api.models import Account
        return Account.objects.create(user=user, name='子账户1', parent=parent_account)

    @pytest.fixture
    def child2(self, user, parent_account):
        from api.models import Account
        return Account.objects.create(user=user, name='子账户2', parent=parent_account)

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.5000'),
            estimate_nav=Decimal('1.6000'),
        )

    def test_parent_account_summary(self, parent_account, child1, child2, fund):
        """测试父账户汇总 = 所有子账户之和"""
        from api.models import Position

        # 子账户1的持仓
        Position.objects.create(
            account=child1,
            fund=fund,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        # 子账户2的持仓
        Position.objects.create(
            account=child2,
            fund=fund,
            holding_share=Decimal('200'),
            holding_cost=Decimal('2000'),
            holding_nav=Decimal('10'),
        )

        # 父账户汇总 = 子账户1 + 子账户2
        assert parent_account.holding_cost == Decimal('3000')  # 1000 + 2000
        assert parent_account.holding_value == Decimal('450')  # 150 + 300
        assert parent_account.pnl == Decimal('-2550')  # -850 + (-1700)
        assert parent_account.pnl_rate == Decimal('-0.85')  # -2550 / 3000

        assert parent_account.estimate_value == Decimal('480')  # 160 + 320
        assert parent_account.estimate_pnl == Decimal('-2520')  # -840 + (-1680)
        assert parent_account.estimate_pnl_rate == Decimal('-0.84')  # -2520 / 3000

        assert parent_account.today_pnl == Decimal('30')  # 10 + 20
        assert parent_account.today_pnl_rate == Decimal('0.0667')  # 30 / 450

    def test_parent_account_without_children(self, parent_account):
        """测试无子账户的父账户返回 0"""
        assert parent_account.holding_cost == Decimal('0')
        assert parent_account.holding_value == Decimal('0')
        assert parent_account.pnl == Decimal('0')
        assert parent_account.pnl_rate is None
        assert parent_account.estimate_value == Decimal('0')
        assert parent_account.estimate_pnl == Decimal('0')
        assert parent_account.estimate_pnl_rate is None
        assert parent_account.today_pnl == Decimal('0')
        assert parent_account.today_pnl_rate is None

    def test_parent_account_with_empty_children(self, parent_account, child1, child2):
        """测试子账户无持仓时父账户返回 0"""
        assert parent_account.holding_cost == Decimal('0')
        assert parent_account.holding_value == Decimal('0')
        assert parent_account.pnl == Decimal('0')
        assert parent_account.pnl_rate is None

