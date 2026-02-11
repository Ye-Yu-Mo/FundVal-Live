"""
工具函数
"""
from typing import Optional
from fastapi import HTTPException, status
from .db import get_db_connection
from .auth import User


def verify_account_ownership(account_id: int, user: User) -> None:
    """
    验证账户所有权

    Args:
        account_id: 账户 ID
        user: 当前用户

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

    # 检查账户所有权（管理员可以访问所有账户）
    if account_user_id != user.id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此账户"
        )
