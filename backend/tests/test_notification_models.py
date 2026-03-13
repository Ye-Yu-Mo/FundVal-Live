"""
测试通知系统数据模型

测试点：
1. NotificationChannel 创建和约束
2. NotificationRule 创建和约束
3. NotificationLog 创建
4. M2M 关系
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
class TestNotificationChannel:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    def test_create_webhook_channel(self, user):
        from api.models import NotificationChannel
        channel = NotificationChannel.objects.create(
            user=user,
            channel_type='webhook',
            config={'webhook_url': 'https://example.com/hook'},
        )
        assert channel.channel_type == 'webhook'
        assert channel.config['webhook_url'] == 'https://example.com/hook'
        assert channel.is_active is True

    def test_create_email_channel(self, user):
        from api.models import NotificationChannel
        channel = NotificationChannel.objects.create(
            user=user,
            channel_type='email',
            config={'email': 'test@example.com'},
        )
        assert channel.channel_type == 'email'
        assert channel.config['email'] == 'test@example.com'

    def test_multiple_channels_same_type(self, user):
        """同一用户可以有多个同类型渠道"""
        from api.models import NotificationChannel
        NotificationChannel.objects.create(
            user=user, channel_type='webhook',
            config={'webhook_url': 'https://a.com/hook'},
        )
        NotificationChannel.objects.create(
            user=user, channel_type='webhook',
            config={'webhook_url': 'https://b.com/hook'},
        )
        assert NotificationChannel.objects.filter(user=user).count() == 2


@pytest.mark.django_db
class TestNotificationRule:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

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

    def test_create_rule(self, user, fund, channel):
        from api.models import NotificationRule
        rule = NotificationRule.objects.create(
            user=user,
            fund=fund,
            rule_type='growth_up',
            threshold=Decimal('5.00'),
            cooldown_minutes=60,
        )
        rule.channels.add(channel)

        assert rule.rule_type == 'growth_up'
        assert rule.threshold == Decimal('5.00')
        assert rule.cooldown_minutes == 60
        assert rule.is_active is True
        assert rule.channels.count() == 1

    def test_rule_multiple_channels(self, user, fund):
        from api.models import NotificationRule, NotificationChannel
        ch1 = NotificationChannel.objects.create(
            user=user, channel_type='webhook',
            config={'webhook_url': 'https://a.com/hook'},
        )
        ch2 = NotificationChannel.objects.create(
            user=user, channel_type='email',
            config={'email': 'test@example.com'},
        )
        rule = NotificationRule.objects.create(
            user=user, fund=fund, rule_type='growth_down',
            threshold=Decimal('3.00'),
        )
        rule.channels.add(ch1, ch2)
        assert rule.channels.count() == 2

    def test_negative_threshold_rejected(self, user, fund):
        """负阈值应该被拒绝"""
        from api.models import NotificationRule
        from django.db import connection
        with pytest.raises(Exception):
            rule = NotificationRule(
                user=user, fund=fund, rule_type='growth_up',
                threshold=Decimal('-1.00'),
            )
            rule.save()
            # 触发 DB 约束检查
            connection.check_constraints()

    def test_negative_cooldown_rejected(self, user, fund):
        """负冷却时间应该被拒绝"""
        from api.models import NotificationRule
        from django.db import connection
        with pytest.raises(Exception):
            rule = NotificationRule(
                user=user, fund=fund, rule_type='growth_up',
                threshold=Decimal('5.00'),
                cooldown_minutes=-1,
            )
            rule.save()
            connection.check_constraints()


@pytest.mark.django_db
class TestNotificationLog:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

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

    @pytest.fixture
    def rule(self, user, fund, channel):
        from api.models import NotificationRule
        r = NotificationRule.objects.create(
            user=user, fund=fund, rule_type='growth_up',
            threshold=Decimal('5.00'),
        )
        r.channels.add(channel)
        return r

    def test_create_success_log(self, rule, channel, fund):
        from api.models import NotificationLog
        log = NotificationLog.objects.create(
            rule=rule,
            channel=channel,
            fund_code=fund.fund_code,
            fund_name=fund.fund_name,
            growth=Decimal('6.50'),
            status='success',
        )
        assert log.status == 'success'
        assert log.growth == Decimal('6.50')
        assert log.error_message is None

    def test_create_failed_log(self, rule, channel, fund):
        from api.models import NotificationLog
        log = NotificationLog.objects.create(
            rule=rule,
            channel=channel,
            fund_code=fund.fund_code,
            fund_name=fund.fund_name,
            growth=Decimal('6.50'),
            status='failed',
            error_message='Connection timeout',
        )
        assert log.status == 'failed'
        assert log.error_message == 'Connection timeout'
