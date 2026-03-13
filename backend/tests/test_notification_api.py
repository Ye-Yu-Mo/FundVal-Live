"""
测试通知系统 API 端点

测试点：
1. NotificationChannel CRUD + 用户隔离
2. NotificationChannel test action
3. NotificationRule CRUD + 用户隔离
4. NotificationLog 只读 + 用户隔离
"""
import pytest
from decimal import Decimal
from unittest.mock import patch
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestNotificationChannelAPI:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='user1', password='pass')

    @pytest.fixture
    def other_user(self):
        return User.objects.create_user(username='user2', password='pass')

    @pytest.fixture
    def client(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    def test_create_webhook_channel(self, client):
        resp = client.post('/api/notification-channels/', {
            'channel_type': 'webhook',
            'config': {'webhook_url': 'https://example.com/hook'},
        }, format='json')
        assert resp.status_code == 201
        assert resp.data['channel_type'] == 'webhook'

    def test_create_email_channel(self, client):
        resp = client.post('/api/notification-channels/', {
            'channel_type': 'email',
            'config': {
                'smtp_host': 'smtp.qq.com',
                'smtp_port': 465,
                'smtp_ssl': True,
                'username': 'sender@qq.com',
                'password': 'authcode',
                'to_email': 'recipient@example.com',
            },
        }, format='json')
        assert resp.status_code == 201

    def test_create_webhook_missing_url_rejected(self, client):
        resp = client.post('/api/notification-channels/', {
            'channel_type': 'webhook',
            'config': {},
        }, format='json')
        assert resp.status_code == 400

    def test_list_only_own_channels(self, client, user, other_user):
        from api.models import NotificationChannel
        NotificationChannel.objects.create(
            user=user, channel_type='webhook',
            config={'webhook_url': 'https://a.com'},
        )
        NotificationChannel.objects.create(
            user=other_user, channel_type='webhook',
            config={'webhook_url': 'https://b.com'},
        )
        resp = client.get('/api/notification-channels/')
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_unauthenticated_rejected(self):
        c = APIClient()
        resp = c.get('/api/notification-channels/')
        assert resp.status_code == 401

    @patch('api.notifications.webhook.WebhookChannel.send')
    def test_test_action_success(self, mock_send, client, user):
        from api.models import NotificationChannel
        mock_send.return_value = True
        channel = NotificationChannel.objects.create(
            user=user, channel_type='webhook',
            config={'webhook_url': 'https://example.com/hook'},
        )
        resp = client.post(f'/api/notification-channels/{channel.id}/test/')
        assert resp.status_code == 200
        assert '成功' in resp.data['message']

    @patch('api.notifications.webhook.WebhookChannel.send')
    def test_test_action_failure(self, mock_send, client, user):
        from api.models import NotificationChannel
        mock_send.return_value = False
        channel = NotificationChannel.objects.create(
            user=user, channel_type='webhook',
            config={'webhook_url': 'https://example.com/hook'},
        )
        resp = client.post(f'/api/notification-channels/{channel.id}/test/')
        assert resp.status_code == 400


@pytest.mark.django_db
class TestNotificationRuleAPI:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='user1', password='pass')

    @pytest.fixture
    def client(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    @pytest.fixture
    def fund(self):
        from api.models import Fund
        return Fund.objects.create(fund_code='510300', fund_name='沪深300ETF', fund_type='股票指数型')

    @pytest.fixture
    def channel(self, user):
        from api.models import NotificationChannel
        return NotificationChannel.objects.create(
            user=user, channel_type='webhook',
            config={'webhook_url': 'https://example.com/hook'},
        )

    def test_create_rule(self, client, fund, channel):
        resp = client.post('/api/notification-rules/', {
            'fund': str(fund.id),
            'rule_type': 'growth_up',
            'threshold': '5.00',
            'cooldown_minutes': 60,
            'channel_ids': [str(channel.id)],
        }, format='json')
        assert resp.status_code == 201
        assert resp.data['rule_type'] == 'growth_up'
        assert len(resp.data['channels']) == 1

    def test_list_rules(self, client, fund, channel):
        from api.models import NotificationRule
        rule = NotificationRule.objects.create(
            user=client.handler._force_user,
            fund=fund, rule_type='growth_up',
            threshold=Decimal('5.00'),
        )
        rule.channels.add(channel)
        resp = client.get('/api/notification-rules/')
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_delete_rule(self, client, fund):
        from api.models import NotificationRule
        rule = NotificationRule.objects.create(
            user=client.handler._force_user,
            fund=fund, rule_type='growth_up',
            threshold=Decimal('5.00'),
        )
        resp = client.delete(f'/api/notification-rules/{rule.id}/')
        assert resp.status_code == 204


@pytest.mark.django_db
class TestNotificationLogAPI:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='user1', password='pass')

    @pytest.fixture
    def client(self, user):
        c = APIClient()
        c.force_authenticate(user=user)
        return c

    @pytest.fixture
    def log(self, user):
        from api.models import Fund, NotificationChannel, NotificationRule, NotificationLog
        fund = Fund.objects.create(fund_code='510300', fund_name='沪深300ETF')
        channel = NotificationChannel.objects.create(
            user=user, channel_type='webhook',
            config={'webhook_url': 'https://example.com/hook'},
        )
        rule = NotificationRule.objects.create(
            user=user, fund=fund, rule_type='growth_up',
            threshold=Decimal('5.00'),
        )
        rule.channels.add(channel)
        return NotificationLog.objects.create(
            rule=rule, channel=channel,
            fund_code='510300', fund_name='沪深300ETF',
            growth=Decimal('6.50'), status='success',
        )

    def test_list_logs(self, client, log):
        resp = client.get('/api/notification-logs/')
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]['status'] == 'success'

    def test_logs_are_readonly(self, client):
        resp = client.post('/api/notification-logs/', {}, format='json')
        assert resp.status_code == 405
