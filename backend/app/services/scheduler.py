import logging
import threading
import time
from datetime import datetime, timedelta, timezone
import akshare as ak
import pandas as pd
from ..db import get_db_connection
from ..config import Config
from ..services.fund import get_combined_valuation
from ..services.subscription import get_active_subscriptions, update_notification_time
from ..services.email import send_email
from ..services.trade import process_pending_transactions

logger = logging.getLogger(__name__)

# Define China Standard Time (UTC+8)
CST = timezone(timedelta(hours=8))

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

from ..services.subscription import get_active_subscriptions, update_notification_time, update_digest_time

def check_subscriptions():
    """
    Check all subscriptions and send alerts (Volatility & Digest).
    """
    logger.info("Checking subscriptions...")
    subs = get_active_subscriptions()
    if not subs:
        return

    now_cst = datetime.now(CST)
    today_str = now_cst.strftime("%Y-%m-%d")
    current_time_str = now_cst.strftime("%H:%M")

    # Cache valuations during this run to avoid duplicate API calls
    valuations = {}

    for sub in subs:
        code = sub["code"]
        sub_id = sub["id"]
        email = sub["email"]
        
        # 1. Fetch data if needed
        if code not in valuations:
            valuations[code] = get_combined_valuation(code)
        
        data = valuations[code]
        if not data: continue
        
        est_rate = data.get("estRate", 0.0)
        fund_name = data.get("name", code)

        # --- Sub-task A: Real-time Volatility Alert ---
        # Logic: If volatility enabled AND threshold crossed AND not yet notified today
        if sub["enable_volatility"]:
            last_notified = sub["last_notified_at"]
            if not (last_notified and last_notified.startswith(today_str)):
                triggered = False
                reason = ""
                
                if sub["threshold_up"] > 0 and est_rate >= sub["threshold_up"]:
                    triggered = True
                    reason = f"上涨已达到 {est_rate}% (阈值: {sub['threshold_up']}%)"
                elif sub["threshold_down"] < 0 and est_rate <= sub["threshold_down"]:
                    triggered = True
                    reason = f"下跌已达到 {est_rate}% (阈值: {sub['threshold_down']}%)"
                
                if triggered:
                    subject = f"【异动提醒】{fund_name} ({code}) 预估 {est_rate}%"
                    content = f"""
                    <h3>基金异动提醒</h3>
                    <p>基金: {fund_name} ({code})</p>
                    <p>当前预估涨跌幅: <b>{est_rate}%</b></p>
                    <p>触发原因: {reason}</p>
                    <p>估值时间: {data.get('time')}</p>
                    <hr/>
                    <p>此邮件由 FundVal Live 自动发送。</p>
                    """
                    if send_email(email, subject, content, is_html=True):
                        update_notification_time(sub_id)

        # --- Sub-task B: Daily Scheduled Digest ---
        # Logic: If digest enabled AND current time >= digest time AND not yet sent today
        if sub["enable_digest"]:
            last_digest = sub["last_digest_at"]
            if not (last_digest and last_digest.startswith(today_str)):
                # If we are at or past the scheduled time
                if current_time_str >= sub["digest_time"]:
                    subject = f"【每日总结】{fund_name} ({code}) 今日估值汇总"
                    content = f"""
                    <h3>每日基金总结</h3>
                    <p>基金: {fund_name} ({code})</p>
                    <p>今日收盘/最新估值: {data.get('estimate', 'N/A')}</p>
                    <p>今日涨跌幅: <b>{est_rate}%</b></p>
                    <p>总结时间: {now_cst.strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <hr/>
                    <p>祝您投资愉快！</p>
                    """
                    if send_email(email, subject, content, is_html=True):
                        update_digest_time(sub_id)

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
                # 24/7 Monitoring
                check_subscriptions()
                # 待确认加仓/减仓：用当日已公布净值更新持仓
                n = process_pending_transactions()
                if n:
                    logger.info(f"Applied {n} pending add/reduce transactions.")
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            
            # Check every 5 minutes for better time precision on digests
            time.sleep(300)
    
    t = threading.Thread(target=_run, daemon=True)
    t.start()
