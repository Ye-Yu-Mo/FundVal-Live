"""
通知渠道模块
"""
from .registry import ChannelRegistry
from .webhook import WebhookChannel
from .email import EmailChannel

# 自动注册所有渠道
ChannelRegistry.register(WebhookChannel())
ChannelRegistry.register(EmailChannel())

__all__ = ['ChannelRegistry', 'WebhookChannel', 'EmailChannel']
