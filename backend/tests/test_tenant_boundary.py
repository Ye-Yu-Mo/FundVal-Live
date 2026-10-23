"""
多租户边界回归测试

覆盖：
1. 不能在他人的账户上创建流水
2. 不能把账户挂到他人的父账户下
3. 不能把账户设为自己的父账户
4. 不能借用他人的数据源凭证
5. 匿名不能调用会写库/触发外部抓取的接口
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def alice():
    return User.objects.create_user(username="alice", password="pass")


@pytest.fixture
def bob():
    return User.objects.create_user(username="bob", password="pass")


@pytest.fixture
def fund():
    from api.models import Fund

    return Fund.objects.create(fund_code="000001", fund_name="测试基金")


def _operation_payload(account_id):
    return {
        "account": str(account_id),
        "fund_code": "000001",
        "operation_type": "BUY",
        "operation_date": "2024-02-11",
        "before_15": True,
        "amount": "1000",
        "share": "100",
        "nav": "10",
    }


@pytest.mark.django_db
class TestOperationTenantBoundary:
    """PositionOperation 只能写自己的子账户"""

    def test_cannot_create_operation_on_other_users_account(
        self, client, alice, bob, fund, create_child_account
    ):
        bob_account = create_child_account(bob, "bob-子账户")
        client.force_authenticate(user=alice)

        response = client.post(
            "/api/positions/operations/",
            _operation_payload(bob_account.id),
            format="json",
        )

        assert response.status_code == 400
        from api.models import PositionOperation

        assert not PositionOperation.objects.filter(account=bob_account).exists()

    def test_can_create_operation_on_own_child_account(
        self, client, alice, fund, create_child_account
    ):
        alice_account = create_child_account(alice, "alice-子账户")
        client.force_authenticate(user=alice)

        response = client.post(
            "/api/positions/operations/",
            _operation_payload(alice_account.id),
            format="json",
        )

        assert response.status_code == 201

    def test_cannot_create_operation_on_parent_account(self, client, alice, fund):
        from api.models import Account

        parent = Account.objects.create(user=alice, name="alice-父账户")
        client.force_authenticate(user=alice)

        response = client.post(
            "/api/positions/operations/",
            _operation_payload(parent.id),
            format="json",
        )

        assert response.status_code == 400


@pytest.mark.django_db
class TestAccountParentTenantBoundary:
    """账户父子关系不能跨用户"""

    def test_cannot_create_account_under_other_users_parent(self, client, alice, bob):
        from api.models import Account

        bob_parent = Account.objects.create(user=bob, name="bob-父账户")
        client.force_authenticate(user=alice)

        response = client.post(
            "/api/accounts/",
            {"name": "alice-子账户", "parent": str(bob_parent.id)},
            format="json",
        )

        assert response.status_code == 400
        assert not Account.objects.filter(user=alice, name="alice-子账户").exists()

    def test_cannot_update_parent_to_other_users_account(self, client, alice, bob):
        from api.models import Account

        alice_account = Account.objects.create(user=alice, name="alice-账户")
        bob_parent = Account.objects.create(user=bob, name="bob-父账户")
        client.force_authenticate(user=alice)

        response = client.patch(
            f"/api/accounts/{alice_account.id}/",
            {"parent": str(bob_parent.id)},
            format="json",
        )

        assert response.status_code == 400
        alice_account.refresh_from_db()
        assert alice_account.parent_id is None

    def test_account_cannot_be_its_own_parent(self, client, alice):
        from api.models import Account

        account = Account.objects.create(user=alice, name="alice-账户")
        client.force_authenticate(user=alice)

        response = client.patch(
            f"/api/accounts/{account.id}/",
            {"parent": str(account.id)},
            format="json",
        )

        assert response.status_code == 400

    def test_default_account_cannot_have_parent(self, client, alice):
        from api.models import Account

        parent = Account.objects.create(user=alice, name="alice-父账户")
        client.force_authenticate(user=alice)

        response = client.post(
            "/api/accounts/",
            {"name": "alice-子账户", "parent": str(parent.id), "is_default": True},
            format="json",
        )

        assert response.status_code == 400
        assert "is_default" in response.data


@pytest.mark.django_db
class TestCredentialTenantBoundary:
    """数据源凭证只能使用当前用户自己的"""

    def _credential(self, user, token):
        from api.models import UserSourceCredential

        return UserSourceCredential.objects.create(
            user=user,
            source_name="yangjibao",
            token=token,
            is_active=True,
        )

    def test_estimate_does_not_use_other_users_credential(self, client, alice, bob, fund):
        self._credential(bob, "bob-token")
        client.force_authenticate(user=alice)

        fake_source = MagicMock()
        fake_source.fetch_estimate.return_value = {
            "fund_code": "000001",
            "estimate_nav": Decimal("1.2"),
        }

        with patch("api.viewsets.SourceRegistry.get_source", return_value=fake_source):
            response = client.get("/api/funds/000001/estimate/?source=yangjibao")

        assert response.status_code == 400
        fake_source.set_token.assert_not_called()

    def test_anonymous_estimate_does_not_use_any_credential(self, client, bob, fund):
        self._credential(bob, "bob-token")

        fake_source = MagicMock()
        fake_source.fetch_estimate.return_value = {
            "fund_code": "000001",
            "estimate_nav": Decimal("1.2"),
        }

        with patch("api.viewsets.SourceRegistry.get_source", return_value=fake_source):
            response = client.get("/api/funds/000001/estimate/?source=yangjibao")

        assert response.status_code == 400
        fake_source.set_token.assert_not_called()

    def test_status_does_not_report_other_users_login(self, client, alice, bob):
        self._credential(bob, "bob-token")
        client.force_authenticate(user=alice)

        response = client.get("/api/source-credentials/status/?source_name=yangjibao")

        assert response.status_code == 200
        assert response.data["logged_in"] is False

    def test_batch_estimate_does_not_use_other_users_credential(self, client, alice, bob, fund):
        self._credential(bob, "bob-token")
        client.force_authenticate(user=alice)

        fake_source = MagicMock()

        with patch("api.viewsets.SourceRegistry.get_source", return_value=fake_source):
            response = client.post(
                "/api/funds/batch_estimate/",
                {"fund_codes": ["000001"], "source": "yangjibao"},
                format="json",
            )

        assert response.status_code == 400
        fake_source.set_token.assert_not_called()


@pytest.mark.django_db
class TestAnonymousWriteEndpoints:
    """会写库或触发外部抓取的接口必须要求登录"""

    def test_batch_estimate_requires_auth(self, client):
        response = client.post(
            "/api/funds/batch_estimate/", {"fund_codes": ["000001"]}, format="json"
        )
        assert response.status_code == 401

    def test_batch_update_nav_requires_auth(self, client):
        response = client.post(
            "/api/funds/batch_update_nav/", {"fund_codes": ["000001"]}, format="json"
        )
        assert response.status_code == 401

    def test_batch_update_today_nav_requires_auth(self, client):
        response = client.post(
            "/api/funds/batch_update_today_nav/",
            {"fund_codes": ["000001"]},
            format="json",
        )
        assert response.status_code == 401

    def test_query_nav_requires_auth(self, client):
        response = client.post(
            "/api/funds/query_nav/",
            {
                "fund_code": "000001",
                "operation_date": date(2024, 2, 11).isoformat(),
                "before_15": True,
            },
            format="json",
        )
        assert response.status_code == 401

    def test_nav_history_sync_requires_auth(self, client):
        with patch("api.services.nav_history.batch_sync_nav_history", return_value={}) as mock_sync:
            response = client.post(
                "/api/nav-history/sync/", {"fund_codes": ["000001"]}, format="json"
            )

        assert response.status_code == 401
        mock_sync.assert_not_called()


@pytest.mark.django_db
class TestBackgroundCredentialIsolation:
    """后台任务不能借用任意用户的数据源凭证"""

    def test_intraday_snapshot_does_not_use_user_credential(self, bob):
        from datetime import datetime

        from django.utils import timezone as dj_timezone

        from api.models import UserSourceCredential

        UserSourceCredential.objects.create(
            user=bob,
            source_name="xiaobeiyangji",
            token="bob-token",
            is_active=True,
        )

        fake_source = MagicMock()
        fake_source.get_source_name.return_value = "xiaobeiyangji"
        fake_source.fetch_estimate.return_value = None

        now = dj_timezone.make_aware(datetime(2026, 10, 23, 10, 0))

        with (
            patch("api.utils.trading_calendar.is_trading_day", return_value=True),
            patch("django.utils.timezone.localdate", return_value=date(2026, 10, 23)),
            patch("django.utils.timezone.localtime", return_value=now),
            patch(
                "api.sources.registry.SourceRegistry.list_sources",
                return_value=["xiaobeiyangji"],
            ),
            patch(
                "api.sources.registry.SourceRegistry.get_source",
                return_value=fake_source,
            ),
        ):
            from api.tasks import capture_intraday_snapshots

            capture_intraday_snapshots()

        fake_source.set_token.assert_not_called()

    def test_accuracy_command_does_not_use_user_credential(self, bob):
        from datetime import timedelta
        from io import StringIO

        from django.core.management import call_command

        from api.models import EstimateAccuracy, Fund, UserSourceCredential

        fund = Fund.objects.create(fund_code="000001", fund_name="测试基金")
        EstimateAccuracy.objects.create(
            source_name="eastmoney",
            fund=fund,
            estimate_date=date.today() - timedelta(days=1),
            estimate_nav=Decimal("1.1000"),
        )
        UserSourceCredential.objects.create(
            user=bob,
            source_name="xiaobeiyangji",
            token="bob-token",
            is_active=True,
        )

        fake_source = MagicMock()

        with (
            patch(
                "api.management.commands.calculate_accuracy.SourceRegistry.list_sources",
                return_value=["xiaobeiyangji"],
            ),
            patch(
                "api.management.commands.calculate_accuracy.SourceRegistry.get_source",
                return_value=fake_source,
            ),
        ):
            call_command("calculate_accuracy", stdout=StringIO())

        fake_source.set_token.assert_not_called()
