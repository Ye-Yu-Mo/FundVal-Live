"""
通知渠道抽象基类
"""
from abc import ABC, abstractmethod


class BaseNotificationChannel(ABC):
    """通知渠道抽象基类"""

    @abstractmethod
    def get_channel_type(self) -> str:
        """返回渠道类型标识（webhook/email）"""
        pass

    @abstractmethod
    def send(self, title: str, content: str, config: dict) -> bool:
        """
        发送通知

        Args:
            title: 通知标题
            content: 通知内容
            config: 渠道配置（来自 NotificationChannel.config）

        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        pass
