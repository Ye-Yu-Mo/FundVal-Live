"""
Webhook 通知渠道
"""
import logging
import requests
from datetime import datetime, timezone

from .base import BaseNotificationChannel

logger = logging.getLogger(__name__)


class WebhookChannel(BaseNotificationChannel):
    """Webhook 通知渠道"""

    def get_channel_type(self) -> str:
        return 'webhook'

    def _build_payload(self, webhook_url: str, title: str, content: str) -> dict:
        """根据 URL 自动识别平台，构建对应格式的 payload"""
        if 'feishu.cn' in webhook_url or 'larksuite.com' in webhook_url:
            # 飞书机器人格式
            return {
                'msg_type': 'post',
                'content': {
                    'post': {
                        'zh_cn': {
                            'title': title,
                            'content': [[{'tag': 'text', 'text': content}]],
                        }
                    }
                },
            }
        if 'dingtalk.com' in webhook_url:
            # 钉钉机器人格式
            return {
                'msgtype': 'markdown',
                'markdown': {
                    'title': title,
                    'text': f'### {title}\n{content}',
                },
            }
        if 'qyapi.weixin.qq.com' in webhook_url:
            # 企业微信机器人格式
            return {
                'msgtype': 'markdown',
                'markdown': {
                    'content': f'**{title}**\n{content}',
                },
            }
        # 通用格式
        return {
            'title': title,
            'content': content,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    def send(self, title: str, content: str, config: dict) -> bool:
        webhook_url = config.get('webhook_url')
        if not webhook_url:
            logger.error('Webhook 配置缺少 webhook_url')
            return False

        payload = self._build_payload(webhook_url, title, content)

        try:
            resp = requests.post(webhook_url, json=payload, timeout=5)
            if resp.status_code < 200 or resp.status_code >= 300:
                logger.error(f'Webhook 发送失败，状态码：{resp.status_code}, URL: {webhook_url}')
                return False
            # 飞书/钉钉返回 200 但 body 里有错误码
            try:
                body = resp.json()
                err_code = body.get('code') or body.get('errcode')
                if err_code and int(err_code) != 0:
                    logger.error(f'Webhook 平台返回错误：{body}')
                    return False
            except Exception:
                pass
            return True
        except requests.Timeout:
            logger.error(f'Webhook 发送超时：{webhook_url}')
            return False
        except requests.RequestException as e:
            logger.error(f'Webhook 发送失败：{webhook_url}, 错误：{e}')
            return False
