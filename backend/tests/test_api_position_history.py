"""
测试账户历史市值 API

测试点：
1. 正常查询，返回历史数据
2. 缺少 account_id，返回 400
3. 查询其他用户账户，返回 404
4. 查询父账户，返回 400
5. 自定义天数，返回正确数量
6. 未认证用户，返回 401
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


@pytest.mark.django_db
class TestPositionHistoryAPI:
    """账户历史市值 API 测试"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="testuser", password="pass")

    @pytest.fixture
    def other_user(self):
        return User.objects.create_user(username="otheruser", password="pass")

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def auth_client(self, client, user):
        """认证客户端"""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    @pytest.fixture
    def parent_account(self, user):
        """父账户"""
        from api.models import Account

        return Account.objects.create(user=user, name="父账户")

    @pytest.fixture
    def child_account(self, user, create_child_account):
        """子账户"""
        return create_child_account(user, "子账户")

    @pytest.fixture
    def other_child_account(self, other_user, create_child_account):
        """其他用户的子账户"""
        return create_child_account(other_user, "其他子账户")

    @pytest.fixture
    def fund(self):
        from api.models import Fund

        return Fund.objects.create(
            fund_code="000001",
            fund_name="华夏成长混合",
            latest_nav=Decimal("1.5000"),
        )

    def test_position_history_success(self, auth_client, child_account, fund):
        """正常查询，返回历史数据"""
        from api.models import PositionOperation, FundNavHistory

        # 创建操作：5 天前买入
        op_date = date.today() - timedelta(days=5)
        PositionOperation.objects.create(
            account=child_account,
            fund=fund,
            operation_type="BUY",
            operation_date=op_date,
            amount=Decimal("1000.00"),
            share=Decimal("1000.0000"),
            nav=Decimal("1.0000"),
            before_15=True,
        )

        # 创建历史净值
        for i in range(10):
            nav_date = date.today() - timedelta(days=9 - i)
            FundNavHistory.objects.create(
                fund=fund,
                nav_date=nav_date,
                unit_nav=Decimal("1.0000") + Decimal(str(i * 0.1)),
            )

        # 请求 API
        response = auth_client.get(
            "/api/positions/history/", {"account_id": str(child_account.id), "days": 10}
        )

        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # 验证数据格式
        assert isinstance(data, list)
        assert len(data) == 11  # 10 天 + 今天

        # 验证第一条数据
        assert "date" in data[0]
        assert "value" in data[0]
        assert "cost" in data[0]

        # 验证日期范围
        assert data[0]["date"] == (date.today() - timedelta(days=10)).isoformat()
        assert data[-1]["date"] == date.today().isoformat()

    def test_position_history_missing_account_id(self, auth_client):
        """缺少 account_id，返回 400"""
        response = auth_client.get("/api/positions/history/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.json()
        assert "缺少 account_id" in response.json()["error"]

    def test_position_history_unauthorized(self, auth_client, other_child_account):
        """查询其他用户账户，返回 404"""
        response = auth_client.get(
            "/api/positions/history/", {"account_id": str(other_child_account.id)}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_position_history_parent_account(self, auth_client, parent_account):
        """查询父账户，返回 400"""
        response = auth_client.get(
            "/api/positions/history/", {"account_id": str(parent_account.id)}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.json()
        assert "暂不支持父账户" in response.json()["error"]

    def test_position_history_custom_days(self, auth_client, child_account, fund):
        """自定义天数，返回正确数量"""
        from api.models import PositionOperation

        # 创建操作
        op_date = date.today() - timedelta(days=50)
        PositionOperation.objects.create(
            account=child_account,
            fund=fund,
            operation_type="BUY",
            operation_date=op_date,
            amount=Decimal("1000.00"),
            share=Decimal("1000.0000"),
            nav=Decimal("1.0000"),
            before_15=True,
        )

        # 测试 days=7
        response = auth_client.get(
            "/api/positions/history/", {"account_id": str(child_account.id), "days": 7}
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 8  # 7 天 + 今天

        # 测试 days=30
        response = auth_client.get(
            "/api/positions/history/", {"account_id": str(child_account.id), "days": 30}
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 31  # 30 天 + 今天

        # 测试 days=90
        response = auth_client.get(
            "/api/positions/history/", {"account_id": str(child_account.id), "days": 90}
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 91  # 90 天 + 今天

    def test_position_history_unauthenticated(self, client, child_account):
        """未认证用户，返回 401"""
        response = client.get(
            "/api/positions/history/", {"account_id": str(child_account.id)}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_position_history_default_days(self, auth_client, child_account, fund):
        """不传 days 参数，默认 30 天"""
        from api.models import PositionOperation

        # 创建操作
        op_date = date.today() - timedelta(days=50)
        PositionOperation.objects.create(
            account=child_account,
            fund=fund,
            operation_type="BUY",
            operation_date=op_date,
            amount=Decimal("1000.00"),
            share=Decimal("1000.0000"),
            nav=Decimal("1.0000"),
            before_15=True,
        )

        # 不传 days 参数
        response = auth_client.get(
            "/api/positions/history/", {"account_id": str(child_account.id)}
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 31  # 默认 30 天 + 今天

    def test_position_history_invalid_account_id(self, auth_client):
        """无效的 account_id，返回 404"""
        response = auth_client.get(
            "/api/positions/history/",
            {"account_id": "00000000-0000-0000-0000-000000000000"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
