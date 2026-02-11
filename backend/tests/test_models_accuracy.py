"""
测试 EstimateAccuracy 模型

测试点：
1. 准确率记录创建
2. 误差率计算
3. 唯一性约束
"""
import pytest
from decimal import Decimal
from datetime import date
from django.db import IntegrityError
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestEstimateAccuracyModel:
    """EstimateAccuracy 模型测试"""

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='华夏成长混合',
        )

    def test_create_accuracy_record(self, fund):
        """测试创建准确率记录"""
        from api.models import EstimateAccuracy

        record = EstimateAccuracy.objects.create(
            source_name='eastmoney',
            fund=fund,
            estimate_date=date(2024, 2, 11),
            estimate_nav=Decimal('1.1370'),
        )

        assert record.source_name == 'eastmoney'
        assert record.fund == fund
        assert record.estimate_date == date(2024, 2, 11)
        assert record.estimate_nav == Decimal('1.1370')
        assert record.actual_nav is None
        assert record.error_rate is None

    def test_calculate_error_rate(self, fund):
        """测试计算误差率"""
        from api.models import EstimateAccuracy

        record = EstimateAccuracy.objects.create(
            source_name='eastmoney',
            fund=fund,
            estimate_date=date(2024, 2, 11),
            estimate_nav=Decimal('1.1370'),
            actual_nav=Decimal('1.1490'),
        )

        record.calculate_error_rate()

        # 误差率 = |1.1370 - 1.1490| / 1.1490 ≈ 0.010444
        assert record.error_rate is not None
        assert abs(record.error_rate - Decimal('0.010444')) < Decimal('0.000001')

    def test_calculate_error_rate_zero_actual(self, fund):
        """测试实际净值为 0 时不计算误差率"""
        from api.models import EstimateAccuracy

        record = EstimateAccuracy.objects.create(
            source_name='eastmoney',
            fund=fund,
            estimate_date=date(2024, 2, 11),
            estimate_nav=Decimal('1.1370'),
            actual_nav=Decimal('0'),
        )

        record.calculate_error_rate()

        # 实际净值为 0，不计算误差率
        assert record.error_rate is None

    def test_unique_constraint(self, fund):
        """测试唯一性约束：同一数据源、同一基金、同一日期只能有一条记录"""
        from api.models import EstimateAccuracy

        EstimateAccuracy.objects.create(
            source_name='eastmoney',
            fund=fund,
            estimate_date=date(2024, 2, 11),
            estimate_nav=Decimal('1.1370'),
        )

        # 重复创建应该报错
        with pytest.raises(IntegrityError):
            EstimateAccuracy.objects.create(
                source_name='eastmoney',
                fund=fund,
                estimate_date=date(2024, 2, 11),
                estimate_nav=Decimal('1.1400'),
            )

    def test_different_sources_same_fund_date(self, fund):
        """测试不同数据源可以有相同基金和日期的记录"""
        from api.models import EstimateAccuracy

        record1 = EstimateAccuracy.objects.create(
            source_name='eastmoney',
            fund=fund,
            estimate_date=date(2024, 2, 11),
            estimate_nav=Decimal('1.1370'),
        )

        record2 = EstimateAccuracy.objects.create(
            source_name='tiantian',
            fund=fund,
            estimate_date=date(2024, 2, 11),
            estimate_nav=Decimal('1.1380'),
        )

        assert record1.source_name != record2.source_name
        assert record1.fund == record2.fund
        assert record1.estimate_date == record2.estimate_date

    def test_same_source_different_dates(self, fund):
        """测试同一数据源可以有不同日期的记录"""
        from api.models import EstimateAccuracy

        record1 = EstimateAccuracy.objects.create(
            source_name='eastmoney',
            fund=fund,
            estimate_date=date(2024, 2, 11),
            estimate_nav=Decimal('1.1370'),
        )

        record2 = EstimateAccuracy.objects.create(
            source_name='eastmoney',
            fund=fund,
            estimate_date=date(2024, 2, 12),
            estimate_nav=Decimal('1.1400'),
        )

        assert record1.estimate_date != record2.estimate_date

    def test_str_representation(self, fund):
        """测试字符串表示"""
        from api.models import EstimateAccuracy

        record = EstimateAccuracy.objects.create(
            source_name='eastmoney',
            fund=fund,
            estimate_date=date(2024, 2, 11),
            estimate_nav=Decimal('1.1370'),
        )

        str_repr = str(record)
        assert 'eastmoney' in str_repr
        assert '000001' in str_repr
        assert '2024-02-11' in str_repr
