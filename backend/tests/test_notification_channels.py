"""
测试通知渠道抽象层

测试点：
1. WebhookChannel.send 成功
2. WebhookChannel.send 失败（非 2xx、超时、网络错误、缺少配置）
3. EmailChannel.send 成功
4. EmailChannel.send 失败（SMTP 错误、缺少配置）
5. ChannelRegistry 注册和获取
"""
import pytest
from unittest.mock import Mock, patch


class TestWebhookChannel:

    @patch('requests.post')
    def test_send_success_generic(self, mock_post):
        from api.notifications.webhook import WebhookChannel
        mock_post.return_value = Mock(status_code=200, json=Mock(return_value={}))

        channel = WebhookChannel()
        result = channel.send(
            title='测试通知',
            content='涨幅超过阈值',
            config={'webhook_url': 'https://example.com/hook'},
        )

        assert result is True
        payload = mock_post.call_args[1]['json']
        assert payload['title'] == '测试通知'
        assert payload['content'] == '涨幅超过阈值'

    @patch('requests.post')
    def test_send_feishu_format(self, mock_post):
        from api.notifications.webhook import WebhookChannel
        mock_post.return_value = Mock(status_code=200, json=Mock(return_value={'code': 0}))

        channel = WebhookChannel()
        result = channel.send(
            title='测试通知',
            content='涨幅超过阈值',
            config={'webhook_url': 'https://open.feishu.cn/open-apis/bot/v2/hook/xxx'},
        )

        assert result is True
        payload = mock_post.call_args[1]['json']
        assert payload['msg_type'] == 'post'
        assert payload['content']['post']['zh_cn']['title'] == '测试通知'

    @patch('requests.post')
    def test_send_feishu_error_code_returns_false(self, mock_post):
        from api.notifications.webhook import WebhookChannel
        mock_post.return_value = Mock(status_code=200, json=Mock(return_value={'code': 19001}))

        channel = WebhookChannel()
        result = channel.send('title', 'content', {'webhook_url': 'https://open.feishu.cn/open-apis/bot/v2/hook/xxx'})

        assert result is False

    @patch('requests.post')
    def test_send_non_2xx_returns_false(self, mock_post):
        from api.notifications.webhook import WebhookChannel
        mock_post.return_value = Mock(status_code=500)

        channel = WebhookChannel()
        result = channel.send('title', 'content', {'webhook_url': 'https://example.com/hook'})

        assert result is False

    @patch('requests.post')
    def test_send_timeout_returns_false(self, mock_post):
        from api.notifications.webhook import WebhookChannel
        import requests
        mock_post.side_effect = requests.Timeout()

        channel = WebhookChannel()
        result = channel.send('title', 'content', {'webhook_url': 'https://example.com/hook'})

        assert result is False

    @patch('requests.post')
    def test_send_network_error_returns_false(self, mock_post):
        from api.notifications.webhook import WebhookChannel
        import requests
        mock_post.side_effect = requests.RequestException('connection error')

        channel = WebhookChannel()
        result = channel.send('title', 'content', {'webhook_url': 'https://example.com/hook'})

        assert result is False

    def test_send_missing_url_returns_false(self):
        from api.notifications.webhook import WebhookChannel

        channel = WebhookChannel()
        result = channel.send('title', 'content', {})

        assert result is False

    def test_get_channel_type(self):
        from api.notifications.webhook import WebhookChannel
        assert WebhookChannel().get_channel_type() == 'webhook'


class TestEmailChannel:

    VALID_CONFIG = {
        'smtp_host': 'smtp.qq.com',
        'smtp_port': 465,
        'smtp_ssl': True,
        'username': 'sender@qq.com',
        'password': 'authcode',
        'to_email': 'recipient@example.com',
    }

    @patch('smtplib.SMTP_SSL')
    def test_send_success(self, mock_smtp_ssl):
        from api.notifications.email import EmailChannel
        mock_server = Mock()
        mock_smtp_ssl.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_ssl.return_value.__exit__ = Mock(return_value=False)

        channel = EmailChannel()
        result = channel.send(title='测试通知', content='涨幅超过阈值', config=self.VALID_CONFIG)

        assert result is True
        mock_server.login.assert_called_once_with('sender@qq.com', 'authcode')
        mock_server.sendmail.assert_called_once()

    @patch('smtplib.SMTP_SSL')
    def test_send_smtp_error_returns_false(self, mock_smtp_ssl):
        from api.notifications.email import EmailChannel
        import smtplib
        mock_smtp_ssl.return_value.__enter__ = Mock(side_effect=smtplib.SMTPException('error'))
        mock_smtp_ssl.return_value.__exit__ = Mock(return_value=False)

        channel = EmailChannel()
        result = channel.send('title', 'content', self.VALID_CONFIG)

        assert result is False

    def test_send_missing_fields_returns_false(self):
        from api.notifications.email import EmailChannel

        channel = EmailChannel()
        result = channel.send('title', 'content', {})

        assert result is False

    def test_send_starttls(self):
        from api.notifications.email import EmailChannel
        config = {**self.VALID_CONFIG, 'smtp_ssl': False, 'smtp_port': 587}

        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__ = Mock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = Mock(return_value=False)

            channel = EmailChannel()
            result = channel.send('title', 'content', config)

        assert result is True
        mock_server.starttls.assert_called_once()

    def test_get_channel_type(self):
        from api.notifications.email import EmailChannel
        assert EmailChannel().get_channel_type() == 'email'


class TestChannelRegistry:

    def setup_method(self):
        from api.notifications.registry import ChannelRegistry
        ChannelRegistry._channels = {}

    def test_register_and_get(self):
        from api.notifications.registry import ChannelRegistry
        from api.notifications.webhook import WebhookChannel

        channel = WebhookChannel()
        ChannelRegistry.register(channel)

        assert ChannelRegistry.get_channel('webhook') is channel

    def test_get_nonexistent_returns_none(self):
        from api.notifications.registry import ChannelRegistry

        assert ChannelRegistry.get_channel('nonexistent') is None

    def test_list_channels(self):
        from api.notifications.registry import ChannelRegistry
        from api.notifications.webhook import WebhookChannel
        from api.notifications.email import EmailChannel

        ChannelRegistry.register(WebhookChannel())
        ChannelRegistry.register(EmailChannel())

        channels = ChannelRegistry.list_channels()
        assert 'webhook' in channels
        assert 'email' in channels
        assert len(channels) == 2

    def test_auto_registration(self):
        """测试 __init__.py 自动注册"""
        # 重新导入触发自动注册
        import importlib
        import api.notifications
        importlib.reload(api.notifications)

        from api.notifications.registry import ChannelRegistry
        assert ChannelRegistry.get_channel('webhook') is not None
        assert ChannelRegistry.get_channel('email') is not None
