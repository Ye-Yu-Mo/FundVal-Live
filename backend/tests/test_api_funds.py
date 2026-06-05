"""
测试基金相关 API

测试点：
1. 基金列表（分页、搜索）
2. 基金详情
3. 获取估值
4. 获取准确率
5. 同步基金列表（管理员）
"""

import pytest
from decimal import Decimal
from datetime import date
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestFundListAPI:
    """测试基金列表 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def admin_user(self):
        return User.objects.create_superuser(username="admin", password="pass")

    @pytest.fixture
    def funds(self):
        from api.models import Fund

        return [
            Fund.objects.create(
                fund_code="000001", fund_name="华夏成长混合", fund_type="混合型"
            ),
            Fund.objects.create(
                fund_code="000002", fund_name="华夏大盘精选", fund_type="混合型"
            ),
            Fund.objects.create(
                fund_code="110022", fund_name="易方达消费行业", fund_type="股票型"
            ),
        ]

    def test_list_funds_unauthenticated(self, client, funds):
        """测试未认证用户可以查看基金列表"""
        response = client.get("/api/funds/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 3

    def test_list_funds_with_pagination(self, client, funds):
        """测试分页"""
        response = client.get("/api/funds/?page_size=2")
        assert response.status_code == 200
        assert len(response.data["results"]) == 2
        assert response.data["count"] == 3

    def test_search_funds_by_code(self, client, funds):
        """测试按代码搜索"""
        response = client.get("/api/funds/?search=000001")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["fund_code"] == "000001"

    def test_search_funds_by_name(self, client, funds):
        """测试按名称搜索"""
        response = client.get("/api/funds/?search=华夏")
        assert response.status_code == 200
        assert len(response.data["results"]) == 2

    def test_filter_funds_by_type(self, client, funds):
        """测试按类型过滤"""
        response = client.get("/api/funds/?fund_type=股票型")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["fund_code"] == "110022"


@pytest.mark.django_db
class TestFundDetailAPI:
    """测试基金详情 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def fund(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
            fund_type="混合型",
            latest_nav=Decimal("1.5000"),
            latest_nav_date=date(2024, 2, 10),
        )

    def test_get_fund_detail(self, client, fund):
        """测试获取基金详情"""
        response = client.get(f"/api/funds/{fund.fund_code}/")
        assert response.status_code == 200
        assert response.data["fund_code"] == "000001"
        assert response.data["fund_name"] == "华夏成长混合"
        assert Decimal(response.data["latest_nav"]) == Decimal("1.5000")

    def test_get_nonexistent_fund(self, client):
        """测试获取不存在的基金"""
        response = client.get("/api/funds/999999/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestFundEstimateAPI:
    """测试基金估值 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def fund(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
        )

    def test_get_fund_estimate(self, client, fund, mocker):
        """测试获取基金估值"""
        # Mock 数据源
        mock_source = mocker.Mock()
        mock_source.fetch_estimate.return_value = {
            "fund_code": "000001",
            "fund_name": "华夏成长混合",
            "estimate_nav": Decimal("1.1370"),
            "estimate_growth": Decimal("-1.05"),
            "estimate_time": "2024-02-11 15:00",
        }

        mocker.patch("api.sources.SourceRegistry.get_source", return_value=mock_source)

        response = client.get(f"/api/funds/{fund.fund_code}/estimate/")
        assert response.status_code == 200
        assert Decimal(response.data["estimate_nav"]) == Decimal("1.1370")

    def test_get_fund_estimate_with_source(self, client, fund, mocker):
        """测试指定数据源获取估值"""
        mock_source = mocker.Mock()
        mock_source.fetch_estimate.return_value = {
            "fund_code": "000001",
            "estimate_nav": Decimal("1.1370"),
        }

        mocker.patch("api.sources.SourceRegistry.get_source", return_value=mock_source)

        response = client.get(f"/api/funds/{fund.fund_code}/estimate/?source=eastmoney")
        assert response.status_code == 200


@pytest.mark.django_db
class TestFundAccuracyAPI:
    """测试基金准确率 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def fund(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
        )

    @pytest.fixture
    def accuracy_records(self, fund):
        from api.models import EstimateAccuracy

        records = []
        for i in range(10):
            record = EstimateAccuracy.objects.create(
                source_name="eastmoney",
                fund=fund,
                estimate_date=date(2024, 2, i + 1),
                estimate_nav=Decimal("1.1000"),
                actual_nav=Decimal("1.1100"),
                error_rate=Decimal("0.009009"),
            )
            records.append(record)
        return records

    def test_get_fund_accuracy(self, client, fund, accuracy_records):
        """测试获取基金准确率"""
        response = client.get(f"/api/funds/{fund.fund_code}/accuracy/")
        assert response.status_code == 200
        assert "eastmoney" in response.data
        assert "avg_error_rate" in response.data["eastmoney"]
        assert "record_count" in response.data["eastmoney"]


@pytest.mark.django_db
class TestBatchEstimateAPI:
    """测试批量估值 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def funds(self):
        from api.models import Fund
        from django.utils import timezone
        from datetime import timedelta

        # 创建基金，一个有缓存，一个没有缓存
        fund1 = Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
            latest_nav=Decimal("1.5000"),
            estimate_nav=Decimal("1.5100"),
            estimate_growth=Decimal("0.67"),
            estimate_time=timezone.now() - timedelta(minutes=3),  # 3分钟前，缓存有效
        )
        fund2 = Fund.objects.create(
            fund_code="000002",
            fund_name="华夏大盘精选",
            latest_nav=Decimal("2.0000"),
            estimate_nav=Decimal("2.0100"),
            estimate_growth=Decimal("0.50"),
            estimate_time=timezone.now() - timedelta(minutes=10),  # 10分钟前，缓存失效
        )
        fund3 = Fund.objects.create(
            fund_code="110022",
            fund_name="易方达消费行业",
            latest_nav=Decimal("3.0000"),
            # 没有估值数据
        )
        return [fund1, fund2, fund3]

    def test_batch_estimate_cache_hit(self, client, funds, mocker):
        """测试批量估值 - 缓存命中"""
        response = client.post(
            "/api/funds/batch_estimate/", {"fund_codes": ["000001"]}, format="json"
        )

        assert response.status_code == 200
        assert "000001" in response.data
        assert response.data["000001"]["from_cache"] is True
        assert Decimal(response.data["000001"]["estimate_nav"]) == Decimal("1.5100")
        assert Decimal(response.data["000001"]["estimate_growth"]) == Decimal("0.67")

    def test_batch_estimate_cache_miss(self, client, funds, mocker):
        """测试批量估值 - 缓存失效，从数据源获取"""
        # Mock 数据源
        mock_source = mocker.Mock()
        mock_source.fetch_estimate.return_value = {
            "fund_code": "000002",
            "fund_name": "华夏大盘精选",
            "estimate_nav": Decimal("2.0200"),
            "estimate_growth": Decimal("1.00"),
        }
        mocker.patch("api.sources.SourceRegistry.get_source", return_value=mock_source)

        response = client.post(
            "/api/funds/batch_estimate/", {"fund_codes": ["000002"]}, format="json"
        )

        assert response.status_code == 200
        assert "000002" in response.data
        assert response.data["000002"]["from_cache"] is False
        assert Decimal(response.data["000002"]["estimate_nav"]) == Decimal("2.0200")
        assert Decimal(response.data["000002"]["estimate_growth"]) == Decimal("1.00")

    def test_batch_estimate_no_cache(self, client, funds, mocker):
        """测试批量估值 - 无缓存数据，从数据源获取"""
        # Mock 数据源
        mock_source = mocker.Mock()
        mock_source.fetch_estimate.return_value = {
            "fund_code": "110022",
            "fund_name": "易方达消费行业",
            "estimate_nav": Decimal("3.0300"),
            "estimate_growth": Decimal("1.00"),
        }
        mocker.patch("api.sources.SourceRegistry.get_source", return_value=mock_source)

        response = client.post(
            "/api/funds/batch_estimate/", {"fund_codes": ["110022"]}, format="json"
        )

        assert response.status_code == 200
        assert "110022" in response.data
        assert response.data["110022"]["from_cache"] is False
        assert Decimal(response.data["110022"]["estimate_nav"]) == Decimal("3.0300")

    def test_batch_estimate_mixed(self, client, funds, mocker):
        """测试批量估值 - 混合场景（部分缓存命中，部分失效）"""
        # Mock 数据源（只会被调用失效的基金）
        mock_source = mocker.Mock()

        def mock_fetch_estimate(code):
            if code == "000002":
                return {
                    "fund_code": "000002",
                    "estimate_nav": Decimal("2.0200"),
                    "estimate_growth": Decimal("1.00"),
                }
            elif code == "110022":
                return {
                    "fund_code": "110022",
                    "estimate_nav": Decimal("3.0300"),
                    "estimate_growth": Decimal("1.00"),
                }

        mock_source.fetch_estimate.side_effect = mock_fetch_estimate
        mocker.patch("api.sources.SourceRegistry.get_source", return_value=mock_source)

        response = client.post(
            "/api/funds/batch_estimate/",
            {"fund_codes": ["000001", "000002", "110022"]},
            format="json",
        )

        assert response.status_code == 200

        # 000001 缓存命中
        assert response.data["000001"]["from_cache"] is True

        # 000002 和 110022 缓存失效，从数据源获取
        assert response.data["000002"]["from_cache"] is False
        assert response.data["110022"]["from_cache"] is False

    def test_batch_estimate_nonexistent_fund(self, client):
        """测试批量估值 - 不存在的基金"""
        response = client.post(
            "/api/funds/batch_estimate/", {"fund_codes": ["999999"]}, format="json"
        )

        assert response.status_code == 200
        assert "999999" in response.data
        assert "error" in response.data["999999"]

    def test_batch_estimate_empty_codes(self, client):
        """测试批量估值 - 空基金代码列表"""
        response = client.post(
            "/api/funds/batch_estimate/", {"fund_codes": []}, format="json"
        )

        assert response.status_code == 400

    def test_batch_estimate_missing_codes(self, client):
        """测试批量估值 - 缺少 fund_codes 参数"""
        response = client.post("/api/funds/batch_estimate/", {}, format="json")

        assert response.status_code == 400

    def test_batch_estimate_source_error(self, client, funds, mocker):
        """测试批量估值 - 数据源获取失败"""
        # Mock 数据源抛出异常
        mock_source = mocker.Mock()
        mock_source.fetch_estimate.side_effect = Exception("数据源错误")
        mocker.patch("api.sources.SourceRegistry.get_source", return_value=mock_source)

        response = client.post(
            "/api/funds/batch_estimate/", {"fund_codes": ["110022"]}, format="json"
        )

        assert response.status_code == 200
        assert "110022" in response.data
        assert "error" in response.data["110022"]

    def test_batch_estimate_updates_database(self, client, funds, mocker):
        """测试批量估值 - 验证数据库更新"""
        from api.models import Fund

        # Mock 数据源
        mock_source = mocker.Mock()
        mock_source.fetch_estimate.return_value = {
            "fund_code": "110022",
            "estimate_nav": Decimal("3.0300"),
            "estimate_growth": Decimal("1.00"),
        }
        mocker.patch("api.sources.SourceRegistry.get_source", return_value=mock_source)

        response = client.post(
            "/api/funds/batch_estimate/", {"fund_codes": ["110022"]}, format="json"
        )

        assert response.status_code == 200

        # 验证数据库已更新
        fund = Fund.objects.get(fund_code="110022")
        assert fund.estimate_nav == Decimal("3.0300")
        assert fund.estimate_growth == Decimal("1.00")
        assert fund.estimate_time is not None


@pytest.mark.django_db
class TestSyncFundsAPI:
    """测试同步基金列表 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def admin_user(self):
        return User.objects.create_superuser(username="admin", password="pass")

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="user", password="pass")

    def test_sync_funds_as_admin(self, client, admin_user, mocker):
        """测试管理员同步基金列表"""
        client.force_authenticate(user=admin_user)

        # Mock 数据源
        mock_source = mocker.Mock()
        mock_source.fetch_fund_list.return_value = [
            {"fund_code": "000001", "fund_name": "华夏成长混合", "fund_type": "混合型"},
        ]
        mocker.patch("api.sources.SourceRegistry.get_source", return_value=mock_source)

        response = client.post("/api/funds/sync/")
        assert response.status_code == 200
        assert "created" in response.data
        assert "updated" in response.data

    def test_sync_funds_as_regular_user(self, client, user):
        """测试普通用户不能同步基金列表"""
        client.force_authenticate(user=user)

        response = client.post("/api/funds/sync/")
        assert response.status_code == 403

    def test_sync_funds_unauthenticated(self, client):
        """测试未认证用户不能同步基金列表"""
        response = client.post("/api/funds/sync/")
        assert response.status_code == 401
