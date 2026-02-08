"""
认证和授权工具函数
"""
import bcrypt
from .db import get_db_connection


def hash_password(password: str) -> str:
    """
    哈希密码

    Args:
        password: 明文密码

    Returns:
        str: bcrypt 哈希值
    """
    # bcrypt 自动生成 salt 并包含在哈希值中
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    验证密码

    Args:
        password: 明文密码
        password_hash: bcrypt 哈希值

    Returns:
        bool: 密码是否匹配
    """
    try:
        password_bytes = password.encode('utf-8')
        hash_bytes = password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False


def _get_setting_bool(key: str, default: bool = False) -> bool:
    """
    从 settings 表读取布尔值配置

    Args:
        key: 配置键
        default: 默认值

    Returns:
        bool: 配置值
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row is None:
            return default
        return row[0] == '1'
    finally:
        conn.close()


def is_multi_user_mode() -> bool:
    """
    获取多用户模式状态

    Returns:
        bool: True 表示多用户模式，False 表示单用户模式
    """
    return _get_setting_bool('multi_user_mode', False)


def is_registration_allowed() -> bool:
    """
    获取注册开关状态

    Returns:
        bool: True 表示允许注册，False 表示禁止注册
    """
    return _get_setting_bool('allow_registration', False)

