"""
测试基金对比 API

测试点：
1. compare API 返回多只基金的指标数据
2. 无历史数据的基金降级返回
3. 超 5 只返回错误
4. 单只基金返回提示
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.test import Client
from api.models import Fund, FundNavHistory


def _create_nav_history(fund, days=365, start_nav=1.0):
    """批量创建历史净值数据"""
    navs = []
    import random

    random.seed(42)
    for i in range(days):
        d = date.today() - timedelta(days=days - i)
        change = (random.random() - 0.48) * 0.02  # 微小波动
        start_nav = start_nav * (1 + change)
        navs.append(
            FundNavHistory(
                fund=fund,
                nav_date=d,
                unit_nav=Decimal(str(round(start_nav, 4))),
            )
        )
    FundNavHistory.objects.bulk_create(navs)


@pytest.mark.django_db
class TestCompareAPI:
    def test_compare_two_funds(self):
        f1 = Fund.objects.create(
            fund_code="000001", fund_name="基金A", fund_type="混合型"
        )
        f2 = Fund.objects.create(
            fund_code="161725", fund_name="基金B", fund_type="股票型"
        )
        _create_nav_history(f1, days=365)
        _create_nav_history(f2, days=365)

        client = Client()
        resp = client.get("/api/funds/compare/?codes=000001,161725")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["funds"]) == 2
        for f in data["funds"]:
            assert "fund_code" in f
            assert "returns" in f
            assert "metrics" in f
            assert "1m" in f["returns"]
            assert "1y" in f["returns"]
            assert "max_drawdown" in f["metrics"]
            assert "volatility" in f["metrics"]

    def test_no_nav_history_returns_empty_metrics(self):
        f1 = Fund.objects.create(
            fund_code="000001", fund_name="基金A", fund_type="混合型"
        )
        f2 = Fund.objects.create(
            fund_code="161725", fund_name="基金B", fund_type="股票型"
        )
        # 不给 f2 创建 nav history
        _create_nav_history(f1, days=365)

        client = Client()
        resp = client.get("/api/funds/compare/?codes=000001,161725")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["funds"]) == 2
        # f2 没有历史数据，指标应为 null
        f2_data = [f for f in data["funds"] if f["fund_code"] == "161725"][0]
        assert f2_data["returns"]["1m"] is None

    def test_over_five_funds_error(self):
        codes = ",".join([str(i).zfill(6) for i in range(6)])
        for code in codes.split(","):
            Fund.objects.create(fund_code=code, fund_name=f"基金{code}")

        client = Client()
        resp = client.get(f"/api/funds/compare/?codes={codes}")
        assert resp.status_code == 400

    def test_single_fund_returns_error(self):
        Fund.objects.create(fund_code="000001", fund_name="基金A")
        client = Client()
        resp = client.get("/api/funds/compare/?codes=000001")
        assert resp.status_code == 400

    def test_nonexistent_fund_skipped(self):
        f1 = Fund.objects.create(fund_code="000001", fund_name="基金A")
        _create_nav_history(f1, days=365)

        client = Client()
        resp = client.get("/api/funds/compare/?codes=000001,999999")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["funds"]) == 1  # 999999 不存在，跳过
