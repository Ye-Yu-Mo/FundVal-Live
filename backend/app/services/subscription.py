import logging
from datetime import datetime
from ..db import get_db_connection

logger = logging.getLogger(__name__)

def add_subscription(code: str, email: str, up: float, down: float):
    """
    Save or update a subscription for a fund/email pair.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # We allow one subscription per fund+email combination
    cursor.execute("""
        INSERT INTO subscriptions (code, email, threshold_up, threshold_down)
        VALUES (?, ?, ?, ?)
    """, (code, email, up, down))
    
    conn.commit()
    conn.close()
    logger.info(f"Subscription added: {email} -> {code} (Up: {up}%, Down: {down}%)")

def get_active_subscriptions():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Logic for "active": maybe skip if notified in last 4 hours?
    cursor.execute("SELECT * FROM subscriptions")
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_notification_time(sub_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE subscriptions SET last_notified_at = CURRENT_TIMESTAMP WHERE id = ?", (sub_id,))
    conn.commit()
    conn.close()
