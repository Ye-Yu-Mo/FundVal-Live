"""
认证和授权工具函数
"""
import bcrypt
import secrets
import threading
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from fastapi import Request, HTTPException, status
from .db import get_db_connection


# Session 配置
SESSION_COOKIE_NAME = "session_id"
SESSION_EXPIRY_DAYS = 30


@dataclass
class User:
    """用户模型"""
    id: int
    username: str
    is_admin: bool


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


def has_admin_user() -> bool:
    """
    检测是否存在管理员用户

    Returns:
        bool: True 表示存在管理员，False 表示不存在
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = 1")
    row = cursor.fetchone()
    return row["count"] > 0


# ============================================================================
# Session 管理
# ============================================================================

# 内存存储 session（生产环境应该用 Redis）
# 使用硬上限防止 OOM，达到上限时先清理过期 session
_MAX_SESSIONS = 1000  # 硬上限，防止 OOM（降低到 1000）
_sessions = {}
_sessions_lock = threading.Lock()  # 并发保护


def _cleanup_expired_locked():
    """
    清理过期 session（必须在持有锁时调用）

    Returns:
        int: 清理的 session 数量
    """
    now = datetime.now()
    expired_keys = [sid for sid, data in _sessions.items() if now > data['expiry']]
    for sid in expired_keys:
        del _sessions[sid]
    return len(expired_keys)


def create_session(user_id: int) -> str:
    """
    创建 session

    Args:
        user_id: 用户 ID

    Returns:
        str: session_id

    Raises:
        HTTPException: 503 服务器繁忙（session 数量达到上限）
    """
    session_id = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(days=SESSION_EXPIRY_DAYS)

    with _sessions_lock:
        # 先清理过期的 session
        _cleanup_expired_locked()

        # 如果还是达到上限，拒绝创建
        if len(_sessions) >= _MAX_SESSIONS:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="服务器繁忙，请稍后重试"
            )

        _sessions[session_id] = {
            'user_id': user_id,
            'expiry': expiry
        }

    return session_id


def get_session_user(session_id: str) -> Optional[int]:
    """
    获取 session 对应的 user_id

    Args:
        session_id: session ID

    Returns:
        Optional[int]: user_id，如果 session 不存在或已过期则返回 None
    """
    with _sessions_lock:
        if session_id not in _sessions:
            return None

        session = _sessions[session_id]

        # 检查是否过期
        if datetime.now() > session['expiry']:
            del _sessions[session_id]
            return None

        # 续期：每次访问延长 30 天
        session['expiry'] = datetime.now() + timedelta(days=SESSION_EXPIRY_DAYS)

        return session['user_id']


def cleanup_expired_sessions():
    """
    清理所有过期的 session（防止内存泄漏）
    应该由后台任务定期调用
    """
    with _sessions_lock:
        now = datetime.now()
        expired_keys = [sid for sid, data in _sessions.items() if now > data['expiry']]
        for sid in expired_keys:
            del _sessions[sid]
        return len(expired_keys)


def delete_session(session_id: str):
    """
    删除 session

    Args:
        session_id: session ID
    """
    with _sessions_lock:
        if session_id in _sessions:
            del _sessions[session_id]


def _get_user_by_id(user_id: int) -> Optional[User]:
    """
    根据 user_id 获取用户信息

    Args:
        user_id: 用户 ID

    Returns:
        Optional[User]: 用户对象，如果不存在则返回 None
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, is_admin FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return User(id=row[0], username=row[1], is_admin=row[2])


# ============================================================================
# FastAPI Dependencies
# ============================================================================

def get_current_user(request: Request) -> Optional[User]:
    """
    获取当前用户（FastAPI Dependency）

    Args:
        request: FastAPI Request 对象

    Returns:
        Optional[User]: 用户对象
            - 单用户模式：返回 None
            - 多用户模式：从 cookie 读取 session_id，返回 User 对象
    """
    # 从 cookie 读取 session_id
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None

    # 获取 user_id
    user_id = get_session_user(session_id)
    if not user_id:
        return None

    # 获取用户信息
    return _get_user_by_id(user_id)


def require_auth(request: Request) -> User:
    """
    强制要求登录（FastAPI Dependency）

    Args:
        request: FastAPI Request 对象

    Returns:
        User: 用户对象

    Raises:
        HTTPException: 401 未登录
    """
    user = get_current_user(request)

    # 必须登录
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录"
        )

    return user


def require_admin(request: Request) -> User:
    """
    强制要求管理员权限（FastAPI Dependency）

    Args:
        request: FastAPI Request 对象

    Returns:
        User: 用户对象

    Raises:
        HTTPException: 401 未登录，403 权限不足
    """
    user = require_auth(request)

    # 检查是否为管理员
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )

    return user

