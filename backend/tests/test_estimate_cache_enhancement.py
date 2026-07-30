"""
测试 M2 功能3: 估值缓存增强

- Fund.estimate_source 字段存在且可写
- batch_estimate 写入 estimate_source
- 收盘后 (15:00+) 返回 estimate_stale: true
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestEstimateSourceField:
    """Fund.estimate_source 字段"""

    def test_field_exists(self):
        """Fund 模型应有 estimate_source 字段"""
        from api.models import Fund

        assert hasattr(Fund, "estimate_source"), "Fund 模型应有 estimate_source 字段"

    def test_field_nullable(self):
        """estimate_source 可为 None（默认值）"""
        from api.models import Fund

        fund = Fund.objects.create(
            fund_code="000001",
            fund_name="测试",
            latest_nav=Decimal("1.1000"),
        )
        assert fund.estimate_source is None

    def test_field_can_be_set(self):
        """estimate_source 可写入"""
        from api.models import Fund

        fund = Fund.objects.create(
            fund_code="000001",
            fund_name="测试",
            latest_nav=Decimal("1.1000"),
            estimate_source="akshare",
        )
        fund.refresh_from_db()
        assert fund.estimate_source == "akshare"

    def test_field_persists_across_saves(self):
        """estimate_source 在 save 后保持"""
        from api.models import Fund

        fund = Fund.objects.create(
            fund_code="000001",
            fund_name="测试",
            latest_nav=Decimal("1.1000"),
        )
        fund.estimate_source = "yangjibao"
        fund.save()
        fund.refresh_from_db()
        assert fund.estimate_source == "yangjibao"


@pytest.mark.django_db
class TestBatchEstimateWritesSource:
    """batch_estimate 写入 estimate_source"""

    def setup_method(self):
        from api.models import Fund

        self.client = APIClient()
        self.fund = Fund.objects.create(
            fund_code="000001",
            fund_name="测试基金",
            latest_nav=Decimal("1.1000"),
        )

    def test_writes_akshare_source(self):
        """akshare 估值 → estimate_source = 'akshare'"""
        with patch("api.sources.eastmoney.EastMoneySource.fetch_estimate") as mock_fetch:
            mock_fetch.return_value = {
                "fund_code": "000001",
                "fund_name": "测试基金",
                "estimate_nav": Decimal("1.1370"),
                "estimate_growth": Decimal("1.0"),
                "estimate_time": timezone.now(),
            }

            self.client.post(
                "/api/funds/batch_estimate/",
                {"fund_codes": ["000001"]},
                format="json",
            )

        self.fund.refresh_from_db()
        assert self.fund.estimate_source is not None, "batch_estimate 应写入 estimate_source"


@pytest.mark.django_db
class TestEstimateStaleAfterMarketClose:
    """收盘后估值标记 stale"""

    def setup_method(self):
        from api.models import Fund

        self.client = APIClient()
        self.fund = Fund.objects.create(
            fund_code="000001",
            fund_name="测试基金",
            latest_nav=Decimal("1.1000"),
            estimate_nav=Decimal("1.1370"),
            estimate_growth=Decimal("1.0"),
            estimate_time=timezone.now(),
        )

    def test_stale_after_1500(self):
        """15:00 后缓存命中 → estimate_stale: true"""
        # 构造 15:01 的时间，估值时间在 5 分钟 TTL 内
        stale_time = timezone.now().replace(hour=15, minute=1, second=0, microsecond=0)
        # 让估值时间等于 stale_time（刚缓存），TTL 内命中
        self.fund.estimate_time = stale_time
        self.fund.save()

        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = stale_time

            response = self.client.post(
                "/api/funds/batch_estimate/",
                {"fund_codes": ["000001"]},
                format="json",
            )

        assert response.status_code == 200
        data = response.json()
        assert data["000001"].get("from_cache") is True, "缓存应命中"
        assert data["000001"].get("estimate_stale") is True, (
            f"15:00 后应有 estimate_stale: true, 实际: {data['000001']}"
        )

    def test_not_stale_before_1500(self):
        """15:00 前缓存命中 → 无 estimate_stale 标记"""
        # 构造 14:30 的时间，估值刚写入
        fresh_time = timezone.now().replace(hour=14, minute=30, second=0, microsecond=0)
        self.fund.estimate_time = fresh_time
        self.fund.save()

        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = fresh_time

            response = self.client.post(
                "/api/funds/batch_estimate/",
                {"fund_codes": ["000001"]},
                format="json",
            )

        assert response.status_code == 200
        data = response.json()
        assert data["000001"].get("from_cache") is True, "缓存应命中"
        assert data["000001"].get("estimate_stale") is not True, (
            f"15:00 前不应有 estimate_stale: true, 实际: {data['000001']}"
        )

    def test_stale_when_fresh_fetch_after_1500(self):
        """15:00 后即使新抓取（非缓存），也应标记 stale — 估值不会再更新了"""
        stale_time = timezone.now().replace(hour=15, minute=1, second=0, microsecond=0)
        # 估值时间是 10 分钟前 → 缓存过期，会走 fresh fetch
        self.fund.estimate_time = stale_time - timedelta(minutes=10)
        self.fund.save()

        with patch("django.utils.timezone.now") as mock_now:
            mock_now.return_value = stale_time

            with patch("api.sources.eastmoney.EastMoneySource.fetch_estimate") as mock_fetch:
                mock_fetch.return_value = {
                    "fund_code": "000001",
                    "fund_name": "测试基金",
                    "estimate_nav": Decimal("1.1500"),
                    "estimate_growth": Decimal("2.0"),
                    "estimate_time": stale_time,
                }

                response = self.client.post(
                    "/api/funds/batch_estimate/",
                    {"fund_codes": ["000001"]},
                    format="json",
                )

        assert response.status_code == 200
        data = response.json()
        assert data["000001"].get("from_cache") is False, "缓存过期，应新获取"
        # 15:00 后即使新获取，估值也是收盘估值，不再更新
        assert data["000001"].get("estimate_stale") is True, "15:00 后新抓取估值也应标记 stale"
