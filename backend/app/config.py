import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# 判断是否为打包后的应用
if getattr(sys, 'frozen', False):
    # 打包后：使用用户目录
    BASE_DIR = Path.home() / '.fundval-live'
    BASE_DIR.mkdir(parents=True, exist_ok=True)
else:
    # 开发模式：使用项目目录
    BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root (one level up from backend)
if not getattr(sys, 'frozen', False):
    load_dotenv(BASE_DIR.parent / ".env")

def _load_settings_from_db():
    """从数据库读取配置，解密加密字段"""
    try:
        import sqlite3
        from .crypto import decrypt_value

        db_path = os.path.join(BASE_DIR, "data", "fund.db")
        if not os.path.exists(db_path):
            return {}

        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, encrypted FROM settings WHERE user_id IS NULL")
        rows = cursor.fetchall()
        # Note: Connection will be closed by garbage collector

        settings = {}
        for row in rows:
            key, value, encrypted = row
            if encrypted and value:
                value = decrypt_value(value)
            settings[key] = value
        return settings
    except Exception as e:
        print(f"Failed to load settings from DB: {e}")
        return {}

def _get_setting(key: str, default: str = "") -> str:
    """获取配置，优先级：数据库 > .env > 默认值"""
    db_settings = _load_settings_from_db()
    if key in db_settings and db_settings[key]:
        return db_settings[key]
    return os.getenv(key, default)

class Config:
    # Database
    DB_PATH = os.path.join(BASE_DIR, "data", "fund.db")
    DB_URL = f"sqlite:///{DB_PATH}"

    # Data Sources
    DEFAULT_DATA_SOURCE = "eastmoney"

    # External APIs (Eastmoney)
    EASTMONEY_API_URL = "http://fundgz.1234567.com.cn/js/{code}.js"
    EASTMONEY_DETAILED_API_URL = "http://fund.eastmoney.com/pingzhongdata/{code}.js"
    EASTMONEY_ALL_FUNDS_API_URL = "http://fund.eastmoney.com/js/fundcode_search.js"

    # Update Intervals
    FUND_LIST_UPDATE_INTERVAL = 86400  # 24 hours
    STOCK_SPOT_CACHE_DURATION = 60     # 1 minute (for holdings calculation)

    # AI Configuration - 动态读取
    OPENAI_API_KEY = _get_setting("OPENAI_API_KEY", "")
    OPENAI_API_BASE = _get_setting("OPENAI_API_BASE", "https://api.openai.com/v1")
    AI_MODEL_NAME = _get_setting("AI_MODEL_NAME", "gpt-3.5-turbo")

    # Email / Subscription Configuration - 动态读取
    SMTP_HOST = _get_setting("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(_get_setting("SMTP_PORT", "587"))
    SMTP_USER = _get_setting("SMTP_USER", "")
    SMTP_PASSWORD = _get_setting("SMTP_PASSWORD", "")
    EMAIL_FROM = _get_setting("EMAIL_FROM", "noreply@fundval.live")

    @classmethod
    def reload(cls):
        """重新加载配置（在设置更新后调用）"""
        cls.OPENAI_API_KEY = _get_setting("OPENAI_API_KEY", "")
        cls.OPENAI_API_BASE = _get_setting("OPENAI_API_BASE", "https://api.openai.com/v1")
        cls.AI_MODEL_NAME = _get_setting("AI_MODEL_NAME", "gpt-3.5-turbo")
        cls.SMTP_HOST = _get_setting("SMTP_HOST", "smtp.gmail.com")
        cls.SMTP_PORT = int(_get_setting("SMTP_PORT", "587"))
        cls.SMTP_USER = _get_setting("SMTP_USER", "")
        cls.SMTP_PASSWORD = _get_setting("SMTP_PASSWORD", "")
        cls.EMAIL_FROM = _get_setting("EMAIL_FROM", "noreply@fundval.live")

