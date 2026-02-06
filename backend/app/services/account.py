from typing import List, Dict, Any
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..db import get_db_connection
from .fund import get_combined_valuation, MAJOR_CATEGORIES

logger = logging.getLogger(__name__)

def classify_fund_simple(name: str) -> str:
    """
    Fast classification based on name keywords.
    """
    for cat, keywords in MAJOR_CATEGORIES.items():
        if any(kw in name for kw in keywords):
            return cat
    if "债" in name: return "债券"
    return "混合/其他"

def get_all_positions() -> Dict[str, Any]:
    """
    Fetch all positions, get real-time valuations in parallel,
    and compute portfolio statistics.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM positions")
    rows = cursor.fetchall()
    conn.close()

    positions = []
    total_market_value = 0.0
    total_cost = 0.0
    total_day_income = 0.0

    # 1. Fetch real-time data in parallel
    # We map code -> row data first
    position_map = {row["code"]: row for row in rows}
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit tasks
        future_to_code = {
            executor.submit(get_combined_valuation, code): code 
            for code in position_map.keys()
        }
        
        # Process results
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            row = position_map[code]
            
            try:
                # Default safe values
                data = future.result() or {}
                name = data.get("name", code)
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
                    "type": classify_fund_simple(name), # Add type here
                    "cost": cost,
                    "shares": shares,
                    "nav": nav,
                    "nav_date": data.get("navDate", "--"), # If available, else implicit
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

            except Exception as e:
                logger.error(f"Error processing position {code}: {e}")
                positions.append({
                    "code": code,
                    "name": "Error",
                    "cost": float(row["cost"]),
                    "shares": float(row["shares"]),
                    "nav": 0.0,
                    "estimate": 0.0,
                    "est_market_value": 0.0,
                    "day_income": 0.0,
                    "total_income": 0.0,
                    "total_return_rate": 0.0,
                    "accumulated_income": 0.0,
                    "est_rate": 0.0,
                    "is_est_valid": False,
                    "update_time": "--"
                })

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
        "positions": sorted(positions, key=lambda x: x["est_market_value"], reverse=True)
    }

def upsert_position(code: str, cost: float, shares: float):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO positions (code, cost, shares) 
        VALUES (?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            cost = excluded.cost,
            shares = excluded.shares,
            updated_at = CURRENT_TIMESTAMP
    """, (code, cost, shares))
    conn.commit()
    conn.close()

def remove_position(code: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM positions WHERE code = ?", (code,))
    conn.commit()
    conn.close()
