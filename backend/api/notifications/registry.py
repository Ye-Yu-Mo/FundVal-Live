"""
通知渠道注册表
"""

from .base import BaseNotificationChannel


class ChannelRegistry:
    """通知渠道注册表（单例）"""

    _channels = {}

    @classmethod
    def register(cls, channel: BaseNotificationChannel):
        cls._channels[channel.get_channel_type()] = channel

    @classmethod
    def get_channel(cls, channel_type: str) -> BaseNotificationChannel | None:
        return cls._channels.get(channel_type)

    @classmethod
    def list_channels(cls) -> list[str]:
        return list(cls._channels.keys())
