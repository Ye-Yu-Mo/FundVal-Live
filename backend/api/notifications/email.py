"""
Email 通知渠道

config 字段格式：
{
    "smtp_host": "smtp.qq.com",
    "smtp_port": 465,
    "smtp_ssl": true,
    "username": "your@qq.com",
    "password": "授权码",
    "from_email": "your@qq.com",   # 可选，默认同 username
    "to_email": "recipient@example.com"
}
"""
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.header import Header

from .base import BaseNotificationChannel

logger = logging.getLogger(__name__)


class EmailChannel(BaseNotificationChannel):
    """Email 通知渠道（使用用户自定义 SMTP 配置）"""

    def get_channel_type(self) -> str:
        return 'email'

    def send(self, title: str, content: str, config: dict) -> bool:
        smtp_host = config.get('smtp_host')
        smtp_port = config.get('smtp_port', 465)
        smtp_ssl = config.get('smtp_ssl', True)
        username = config.get('username')
        password = config.get('password')
        from_email = config.get('from_email') or username
        to_email = config.get('to_email')

        if not all([smtp_host, username, password, to_email]):
            logger.error('Email 配置不完整，缺少必要字段')
            return False

        msg = MIMEText(content, 'plain', 'utf-8')
        msg['Subject'] = Header(title, 'utf-8')
        msg['From'] = from_email
        msg['To'] = to_email

        try:
            if smtp_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=10) as server:
                    server.login(username, password)
                    server.sendmail(from_email, [to_email], msg.as_string())
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(username, password)
                    server.sendmail(from_email, [to_email], msg.as_string())
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f'Email 认证失败：{username}, 错误：{e}')
            return False
        except smtplib.SMTPException as e:
            logger.error(f'Email 发送失败：{to_email}, 错误：{e}')
            return False
        except Exception as e:
            logger.error(f'Email 发送失败（未知错误）：{to_email}, 错误：{e}')
            return False
