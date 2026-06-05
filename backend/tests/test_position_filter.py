"""
测试持仓按基金过滤功能
"""

import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from api.models import Fund, Position

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user1(db):
    return User.objects.create_user(username="user1", password="pass123")


@pytest.fixture
def user2(db):
    return User.objects.create_user(username="user2", password="pass123")


@pytest.fixture
def fund1(db):
    return Fund.objects.create(fund_code="000001", fund_name="华夏成长混合")


@pytest.fixture
def fund2(db):
    return Fund.objects.create(fund_code="000002", fund_name="华夏大盘精选")


@pytest.mark.django_db
def test_filter_by_fund_code(api_client, user1, fund1, fund2, create_child_account):
    """测试按基金代码过滤持仓"""
    # 创建子账户
    account1 = create_child_account(user1, "账户1")
    account2 = create_child_account(user1, "账户2")

    # 创建持仓
    Position.objects.create(
        account=account1,
        fund=fund1,
        holding_share=Decimal("1000"),
        holding_cost=Decimal("1200"),
    )
    Position.objects.create(
        account=account2,
        fund=fund1,
        holding_share=Decimal("500"),
        holding_cost=Decimal("625"),
    )
    Position.objects.create(
        account=account1,
        fund=fund2,
        holding_share=Decimal("800"),
        holding_cost=Decimal("1840"),
    )

    # 登录
    api_client.force_authenticate(user=user1)

    # 按基金过滤
    response = api_client.get("/api/positions/", {"fund_code": "000001"})

    assert response.status_code == 200
    assert len(response.data) == 2
    assert all(pos["fund"]["fund_code"] == "000001" for pos in response.data)


@pytest.mark.django_db
def test_filter_by_fund_code_empty(api_client, user1, fund1, create_child_account):
    """测试过滤不存在的基金返回空列表"""
    # 创建子账户和持仓
    account1 = create_child_account(user1, "账户1")
    Position.objects.create(
        account=account1,
        fund=fund1,
        holding_share=Decimal("1000"),
        holding_cost=Decimal("1200"),
    )

    # 登录
    api_client.force_authenticate(user=user1)

    # 查询不存在的基金
    response = api_client.get("/api/positions/", {"fund_code": "999999"})

    assert response.status_code == 200
    assert len(response.data) == 0


@pytest.mark.django_db
def test_filter_by_fund_code_only_current_user(
    api_client, user1, user2, fund1, create_child_account
):
    """测试只返回当前用户的持仓"""
    # user1 的持仓
    account1 = create_child_account(user1, "账户1")
    Position.objects.create(
        account=account1,
        fund=fund1,
        holding_share=Decimal("1000"),
        holding_cost=Decimal("1200"),
    )

    # user2 的持仓
    account2 = create_child_account(user2, "账户2")
    Position.objects.create(
        account=account2,
        fund=fund1,
        holding_share=Decimal("500"),
        holding_cost=Decimal("625"),
    )

    # 以 user1 登录
    api_client.force_authenticate(user=user1)

    # 按基金过滤
    response = api_client.get("/api/positions/", {"fund_code": "000001"})

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["account_name"] == "账户1"


@pytest.mark.django_db
def test_filter_by_fund_code_requires_auth(api_client):
    """测试未认证用户无法查询持仓"""
    response = api_client.get("/api/positions/", {"fund_code": "000001"})

    assert response.status_code == 401


@pytest.mark.django_db
def test_filter_by_fund_code_and_account(
    api_client, user1, fund1, create_child_account
):
    """测试同时按基金和账户过滤"""
    # 创建子账户
    account1 = create_child_account(user1, "账户1")
    account2 = create_child_account(user1, "账户2")

    # 创建持仓
    Position.objects.create(
        account=account1,
        fund=fund1,
        holding_share=Decimal("1000"),
        holding_cost=Decimal("1200"),
    )
    Position.objects.create(
        account=account2,
        fund=fund1,
        holding_share=Decimal("500"),
        holding_cost=Decimal("625"),
    )

    # 登录
    api_client.force_authenticate(user=user1)

    # 同时按基金和账户过滤
    response = api_client.get(
        "/api/positions/", {"fund_code": "000001", "account": account1.id}
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["account"] == account1.id
    assert response.data[0]["fund"]["fund_code"] == "000001"
