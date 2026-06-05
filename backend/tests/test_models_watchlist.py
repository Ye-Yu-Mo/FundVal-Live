"""
测试 Watchlist 模型

测试点：
1. 自选列表创建
2. 自选项添加
3. 排序
4. 唯一性约束
"""

import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestWatchlistModel:
    """Watchlist 模型测试"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def fund1(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
        )

    @pytest.fixture
    def fund2(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000002",
            fund_name="华夏大盘精选",
        )

    def test_create_watchlist(self, user):
        """测试创建自选列表"""
        from api.models import Watchlist

        watchlist = Watchlist.objects.create(
            user=user,
            name="我的自选",
        )

        assert watchlist.user == user
        assert watchlist.name == "我的自选"

    def test_watchlist_name_unique_per_user(self, user):
        """测试同一用户下自选列表名唯一"""
        from api.models import Watchlist

        Watchlist.objects.create(user=user, name="我的自选")

        # 重复名称应该报错
        with pytest.raises(IntegrityError):
            Watchlist.objects.create(user=user, name="我的自选")

    def test_different_users_can_have_same_watchlist_name(self):
        """测试不同用户可以有相同自选列表名"""
        from api.models import Watchlist

        user1 = User.objects.create_user(username="user1", password="pass1")
        user2 = User.objects.create_user(username="user2", password="pass2")

        wl1 = Watchlist.objects.create(user=user1, name="我的自选")
        wl2 = Watchlist.objects.create(user=user2, name="我的自选")

        assert wl1.name == wl2.name
        assert wl1.user != wl2.user


@pytest.mark.django_db
class TestWatchlistItemModel:
    """WatchlistItem 模型测试"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def watchlist(self, user):
        from api.models import Watchlist

        return Watchlist.objects.create(user=user, name="我的自选")

    @pytest.fixture
    def fund1(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
        )

    @pytest.fixture
    def fund2(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000002",
            fund_name="华夏大盘精选",
        )

    def test_add_fund_to_watchlist(self, watchlist, fund1):
        """测试添加基金到自选"""
        from api.models import WatchlistItem

        item = WatchlistItem.objects.create(
            watchlist=watchlist,
            fund=fund1,
            order=0,
        )

        assert item.watchlist == watchlist
        assert item.fund == fund1
        assert item.order == 0

    def test_watchlist_item_unique_per_watchlist_fund(self, watchlist, fund1):
        """测试同一自选列表中基金唯一"""
        from api.models import WatchlistItem

        WatchlistItem.objects.create(
            watchlist=watchlist,
            fund=fund1,
            order=0,
        )

        # 重复添加应该报错
        with pytest.raises(IntegrityError):
            WatchlistItem.objects.create(
                watchlist=watchlist,
                fund=fund1,
                order=1,
            )

    def test_watchlist_items_ordering(self, watchlist, fund1, fund2):
        """测试自选项按 order 排序"""
        from api.models import WatchlistItem

        item2 = WatchlistItem.objects.create(
            watchlist=watchlist,
            fund=fund2,
            order=1,
        )

        item1 = WatchlistItem.objects.create(
            watchlist=watchlist,
            fund=fund1,
            order=0,
        )

        items = list(WatchlistItem.objects.all())
        # 应该按 order 升序排列
        assert items[0] == item1  # order=0
        assert items[1] == item2  # order=1

    def test_delete_watchlist_cascades_to_items(self, watchlist, fund1, fund2):
        """测试删除自选列表会级联删除自选项"""
        from api.models import WatchlistItem

        item1 = WatchlistItem.objects.create(watchlist=watchlist, fund=fund1)
        item2 = WatchlistItem.objects.create(watchlist=watchlist, fund=fund2)

        watchlist_id = watchlist.id
        item1_id = item1.id
        item2_id = item2.id

        watchlist.delete()

        # 自选列表和所有自选项都应该被删除
        assert not WatchlistItem.objects.filter(id=item1_id).exists()
        assert not WatchlistItem.objects.filter(id=item2_id).exists()
