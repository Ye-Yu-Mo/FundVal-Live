"""
测试账户 API 序列化器（阶段三）

测试点：
1. 父账户返回 children 列表
2. 子账户返回汇总字段
3. 父账户汇总字段正确
"""

import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestAccountSerializerWithSummary:
    """测试账户序列化器汇总字段"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def parent_account(self, user):
        from api.models import Account

        return Account.objects.create(user=user, name="父账户")

    @pytest.fixture
    def child_account(self, user, parent_account):
        from api.models import Account

        return Account.objects.create(user=user, name="子账户", parent=parent_account)

    @pytest.fixture
    def fund(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000001",
            fund_name="测试基金",
            latest_nav=Decimal("1.5000"),
            estimate_nav=Decimal("1.6000"),
        )

    def test_child_account_serializer_includes_summary_fields(
        self, client, user, child_account, fund
    ):
        """测试子账户序列化器包含汇总字段"""
        from api.models import Position

        # 创建持仓
        Position.objects.create(
            account=child_account,
            fund=fund,
            holding_share=Decimal("100"),
            holding_cost=Decimal("1000"),
            holding_nav=Decimal("10"),
        )

        client.force_authenticate(user=user)
        response = client.get(f"/api/accounts/{child_account.id}/")

        assert response.status_code == 200
        data = response.data

        # 验证汇总字段存在
        assert "holding_cost" in data
        assert "holding_value" in data
        assert "pnl" in data
        assert "pnl_rate" in data
        assert "estimate_value" in data
        assert "estimate_pnl" in data
        assert "estimate_pnl_rate" in data
        assert "today_pnl" in data
        assert "today_pnl_rate" in data

        # 验证汇总字段值正确
        assert Decimal(data["holding_cost"]) == Decimal("1000")
        assert Decimal(data["holding_value"]) == Decimal("150")
        assert Decimal(data["pnl"]) == Decimal("-850")
        assert Decimal(data["pnl_rate"]) == Decimal("-0.85")

    def test_parent_account_serializer_includes_children(
        self, client, user, parent_account, child_account
    ):
        """测试父账户序列化器包含 children 列表"""
        client.force_authenticate(user=user)
        response = client.get(f"/api/accounts/{parent_account.id}/")

        assert response.status_code == 200
        data = response.data

        # 验证 children 字段存在
        assert "children" in data
        assert isinstance(data["children"], list)
        assert len(data["children"]) == 1
        assert data["children"][0]["id"] == str(child_account.id)
        assert data["children"][0]["name"] == "子账户"

    def test_parent_account_serializer_includes_summary_fields(
        self, client, user, parent_account, child_account, fund
    ):
        """测试父账户序列化器包含汇总字段"""
        from api.models import Position

        # 创建子账户持仓
        Position.objects.create(
            account=child_account,
            fund=fund,
            holding_share=Decimal("100"),
            holding_cost=Decimal("1000"),
            holding_nav=Decimal("10"),
        )

        client.force_authenticate(user=user)
        response = client.get(f"/api/accounts/{parent_account.id}/")

        assert response.status_code == 200
        data = response.data

        # 验证汇总字段存在且正确
        assert "holding_cost" in data
        assert "holding_value" in data
        assert "pnl" in data

        # 父账户汇总 = 子账户汇总
        assert Decimal(data["holding_cost"]) == Decimal("1000")
        assert Decimal(data["holding_value"]) == Decimal("150")
        assert Decimal(data["pnl"]) == Decimal("-850")

    def test_account_list_includes_summary_fields(
        self, client, user, parent_account, child_account, fund
    ):
        """测试账户列表包含汇总字段"""
        from api.models import Position

        Position.objects.create(
            account=child_account,
            fund=fund,
            holding_share=Decimal("100"),
            holding_cost=Decimal("1000"),
            holding_nav=Decimal("10"),
        )

        client.force_authenticate(user=user)
        response = client.get("/api/accounts/")

        assert response.status_code == 200
        assert len(response.data) == 2  # 父账户 + 子账户

        # 找到父账户和子账户
        parent_data = next(
            a for a in response.data if a["id"] == str(parent_account.id)
        )
        child_data = next(a for a in response.data if a["id"] == str(child_account.id))

        # 验证都包含汇总字段
        assert "holding_cost" in parent_data
        assert "holding_cost" in child_data
        assert "children" in parent_data
        assert "children" not in child_data  # 子账户不应该有 children 字段

    def test_child_account_without_positions(self, client, user, child_account):
        """测试无持仓子账户的汇总字段"""
        client.force_authenticate(user=user)
        response = client.get(f"/api/accounts/{child_account.id}/")

        assert response.status_code == 200
        data = response.data

        # 验证汇总字段为 0 或 None
        assert Decimal(data["holding_cost"]) == Decimal("0")
        assert Decimal(data["holding_value"]) == Decimal("0")
        assert Decimal(data["pnl"]) == Decimal("0")
        assert data["pnl_rate"] is None

    def test_parent_account_without_children(self, client, user, parent_account):
        """测试无子账户的父账户"""
        client.force_authenticate(user=user)
        response = client.get(f"/api/accounts/{parent_account.id}/")

        assert response.status_code == 200
        data = response.data

        # 验证 children 为空列表
        assert "children" in data
        assert data["children"] == []

        # 验证汇总字段为 0
        assert Decimal(data["holding_cost"]) == Decimal("0")
        assert Decimal(data["holding_value"]) == Decimal("0")
