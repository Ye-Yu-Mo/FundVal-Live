from typing import List, Dict, Any, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from ..db import get_db_connection
from .fund import get_combined_valuation, get_fund_type, get_fund_category

logger = logging.getLogger(__name__)

def get_all_positions(account_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Fetch all positions for a specific account, get real-time valuations in parallel,
    and compute portfolio statistics.

    Args:
        account_id: 账户 ID
        user_id: 用户 ID（单用户模式为 None，多用户模式为 current_user.id）

    Returns:
        Dict containing summary and positions
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM positions WHERE account_id = ? AND shares > 0", (account_id,))

    rows = cursor.fetchall()

    positions = []
    total_market_value = 0.0
    total_cost = 0.0
    total_day_income = 0.0

    # Optimization: Batch fetch fund info and NAV status for all positions
    codes = [row["code"] for row in rows]
    if not codes:
        return {
            "summary": {
                "total_market_value": 0.0,
                "total_cost": 0.0,
                "total_income": 0.0,
                "total_return_rate": 0.0,
                "total_day_income": 0.0
            },
            "positions": []
        }

    # Batch query 1: Get fund info (name, type) for all codes
    # Defensive: Limit batch size to prevent SQL statement overflow
    if len(codes) > 500:
        raise ValueError(f"Too many positions ({len(codes)}), maximum 500 allowed")

    conn_batch = get_db_connection()
    cursor_batch = conn_batch.cursor()
    placeholders = ','.join('?' * len(codes))
    cursor_batch.execute(f"""
        SELECT code, name, type FROM funds WHERE code IN ({placeholders})
    """, codes)
    fund_info_map = {row["code"]: {"name": row["name"], "type": row["type"]} for row in cursor_batch.fetchall()}

    # Batch query 2: Get latest NAV dates for all codes
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor_batch.execute(f"""
        SELECT code, MAX(date) as latest_date
        FROM fund_history
        WHERE code IN ({placeholders})
        GROUP BY code
    """, codes)
    nav_date_map = {row["code"]: row["latest_date"] for row in cursor_batch.fetchall()}

    # 1. Fetch real-time data in parallel
    position_map = {row["code"]: row for row in rows}

    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit tasks
        future_to_code = {
            executor.submit(get_combined_valuation, code): code
            for code in position_map.keys()
        }

        # Process results with timeout protection
        try:
            for future in as_completed(future_to_code, timeout=30):
                code = future_to_code[future]
                row = position_map[code]

                try:
                    # Default safe values
                    data = future.result(timeout=5) or {}

                    # Use pre-fetched fund info
                    fund_info = fund_info_map.get(code, {})
                    name = data.get("name") or fund_info.get("name") or code
                    fund_type = fund_info.get("type")

                    # Get fund type if not in cache
                    if not fund_type:
                        fund_type = get_fund_type(code, name)

                    # Use pre-fetched NAV date
                    latest_date = nav_date_map.get(code)
                    nav_updated_today = latest_date == today_str if latest_date else False

                    nav = float(data.get("nav", 0.0))
                    estimate = float(data.get("estimate", 0.0))
                    # If estimate is 0 (e.g. market closed or error), use NAV
                    current_price = estimate if estimate > 0 else nav

                    # Calculations
                    cost = float(row["cost"])
                    shares = float(row["shares"])

                    # 1. Base Metrics
                    nav_market_value = nav * shares
                    cost_basis = cost * shares

                    # 2. Estimate & Reliability Check
                    # est_rate is percent, e.g. 1.5 for +1.5%
                    est_rate = data.get("est_rate", data.get("estRate", 0.0))

                    # Validation: If estRate is absurdly high for a fund (abs > 10%), ignore estimate unless confirmed valid
                    is_est_valid = False
                    if estimate > 0 and nav > 0:
                        if abs(est_rate) < 10.0 or "ETF" in name or "联接" in name:
                            # Allow higher volatility for ETFs, but 10% is still a good sanity check for generic funds.
                            # Actually, let's stick to the 10% clamp for safety, or trust the user knows.
                            # Linus: "Trust, but verify." We'll flag it but calculate it.
                            is_est_valid = True
                        else:
                            is_est_valid = False

                    # 3. Derived Metrics

                    # A. Confirmed (Based on Yesterday's NAV)
                    accumulated_income = nav_market_value - cost_basis
                    accumulated_return_rate = (accumulated_income / cost_basis * 100) if cost_basis > 0 else 0.0

                    # B. Intraday (Based on Real-time Estimate)
                    if is_est_valid:
                        day_income = (estimate - nav) * shares
                        est_market_value = estimate * shares
                    else:
                        day_income = 0.0
                        est_market_value = nav_market_value # Fallback to confirmed value

                    # C. Total Projected
                    total_income = accumulated_income + day_income
                    total_return_rate = (total_income / cost_basis * 100) if cost_basis > 0 else 0.0

                    positions.append({
                        "code": code,
                        "name": name,
                        "type": fund_type,
                        "category": get_fund_category(fund_type),
                        "cost": cost,
                        "shares": shares,
                        "nav": nav,
                        "nav_date": data.get("navDate", "--"), # If available, else implicit
                        "nav_updated_today": nav_updated_today,
                        "estimate": estimate,
                        "est_rate": est_rate,
                        "is_est_valid": is_est_valid,

                        # Values
                        "cost_basis": round(cost_basis, 2),
                        "nav_market_value": round(nav_market_value, 2),
                        "est_market_value": round(est_market_value, 2),

                        # PnL
                        "accumulated_income": round(accumulated_income, 2),
                        "accumulated_return_rate": round(accumulated_return_rate, 2),

                        "day_income": round(day_income, 2),

                        "total_income": round(total_income, 2),
                        "total_return_rate": round(total_return_rate, 2),

                        "update_time": data.get("time", "--")
                    })

                    total_market_value += est_market_value
                    total_day_income += day_income
                    total_cost += cost_basis
                    # accumulated income sum not strictly needed for top card but good to have?
                    # Let's keep total_income as the projected total.

                except TimeoutError:
                    logger.warning(f"Timeout fetching valuation for {code}")
                    positions.append({
                        "code": code,
                        "name": "Timeout",
                        "cost": float(row["cost"]),
                        "shares": float(row["shares"]),
                        "nav": 0.0,
                        "estimate": 0.0,
                        "nav_market_value": 0.0,
                        "est_market_value": 0.0,
                        "day_income": 0.0,
                        "total_income": 0.0,
                        "total_return_rate": 0.0,
                        "accumulated_income": 0.0,
                        "est_rate": 0.0,
                        "is_est_valid": False,
                        "update_time": "--"
                    })
                except Exception as e:
                    logger.error(f"Error processing position {code}: {e}")
                    positions.append({
                        "code": code,
                        "name": "Error",
                        "cost": float(row["cost"]),
                        "shares": float(row["shares"]),
                        "nav": 0.0,
                        "estimate": 0.0,
                        "nav_market_value": 0.0,
                        "est_market_value": 0.0,
                        "day_income": 0.0,
                        "total_income": 0.0,
                        "total_return_rate": 0.0,
                        "accumulated_income": 0.0,
                        "est_rate": 0.0,
                        "is_est_valid": False,
                        "update_time": "--"
                    })
        except TimeoutError:
            logger.error("Overall timeout in parallel valuation fetch")

    total_income = total_market_value - total_cost
    total_return_rate = (total_income / total_cost * 100) if total_cost > 0 else 0.0

    return {
        "summary": {
            "total_market_value": round(total_market_value, 2), # Projected
            "total_cost": round(total_cost, 2),
            "total_day_income": round(total_day_income, 2),
            "total_income": round(total_income, 2),
            "total_return_rate": round(total_return_rate, 2)
        },
        "positions": sorted(positions, key=lambda x: x["nav_market_value"], reverse=True)
    }

def upsert_position(account_id: int, code: str, cost: float, shares: float, user_id: Optional[int] = None):
    """
    更新或插入持仓

    Args:
        account_id: 账户 ID
        code: 基金代码
        cost: 成本
        shares: 份额
        user_id: 用户 ID（用于验证，但实际不需要，因为 account_id 已经验证过所有权）
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO positions (account_id, code, cost, shares)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(account_id, code) DO UPDATE SET
            cost = excluded.cost,
            shares = excluded.shares,
            updated_at = CURRENT_TIMESTAMP
    """, (account_id, code, cost, shares))
    conn.commit()

def remove_position(account_id: int, code: str, user_id: Optional[int] = None):
    """
    删除持仓

    Args:
        account_id: 账户 ID
        code: 基金代码
        user_id: 用户 ID（用于验证，但实际不需要，因为 account_id 已经验证过所有权）
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM positions WHERE account_id = ? AND code = ?", (account_id, code))
    conn.commit()
