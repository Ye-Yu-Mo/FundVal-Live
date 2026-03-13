"""
测试通知规则 Celery 任务

测试点：
1. 涨幅触发规则
2. 跌幅触发规则
3. 未触发规则（未达阈值）
4. 冷却时间内不重复发送
5. 无估值数据时跳过
6. 渠道发送失败记录 failed 日志
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, Mock
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


@pytest.mark.django_db
class TestCheckNotificationRules:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def fund_up(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='510300',
            fund_name='沪深300ETF',
            fund_type='股票指数型',
            estimate_growth=Decimal('6.50'),
        )

    @pytest.fixture
    def fund_down(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000001',
            fund_name='华夏成长混合',
            fund_type='混合型',
            estimate_growth=Decimal('-4.00'),
        )

    @pytest.fixture
    def fund_no_estimate(self):
        from api.models import Fund
        return Fund.objects.create(
            fund_code='000002',
            fund_name='无估值基金',
            fund_type='混合型',
            estimate_growth=None,
        )

    @pytest.fixture
    def webhook_channel(self, user):
        from api.models import NotificationChannel
        return NotificationChannel.objects.create(
            user=user,
            channel_type='webhook',
            config={'webhook_url': 'https://example.com/hook'},
        )

    def _make_rule(self, user, fund, rule_type, threshold, channel, cooldown=60):
        from api.models import NotificationRule
        rule = NotificationRule.objects.create(
            user=user, fund=fund,
            rule_type=rule_type,
            threshold=Decimal(str(threshold)),
            cooldown_minutes=cooldown,
        )
        rule.channels.add(channel)
        return rule

    @patch('api.notifications.webhook.WebhookChannel.send')
    def test_growth_up_triggers(self, mock_send, user, fund_up, webhook_channel):
        """涨幅超过阈值时触发通知"""
        mock_send.return_value = True
        self._make_rule(user, fund_up, 'growth_up', 5.0, webhook_channel)

        from api.tasks import check_notification_rules
        result = check_notification_rules()

        assert '触发 1 条' in result
        assert '发送 1 条' in result
        mock_send.assert_called_once()

    @patch('api.notifications.webhook.WebhookChannel.send')
    def test_growth_down_triggers(self, mock_send, user, fund_down, webhook_channel):
        """跌幅超过阈值时触发通知"""
        mock_send.return_value = True
        self._make_rule(user, fund_down, 'growth_down', 3.0, webhook_channel)

        from api.tasks import check_notification_rules
        result = check_notification_rules()

        assert '触发 1 条' in result
        mock_send.assert_called_once()

    @patch('api.notifications.webhook.WebhookChannel.send')
    def test_below_threshold_not_triggered(self, mock_send, user, fund_up, webhook_channel):
        """未达阈值时不触发"""
        self._make_rule(user, fund_up, 'growth_up', 10.0, webhook_channel)

        from api.tasks import check_notification_rules
        result = check_notification_rules()

        assert '触发 0 条' in result
        mock_send.assert_not_called()

    @patch('api.notifications.webhook.WebhookChannel.send')
    def test_cooldown_prevents_resend(self, mock_send, user, fund_up, webhook_channel):
        """冷却期内不重复发送"""
        from api.models import NotificationLog
        mock_send.return_value = True
        rule = self._make_rule(user, fund_up, 'growth_up', 5.0, webhook_channel, cooldown=60)

        # 模拟已有成功通知记录
        NotificationLog.objects.create(
            rule=rule,
            channel=webhook_channel,
            fund_code=fund_up.fund_code,
            fund_name=fund_up.fund_name,
            growth=Decimal('6.50'),
            status='success',
        )

        from api.tasks import check_notification_rules
        result = check_notification_rules()

        assert '触发 1 条' in result
        assert '发送 0 条' in result
        mock_send.assert_not_called()

    @patch('api.notifications.webhook.WebhookChannel.send')
    def test_no_estimate_skipped(self, mock_send, user, fund_no_estimate, webhook_channel):
        """无估值数据时跳过"""
        self._make_rule(user, fund_no_estimate, 'growth_up', 5.0, webhook_channel)

        from api.tasks import check_notification_rules
        result = check_notification_rules()

        assert '触发 0 条' in result
        mock_send.assert_not_called()

    @patch('api.notifications.webhook.WebhookChannel.send')
    def test_send_failure_logs_failed(self, mock_send, user, fund_up, webhook_channel):
        """发送失败时记录 failed 日志"""
        from api.models import NotificationLog
        mock_send.return_value = False
        self._make_rule(user, fund_up, 'growth_up', 5.0, webhook_channel)

        from api.tasks import check_notification_rules
        check_notification_rules()

        log = NotificationLog.objects.filter(rule__fund=fund_up).first()
        assert log is not None
        assert log.status == 'failed'

    @patch('api.notifications.webhook.WebhookChannel.send')
    def test_inactive_rule_skipped(self, mock_send, user, fund_up, webhook_channel):
        """未激活的规则不触发"""
        from api.models import NotificationRule
        rule = NotificationRule.objects.create(
            user=user, fund=fund_up,
            rule_type='growth_up',
            threshold=Decimal('5.0'),
            is_active=False,
        )
        rule.channels.add(webhook_channel)

        from api.tasks import check_notification_rules
        result = check_notification_rules()

        assert '触发 0 条' in result
        mock_send.assert_not_called()
