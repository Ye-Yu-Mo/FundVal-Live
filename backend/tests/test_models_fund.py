"""
测试 Fund 模型

测试点：
1. 基金创建
2. fund_code 唯一性
3. 净值更新
"""

import pytest
from decimal import Decimal
from datetime import date
from django.db import IntegrityError
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestFundModel:
    """Fund 模型测试"""

    def test_create_fund(self):
        """测试创建基金"""
        from api.models import Fund

        fund = Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
            fund_type="混合型",
        )

        assert fund.fund_code == "000001"
        assert fund.fund_name == "华夏成长混合"
        assert fund.fund_type == "混合型"
        assert fund.latest_nav is None
        assert fund.latest_nav_date is None

    def test_fund_code_unique(self):
        """测试基金代码唯一性"""
        from api.models import Fund

        Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
        )

        # 重复的 fund_code 应该报错
        with pytest.raises(IntegrityError):
            Fund.objects.create(
                fund_code="000001",
                fund_name="重复基金",
            )

    def test_update_nav(self):
        """测试更新净值"""
        from api.models import Fund

        fund = Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
        )

        # 更新净值
        fund.latest_nav = Decimal("1.5000")
        fund.latest_nav_date = date(2024, 2, 11)
        fund.save()

        # 重新查询验证
        fund.refresh_from_db()
        assert fund.latest_nav == Decimal("1.5000")
        assert fund.latest_nav_date == date(2024, 2, 11)

    def test_fund_str_representation(self):
        """测试基金字符串表示"""
        from api.models import Fund

        fund = Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
        )

        # 应该返回有意义的字符串
        assert "000001" in str(fund) or "华夏成长混合" in str(fund)
