import logging
from typing import Optional
from datetime import datetime
from ..db import get_db_connection

logger = logging.getLogger(__name__)

def add_subscription(
    code: str,
    email: str,
    user_id: Optional[int],
    up: float,
    down: float,
    enable_digest: bool = False,
    digest_time: str = "14:45",
    enable_volatility: bool = True
):
    """
    Save or update a subscription for a fund/email pair.

    Args:
        code: 基金代码
        email: 邮箱地址（用于发送通知）
        user_id: 用户 ID（用于数据隔离，单用户模式为 None）
        up: 上涨阈值
        down: 下跌阈值
        enable_digest: 是否启用每日摘要
        digest_time: 摘要发送时间
        enable_volatility: 是否启用波动提醒
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # UNIQUE constraint: (code, email, user_id)
    # This allows different users to use the same email
    cursor.execute("""
        INSERT INTO subscriptions
        (code, email, user_id, threshold_up, threshold_down, enable_digest, digest_time, enable_volatility)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code, email, user_id) DO UPDATE SET
            threshold_up = excluded.threshold_up,
            threshold_down = excluded.threshold_down,
            enable_digest = excluded.enable_digest,
            digest_time = excluded.digest_time,
            enable_volatility = excluded.enable_volatility
    """, (code, email, user_id, up, down, int(enable_digest), digest_time, int(enable_volatility)))

    conn.commit()
    logger.info(f"Subscription updated: {email} -> {code} (user_id={user_id}, Volatility: {enable_volatility}, Digest: {enable_digest} @ {digest_time})")

def get_active_subscriptions():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions")
    rows = cursor.fetchall()
    return rows

def update_notification_time(sub_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE subscriptions SET last_notified_at = CURRENT_TIMESTAMP WHERE id = ?", (sub_id,))
    conn.commit()

def update_digest_time(sub_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE subscriptions SET last_digest_at = CURRENT_TIMESTAMP WHERE id = ?", (sub_id,))
    conn.commit()
    
