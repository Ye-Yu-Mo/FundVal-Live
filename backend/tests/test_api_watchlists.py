"""
测试自选列表相关 API

测试点：
1. 自选列表列表
2. 创建自选列表
3. 自选列表详情
4. 更新自选列表
5. 删除自选列表
6. 添加基金到自选
7. 移除基金
8. 重新排序
"""

import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestWatchlistListAPI:
    """测试自选列表列表 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def watchlists(self, user):
        from api.models import Watchlist

        return [
            Watchlist.objects.create(user=user, name="自选1"),
            Watchlist.objects.create(user=user, name="自选2"),
        ]

    def test_list_watchlists(self, client, user, watchlists):
        """测试查看自选列表"""
        client.force_authenticate(user=user)
        response = client.get("/api/watchlists/")
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_list_watchlists_unauthenticated(self, client):
        """测试未认证用户不能查看自选"""
        response = client.get("/api/watchlists/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestWatchlistCreateAPI:
    """测试创建自选列表 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    def test_create_watchlist(self, client, user):
        """测试创建自选列表"""
        client.force_authenticate(user=user)
        response = client.post(
            "/api/watchlists/",
            {
                "name": "我的自选",
            },
        )
        assert response.status_code == 201
        assert response.data["name"] == "我的自选"

    def test_create_watchlist_duplicate_name(self, client, user):
        """测试创建重名自选列表"""
        from api.models import Watchlist

        Watchlist.objects.create(user=user, name="我的自选")

        client.force_authenticate(user=user)
        response = client.post(
            "/api/watchlists/",
            {
                "name": "我的自选",
            },
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestWatchlistDetailAPI:
    """测试自选列表详情 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def watchlist(self, user):
        from api.models import Watchlist

        return Watchlist.objects.create(user=user, name="我的自选")

    def test_get_watchlist_detail(self, client, user, watchlist):
        """测试获取自选列表详情"""
        client.force_authenticate(user=user)
        response = client.get(f"/api/watchlists/{watchlist.id}/")
        assert response.status_code == 200
        assert response.data["name"] == "我的自选"

    def test_get_watchlist_with_items(self, client, user, watchlist):
        """测试获取自选列表（包含基金）"""
        from api.models import Fund, WatchlistItem

        fund1 = Fund.objects.create(fund_code="000001", fund_name="基金1")
        fund2 = Fund.objects.create(fund_code="000002", fund_name="基金2")

        WatchlistItem.objects.create(watchlist=watchlist, fund=fund1, order=0)
        WatchlistItem.objects.create(watchlist=watchlist, fund=fund2, order=1)

        client.force_authenticate(user=user)
        response = client.get(f"/api/watchlists/{watchlist.id}/")
        assert response.status_code == 200
        assert len(response.data["items"]) == 2


@pytest.mark.django_db
class TestWatchlistUpdateAPI:
    """测试更新自选列表 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def watchlist(self, user):
        from api.models import Watchlist

        return Watchlist.objects.create(user=user, name="我的自选")

    def test_update_watchlist_name(self, client, user, watchlist):
        """测试更新自选列表名称"""
        client.force_authenticate(user=user)
        response = client.put(
            f"/api/watchlists/{watchlist.id}/",
            {
                "name": "新名称",
            },
        )
        assert response.status_code == 200
        assert response.data["name"] == "新名称"


@pytest.mark.django_db
class TestWatchlistDeleteAPI:
    """测试删除自选列表 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def watchlist(self, user):
        from api.models import Watchlist

        return Watchlist.objects.create(user=user, name="我的自选")

    def test_delete_watchlist(self, client, user, watchlist):
        """测试删除自选列表"""
        client.force_authenticate(user=user)
        response = client.delete(f"/api/watchlists/{watchlist.id}/")
        assert response.status_code == 204

        from api.models import Watchlist

        assert not Watchlist.objects.filter(id=watchlist.id).exists()


@pytest.mark.django_db
class TestWatchlistItemsAPI:
    """测试自选列表项 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def watchlist(self, user):
        from api.models import Watchlist

        return Watchlist.objects.create(user=user, name="我的自选")

    @pytest.fixture
    def fund(self):
        from api.models import Fund

        return Fund.objects.create(fund_code="000001", fund_name="华夏成长混合")

    def test_add_fund_to_watchlist(self, client, user, watchlist, fund):
        """测试添加基金到自选"""
        client.force_authenticate(user=user)
        response = client.post(
            f"/api/watchlists/{watchlist.id}/items/",
            {
                "fund_code": fund.fund_code,
            },
        )
        assert response.status_code == 201

        from api.models import WatchlistItem

        assert WatchlistItem.objects.filter(watchlist=watchlist, fund=fund).exists()

    def test_add_duplicate_fund(self, client, user, watchlist, fund):
        """测试添加重复基金"""
        from api.models import WatchlistItem

        WatchlistItem.objects.create(watchlist=watchlist, fund=fund)

        client.force_authenticate(user=user)
        response = client.post(
            f"/api/watchlists/{watchlist.id}/items/",
            {
                "fund_code": fund.fund_code,
            },
        )
        assert response.status_code == 400

    def test_remove_fund_from_watchlist(self, client, user, watchlist, fund):
        """测试从自选移除基金"""
        from api.models import WatchlistItem

        WatchlistItem.objects.create(watchlist=watchlist, fund=fund)

        client.force_authenticate(user=user)
        response = client.delete(
            f"/api/watchlists/{watchlist.id}/items/{fund.fund_code}/"
        )
        assert response.status_code == 204

        assert not WatchlistItem.objects.filter(watchlist=watchlist, fund=fund).exists()


@pytest.mark.django_db
class TestWatchlistReorderAPI:
    """测试自选列表重新排序 API"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def watchlist_with_items(self, user):
        from api.models import Watchlist, Fund, WatchlistItem

        watchlist = Watchlist.objects.create(user=user, name="我的自选")

        fund1 = Fund.objects.create(fund_code="000001", fund_name="基金1")
        fund2 = Fund.objects.create(fund_code="000002", fund_name="基金2")
        fund3 = Fund.objects.create(fund_code="000003", fund_name="基金3")

        WatchlistItem.objects.create(watchlist=watchlist, fund=fund1, order=0)
        WatchlistItem.objects.create(watchlist=watchlist, fund=fund2, order=1)
        WatchlistItem.objects.create(watchlist=watchlist, fund=fund3, order=2)

        return watchlist

    def test_reorder_watchlist_items(self, client, user, watchlist_with_items):
        """测试重新排序自选列表"""
        client.force_authenticate(user=user)
        response = client.put(
            f"/api/watchlists/{watchlist_with_items.id}/reorder/",
            {
                "fund_codes": ["000003", "000001", "000002"],
            },
        )
        assert response.status_code == 200

        from api.models import WatchlistItem

        items = list(
            WatchlistItem.objects.filter(watchlist=watchlist_with_items).order_by(
                "order"
            )
        )

        # 验证排序
        assert items[0].order == 0
        assert items[0].fund.fund_code == "000003"
        assert items[1].order == 1
        assert items[1].fund.fund_code == "000001"
        assert items[2].order == 2
        assert items[2].fund.fund_code == "000002"
