import logging
import re
from fastapi import APIRouter, HTTPException, Body
from ..db import get_db_connection
from ..crypto import encrypt_value, decrypt_value
from ..config import Config

logger = logging.getLogger(__name__)
router = APIRouter()

# 需要加密的字段
ENCRYPTED_FIELDS = {"OPENAI_API_KEY", "SMTP_PASSWORD"}

# 字段验证规则
def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_url(url: str) -> bool:
    pattern = r'^https?://[^\s]+$'
    return re.match(pattern, url) is not None

def validate_port(port: str) -> bool:
    try:
        p = int(port)
        return 1 <= p <= 65535
    except:
        return False

@router.get("/settings")
def get_settings():
    """获取所有设置（加密字段用 *** 掩码）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, encrypted FROM settings")
        rows = cursor.fetchall()
        conn.close()

        settings = {}
        for row in rows:
            key = row["key"]
            value = row["value"]
            encrypted = row["encrypted"]

            # 加密字段用掩码
            if encrypted and value:
                settings[key] = "***"
            else:
                settings[key] = value

        # 如果数据库为空，返回 .env 的默认值（掩码敏感信息）
        if not settings:
            settings = {
                "OPENAI_API_KEY": "***" if Config.OPENAI_API_KEY else "",
                "OPENAI_API_BASE": Config.OPENAI_API_BASE,
                "AI_MODEL_NAME": Config.AI_MODEL_NAME,
                "SMTP_HOST": Config.SMTP_HOST,
                "SMTP_PORT": str(Config.SMTP_PORT),
                "SMTP_USER": Config.SMTP_USER,
                "SMTP_PASSWORD": "***" if Config.SMTP_PASSWORD else "",
                "EMAIL_FROM": Config.EMAIL_FROM,
            }

        return {"settings": settings}
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/settings")
def update_settings(data: dict = Body(...)):
    """更新设置（部分更新，验证输入）"""
    try:
        settings = data.get("settings", {})
        errors = {}

        # 验证输入
        if "SMTP_PORT" in settings:
            if not validate_port(settings["SMTP_PORT"]):
                errors["SMTP_PORT"] = "端口必须在 1-65535 之间"

        if "SMTP_USER" in settings and settings["SMTP_USER"]:
            if not validate_email(settings["SMTP_USER"]):
                errors["SMTP_USER"] = "邮箱格式不正确"

        if "EMAIL_FROM" in settings and settings["EMAIL_FROM"]:
            if not validate_email(settings["EMAIL_FROM"]):
                errors["EMAIL_FROM"] = "邮箱格式不正确"

        if "OPENAI_API_BASE" in settings and settings["OPENAI_API_BASE"]:
            if not validate_url(settings["OPENAI_API_BASE"]):
                errors["OPENAI_API_BASE"] = "URL 格式不正确"

        if errors:
            raise HTTPException(status_code=400, detail={"errors": errors})

        # 保存到数据库
        conn = get_db_connection()
        cursor = conn.cursor()

        for key, value in settings.items():
            # 跳过掩码值（用户没有修改）
            if value == "***":
                continue

            # 判断是否需要加密
            encrypted = 1 if key in ENCRYPTED_FIELDS else 0
            if encrypted and value:
                value = encrypt_value(value)

            # Upsert
            cursor.execute("""
                INSERT INTO settings (key, value, encrypted, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    encrypted = excluded.encrypted,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, value, encrypted))

        conn.commit()
        conn.close()

        # 重新加载配置
        Config.reload()

        return {"message": "设置已保存"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preferences")
def get_preferences():
    """获取用户偏好（自选列表、当前账户、排序选项）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取自选列表
        cursor.execute("SELECT value FROM settings WHERE key = 'user_watchlist'")
        watchlist_row = cursor.fetchone()
        watchlist = watchlist_row["value"] if watchlist_row else "[]"

        # 获取当前账户
        cursor.execute("SELECT value FROM settings WHERE key = 'user_current_account'")
        account_row = cursor.fetchone()
        current_account = int(account_row["value"]) if account_row else 1

        # 获取排序选项
        cursor.execute("SELECT value FROM settings WHERE key = 'user_sort_option'")
        sort_row = cursor.fetchone()
        sort_option = sort_row["value"] if sort_row else None

        conn.close()

        return {
            "watchlist": watchlist,
            "currentAccount": current_account,
            "sortOption": sort_option
        }
    except Exception as e:
        logger.error(f"Failed to get preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/preferences")
def update_preferences(data: dict = Body(...)):
    """更新用户偏好"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if "watchlist" in data:
            cursor.execute("""
                INSERT INTO settings (key, value, encrypted, updated_at)
                VALUES ('user_watchlist', ?, 0, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (data["watchlist"],))

        if "currentAccount" in data:
            cursor.execute("""
                INSERT INTO settings (key, value, encrypted, updated_at)
                VALUES ('user_current_account', ?, 0, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (str(data["currentAccount"]),))

        if "sortOption" in data:
            cursor.execute("""
                INSERT INTO settings (key, value, encrypted, updated_at)
                VALUES ('user_sort_option', ?, 0, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (data["sortOption"],))

        conn.commit()
        conn.close()

        return {"message": "偏好已保存"}
    except Exception as e:
        logger.error(f"Failed to update preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))
