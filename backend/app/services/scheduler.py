import logging
import threading
import time
import akshare as ak
import pandas as pd
from ..db import get_db_connection
from ..config import Config

logger = logging.getLogger(__name__)

def fetch_and_update_funds():
    """
    Fetches the complete fund list from AkShare and updates the SQLite DB.
    This is a blocking operation, should be run in a background thread.
    """
    logger.info("Starting fund list update...")
    try:
        # Fetch data
        df = ak.fund_name_em()
        if df is None or df.empty:
            logger.warning("Fetched empty fund list from AkShare.")
            return

        # Rename columns to match our simple schema
        # Expected cols: "基金代码", "基金简称", "基金类型"
        df = df.rename(columns={
            "基金代码": "code",
            "基金简称": "name",
            "基金类型": "type"
        })
        
        # Select only relevant columns
        data_to_insert = df[["code", "name", "type"]].to_dict(orient="records")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Use transaction for speed and safety
        conn.execute("BEGIN")
        
        # Upsert logic (Replace is easier here since we just want the latest list)
        # Using executemany is much faster than looping
        cursor.executemany("""
            INSERT OR REPLACE INTO funds (code, name, type, updated_at)
            VALUES (:code, :name, :type, CURRENT_TIMESTAMP)
        """, data_to_insert)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Fund list updated. Total funds: {len(data_to_insert)}")
        
    except Exception as e:
        logger.error(f"Failed to update fund list: {e}")

from ..services.fund import get_combined_valuation
from ..services.subscription import get_active_subscriptions, update_notification_time
from ..services.email import send_email

def check_subscriptions():
    """
    Check all subscriptions and send alerts.
    """
    logger.info("Checking subscriptions...")
    subs = get_active_subscriptions()
    if not subs:
        return

    # Cache valuations during this run to avoid duplicate API calls
    valuations = {}

    for sub in subs:
        code = sub["code"]
        if code not in valuations:
            valuations[code] = get_combined_valuation(code)
        
        data = valuations[code]
        if not data: continue
        
        est_rate = data.get("estRate", 0.0)
        
        # Check if already notified today
        # last_notified_at is a string like "2026-02-02 10:00:00"
        last_notified = sub["last_notified_at"]
        today_str = datetime.now().strftime("%Y-%m-%d")
        if last_notified and last_notified.startswith(today_str):
            continue

        triggered = False
        reason = ""
        
        if sub["threshold_up"] > 0 and est_rate >= sub["threshold_up"]:
            triggered = True
            reason = f"上涨已达到 {est_rate}% (阈值: {sub['threshold_up']}%)"
        elif sub["threshold_down"] < 0 and est_rate <= sub["threshold_down"]:
            triggered = True
            reason = f"下跌已达到 {est_rate}% (阈值: {sub['threshold_down']}%)"
        
        if triggered:
            subject = f"【FundVal 提醒】基金 {data.get('name', code)} 预估异动"
            content = f"""
            <h3>基金异动提醒</h3>
            <p>基金: {data.get('name')} ({code})</p>
            <p>当前预估涨跌幅: <b>{est_rate}%</b></p>
            <p>触发原因: {reason}</p>
            <p>估值时间: {data.get('time')}</p>
            <hr/>
            <p>此邮件由 FundVal Live 自动发送。</p>
            """
            success = send_email(sub["email"], subject, content, is_html=True)
            if success:
                update_notification_time(sub["id"])

def start_scheduler():
    """
    Simple background thread to check if data needs update.
    """
    def _run():
        # 1. Initial fund list update
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) as cnt FROM funds")
        count = cursor.fetchone()["cnt"]
        conn.close()
        
        if count == 0:
            logger.info("DB is empty. Performing initial fetch.")
            fetch_and_update_funds()
            
        # 2. Main loop
        while True:
            try:
                # Only check during market hours (approx 9:00 - 15:30)
                now = datetime.now()
                if 9 <= now.hour <= 15:
                    check_subscriptions()
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            
            # Wait 10 minutes
            time.sleep(600)
    
    t = threading.Thread(target=_run, daemon=True)
    t.start()

from datetime import datetime
