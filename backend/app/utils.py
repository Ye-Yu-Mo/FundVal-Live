"""
工具函数
"""
from typing import Optional
from fastapi import HTTPException, status
from .db import get_db_connection
from .auth import User, is_multi_user_mode


def verify_account_ownership(account_id: int, user: Optional[User]) -> None:
    """
    验证账户所有权

    Args:
        account_id: 账户 ID
        user: 当前用户（单用户模式下为 None）

    Raises:
        HTTPException: 404 账户不存在，403 无权访问
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账户不存在"
        )

    account_user_id = row[0]

    # 单用户模式：account_user_id 应该是 NULL
    if not is_multi_user_mode():
        if account_user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此账户"
            )
    # 多用户模式：account_user_id 应该等于 current_user.id
    else:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录"
            )
        if account_user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此账户"
            )


def get_user_id_for_query(user: Optional[User]) -> Optional[int]:
    """
    获取用于查询的 user_id

    Args:
        user: 当前用户（单用户模式下为 None）

    Returns:
        Optional[int]: 单用户模式返回 None，多用户模式返回 user.id
    """
    if not is_multi_user_mode():
        return None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录"
        )
    return user.id
