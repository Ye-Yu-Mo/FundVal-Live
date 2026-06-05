"""
测试基金历史净值模型
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from api.models import Fund, FundNavHistory


@pytest.mark.django_db
class TestFundNavHistoryModel:
    """测试 FundNavHistory 模型"""

    @pytest.fixture
    def fund(self):
        """创建测试基金"""
        return Fund.objects.create(
            fund_code="000001",
            fund_name="测试基金",
            fund_type="混合型",
        )

    def test_create_nav_history(self, fund):
        """测试创建历史净值记录"""
        nav = FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
            accumulated_nav=Decimal("2.3456"),
            daily_growth=Decimal("1.23"),
        )

        assert nav.fund == fund
        assert nav.nav_date == date(2024, 1, 1)
        assert nav.unit_nav == Decimal("1.2345")
        assert nav.accumulated_nav == Decimal("2.3456")
        assert nav.daily_growth == Decimal("1.23")

    def test_nav_history_str(self, fund):
        """测试 __str__ 方法"""
        nav = FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
        )

        assert str(nav) == "000001 - 2024-01-01"

    def test_unique_together_constraint(self, fund):
        """测试 unique_together 约束：同一基金同一日期只能有一条记录"""
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
        )

        # 尝试创建相同基金相同日期的记录
        with pytest.raises(IntegrityError):
            FundNavHistory.objects.create(
                fund=fund,
                nav_date=date(2024, 1, 1),
                unit_nav=Decimal("1.3456"),
            )

    def test_optional_fields(self, fund):
        """测试可选字段：accumulated_nav 和 daily_growth 可以为空"""
        nav = FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
        )

        assert nav.accumulated_nav is None
        assert nav.daily_growth is None

    def test_ordering(self, fund):
        """测试默认排序：按日期倒序"""
        nav1 = FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
        )
        nav2 = FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 3),
            unit_nav=Decimal("1.3456"),
        )
        nav3 = FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 2),
            unit_nav=Decimal("1.2890"),
        )

        navs = list(FundNavHistory.objects.filter(fund=fund))
        assert navs[0] == nav2  # 2024-01-03
        assert navs[1] == nav3  # 2024-01-02
        assert navs[2] == nav1  # 2024-01-01

    def test_cascade_delete(self, fund):
        """测试级联删除：删除基金时删除所有历史净值"""
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
        )
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 2),
            unit_nav=Decimal("1.2890"),
        )

        assert FundNavHistory.objects.filter(fund=fund).count() == 2

        fund_id = fund.id
        fund.delete()

        # 使用 fund_id 查询，因为 fund 对象已被删除
        assert FundNavHistory.objects.filter(fund_id=fund_id).count() == 0

    def test_query_by_date_range(self, fund):
        """测试按日期范围查询"""
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
        )
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 15),
            unit_nav=Decimal("1.3456"),
        )
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 31),
            unit_nav=Decimal("1.4567"),
        )

        # 查询 1月1日到1月20日
        navs = FundNavHistory.objects.filter(
            fund=fund,
            nav_date__gte=date(2024, 1, 1),
            nav_date__lte=date(2024, 1, 20),
        )

        assert navs.count() == 2
        assert navs[0].nav_date == date(2024, 1, 15)
        assert navs[1].nav_date == date(2024, 1, 1)

    def test_query_by_single_date(self, fund):
        """测试按单日查询"""
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
        )
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 2),
            unit_nav=Decimal("1.2890"),
        )

        nav = FundNavHistory.objects.get(
            fund=fund,
            nav_date=date(2024, 1, 1),
        )

        assert nav.unit_nav == Decimal("1.2345")

    def test_multiple_funds(self):
        """测试多个基金的历史净值"""
        fund1 = Fund.objects.create(
            fund_code="000001",
            fund_name="基金1",
        )
        fund2 = Fund.objects.create(
            fund_code="000002",
            fund_name="基金2",
        )

        FundNavHistory.objects.create(
            fund=fund1,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
        )
        FundNavHistory.objects.create(
            fund=fund2,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("2.3456"),
        )

        # 同一天不同基金可以有各自的记录
        assert FundNavHistory.objects.filter(nav_date=date(2024, 1, 1)).count() == 2

        # 按基金查询
        assert FundNavHistory.objects.filter(fund=fund1).count() == 1
        assert FundNavHistory.objects.filter(fund=fund2).count() == 1

    def test_decimal_precision(self, fund):
        """测试 Decimal 精度"""
        nav = FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.23456789"),  # 超过 4 位小数
            accumulated_nav=Decimal("2.34567890"),
            daily_growth=Decimal("1.234567"),
        )

        # 重新从数据库读取
        nav.refresh_from_db()

        # 验证精度被正确保存（4 位小数）
        assert nav.unit_nav == Decimal("1.2346")  # 四舍五入
        assert nav.accumulated_nav == Decimal("2.3457")
        assert nav.daily_growth == Decimal("1.2346")

    def test_update_or_create(self, fund):
        """测试 update_or_create 方法"""
        # 首次创建
        nav, created = FundNavHistory.objects.update_or_create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            defaults={
                "unit_nav": Decimal("1.2345"),
                "accumulated_nav": Decimal("2.3456"),
            },
        )

        assert created is True
        assert nav.unit_nav == Decimal("1.2345")

        # 更新已存在的记录
        nav, created = FundNavHistory.objects.update_or_create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            defaults={
                "unit_nav": Decimal("1.3456"),
                "accumulated_nav": Decimal("2.4567"),
            },
        )

        assert created is False
        assert nav.unit_nav == Decimal("1.3456")
        assert nav.accumulated_nav == Decimal("2.4567")

        # 验证只有一条记录
        assert FundNavHistory.objects.filter(fund=fund).count() == 1

    def test_bulk_create(self, fund):
        """测试批量创建"""
        navs = [
            FundNavHistory(
                fund=fund,
                nav_date=date(2024, 1, i),
                unit_nav=Decimal(f"1.{i:04d}"),
            )
            for i in range(1, 11)
        ]

        FundNavHistory.objects.bulk_create(navs)

        assert FundNavHistory.objects.filter(fund=fund).count() == 10

    def test_related_name(self, fund):
        """测试反向关联：fund.nav_history"""
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 1),
            unit_nav=Decimal("1.2345"),
        )
        FundNavHistory.objects.create(
            fund=fund,
            nav_date=date(2024, 1, 2),
            unit_nav=Decimal("1.2890"),
        )

        # 通过 fund 访问历史净值
        navs = fund.nav_history.all()

        assert navs.count() == 2
        assert navs[0].nav_date == date(2024, 1, 2)  # 倒序
        assert navs[1].nav_date == date(2024, 1, 1)
