"""
通知渠道模块
"""

from .email import EmailChannel
from .registry import ChannelRegistry
from .webhook import WebhookChannel

# 自动注册所有渠道
ChannelRegistry.register(WebhookChannel())
ChannelRegistry.register(EmailChannel())

__all__ = ["ChannelRegistry", "EmailChannel", "WebhookChannel"]
