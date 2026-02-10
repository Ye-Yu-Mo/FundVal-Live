from fastapi import APIRouter, HTTPException, Body, Query, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging

from ..services.account import get_all_positions, upsert_position, remove_position
from ..services.trade import add_position_trade, reduce_position_trade, list_transactions
from ..db import get_db_connection
from ..auth import User, get_current_user
from ..utils import verify_account_ownership, get_user_id_for_query

logger = logging.getLogger(__name__)

router = APIRouter()

class AccountModel(BaseModel):
    name: str
    description: Optional[str] = ""

class PositionModel(BaseModel):
    code: str
    cost: float
    shares: float


class AddTradeModel(BaseModel):
    amount: float
    trade_time: Optional[str] = None  # ISO datetime, e.g. 2025-02-05T14:30:00


class ReduceTradeModel(BaseModel):
    shares: float
    trade_time: Optional[str] = None

# Account management endpoints
@router.get("/accounts")
def list_accounts(current_user: Optional[User] = Depends(get_current_user)):
    """获取当前用户的所有账户"""
    try:
        user_id = get_user_id_for_query(current_user)
        conn = get_db_connection()
        cursor = conn.cursor()

        if user_id is None:
            # 单用户模式：返回 user_id IS NULL 的账户
            cursor.execute("SELECT * FROM accounts WHERE user_id IS NULL ORDER BY id")
        else:
            # 多用户模式：返回当前用户的账户
            cursor.execute("SELECT * FROM accounts WHERE user_id = ? ORDER BY id", (user_id,))

        accounts = [dict(row) for row in cursor.fetchall()]
        
        return {"accounts": accounts}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/accounts")
def create_account(data: AccountModel, current_user: Optional[User] = Depends(get_current_user)):
    """创建新账户"""
    try:
        user_id = get_user_id_for_query(current_user)
        conn = get_db_connection()
        cursor = conn.cursor()

        if user_id is None:
            # 单用户模式：user_id = NULL
            cursor.execute(
                "INSERT INTO accounts (name, description, user_id) VALUES (?, ?, NULL)",
                (data.name, data.description)
            )
        else:
            # 多用户模式：user_id = current_user.id
            cursor.execute(
                "INSERT INTO accounts (name, description, user_id) VALUES (?, ?, ?)",
                (data.name, data.description, user_id)
            )

        account_id = cursor.lastrowid
        conn.commit()
        return {"id": account_id, "name": data.name}
    except HTTPException:
        raise
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="账户名称已存在")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/accounts/{account_id}")
def update_account(
    account_id: int,
    data: AccountModel,
    current_user: Optional[User] = Depends(get_current_user)
):
    """更新账户信息"""
    # 验证所有权
    verify_account_ownership(account_id, current_user)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE accounts SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (data.name, data.description, account_id)
        )
        conn.commit()
        
        return {"status": "ok"}
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="账户名称已存在")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, current_user: Optional[User] = Depends(get_current_user)):
    """删除账户（需检查是否有持仓）"""
    # 验证所有权
    verify_account_ownership(account_id, current_user)

    # 不允许删除 ID=1 的默认账户（仅单用户模式）
    if account_id == 1:
        user_id = get_user_id_for_query(current_user)
        if user_id is None:
            raise HTTPException(status_code=400, detail="默认账户不可删除")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查是否有持仓
        cursor.execute("SELECT COUNT(*) as cnt FROM positions WHERE account_id = ?", (account_id,))
        count = cursor.fetchone()["cnt"]

        if count > 0:
            
            raise HTTPException(status_code=400, detail="账户下有持仓，无法删除")

        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()
        

        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Position endpoints
@router.get("/positions/aggregate")
def get_aggregate_positions(current_user: Optional[User] = Depends(get_current_user)):
    """获取当前用户所有账户的聚合持仓"""
    try:
        user_id = get_user_id_for_query(current_user)

        # 获取用户的所有账户
        conn = get_db_connection()
        cursor = conn.cursor()

        if user_id is None:
            # 单用户模式：获取所有 user_id IS NULL 的账户
            cursor.execute("SELECT id FROM accounts WHERE user_id IS NULL")
        else:
            # 多用户模式：获取当前用户的账户
            cursor.execute("SELECT id FROM accounts WHERE user_id = ?", (user_id,))

        account_ids = [row["id"] for row in cursor.fetchall()]
        

        if not account_ids:
            return {
                "summary": {
                    "total_market_value": 0.0,
                    "total_cost": 0.0,
                    "total_day_income": 0.0,
                    "total_income": 0.0,
                    "total_return_rate": 0.0
                },
                "positions": []
            }

        # 获取所有账户的持仓并聚合
        from ..services.account import get_combined_valuation, get_fund_type
        from concurrent.futures import ThreadPoolExecutor, as_completed

        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取所有持仓
        # Defensive: Limit batch size to prevent SQL statement overflow
        if len(account_ids) > 100:
            raise HTTPException(
                status_code=400,
                detail=f"Too many accounts ({len(account_ids)}), maximum 100 allowed"
            )

        placeholders = ",".join("?" * len(account_ids))
        cursor.execute(
            f"SELECT * FROM positions WHERE account_id IN ({placeholders}) AND shares > 0",
            account_ids
        )
        rows = cursor.fetchall()
        

        # 按基金代码聚合
        code_positions = {}
        for row in rows:
            code = row["code"]
            if code not in code_positions:
                code_positions[code] = {
                    "cost": 0.0,
                    "shares": 0.0,
                    "total_cost_basis": 0.0
                }
            # 累加份额和成本基础
            shares = float(row["shares"])
            cost = float(row["cost"])
            code_positions[code]["shares"] += shares
            code_positions[code]["total_cost_basis"] += shares * cost

        # 计算加权平均成本
        position_map = {}
        for code, data in code_positions.items():
            if data["shares"] > 0:
                weighted_avg_cost = data["total_cost_basis"] / data["shares"]
                position_map[code] = {
                    "code": code,
                    "cost": weighted_avg_cost,
                    "shares": data["shares"]
                }

        # 获取实时估值（复用 get_all_positions 的逻辑）
        positions = []
        total_market_value = 0.0
        total_cost = 0.0
        total_day_income = 0.0

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_code = {
                executor.submit(get_combined_valuation, code): code
                for code in position_map.keys()
            }

            for future in as_completed(future_to_code):
                code = future_to_code[future]
                row = position_map[code]

                try:
                    data = future.result() or {}
                    name = data.get("name")
                    fund_type = None

                    if not name:
                        conn_temp = get_db_connection()
                        try:
                            cursor_temp = conn_temp.cursor()
                            cursor_temp.execute("SELECT name, type FROM funds WHERE code = ?", (code,))
                            db_row = cursor_temp.fetchone()
                            if db_row:
                                name = db_row["name"]
                                fund_type = db_row["type"]
                            else:
                                name = code
                        finally:
                            conn_temp.close()

                    if not fund_type:
                        fund_type = get_fund_type(code, name)

                    from datetime import datetime
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    conn_temp = get_db_connection()
                    try:
                        cursor_temp = conn_temp.cursor()
                        cursor_temp.execute(
                            "SELECT date FROM fund_history WHERE code = ? ORDER BY date DESC LIMIT 1",
                            (code,)
                        )
                        latest_nav_row = cursor_temp.fetchone()
                        nav_updated_today = latest_nav_row and latest_nav_row["date"] == today_str
                    finally:
                        conn_temp.close()

                    nav = float(data.get("nav", 0.0))
                    estimate = float(data.get("estimate", 0.0))
                    current_price = estimate if estimate > 0 else nav

                    cost = float(row["cost"])
                    shares = float(row["shares"])

                    nav_market_value = nav * shares
                    cost_basis = cost * shares

                    est_rate = data.get("est_rate", data.get("estRate", 0.0))

                    is_est_valid = False
                    if estimate > 0 and nav > 0:
                        if abs(est_rate) < 10.0 or "ETF" in name or "联接" in name:
                            is_est_valid = True

                    accumulated_income = nav_market_value - cost_basis
                    accumulated_return_rate = (accumulated_income / cost_basis * 100) if cost_basis > 0 else 0.0

                    if is_est_valid:
                        day_income = (estimate - nav) * shares
                        est_market_value = estimate * shares
                    else:
                        day_income = 0.0
                        est_market_value = nav_market_value

                    total_income = accumulated_income + day_income
                    total_return_rate = (total_income / cost_basis * 100) if cost_basis > 0 else 0.0

                    positions.append({
                        "code": code,
                        "name": name,
                        "type": fund_type,
                        "cost": cost,
                        "shares": shares,
                        "nav": nav,
                        "nav_date": data.get("navDate", "--"),
                        "nav_updated_today": nav_updated_today,
                        "estimate": estimate,
                        "est_rate": est_rate,
                        "is_est_valid": is_est_valid,
                        "cost_basis": round(cost_basis, 2),
                        "nav_market_value": round(nav_market_value, 2),
                        "est_market_value": round(est_market_value, 2),
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

        total_income = total_market_value - total_cost
        total_return_rate = (total_income / total_cost * 100) if total_cost > 0 else 0.0

        return {
            "summary": {
                "total_market_value": round(total_market_value, 2),
                "total_cost": round(total_cost, 2),
                "total_day_income": round(total_day_income, 2),
                "total_income": round(total_income, 2),
                "total_return_rate": round(total_return_rate, 2)
            },
            "positions": sorted(positions, key=lambda x: x["nav_market_value"], reverse=True)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/account/positions")
def get_positions(
    account_id: int = Query(..., description="账户 ID"),
    current_user: Optional[User] = Depends(get_current_user)
):
    """获取指定账户的持仓"""
    # 验证所有权
    verify_account_ownership(account_id, current_user)

    try:
        user_id = get_user_id_for_query(current_user)
        return get_all_positions(account_id, user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/account/positions/update-nav")
def update_positions_nav(
    account_id: int = Query(..., description="账户 ID"),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    手动更新持仓基金的净值。
    拉取所有持仓基金的最新净值并更新 fund_history 表。
    只有当日净值已公布才算更新成功。
    """
    # 验证所有权
    verify_account_ownership(account_id, current_user)

    import time
    from datetime import datetime
    from ..services.fund import get_fund_history

    try:
        # Get all holdings for this account
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT code FROM positions WHERE account_id = ? AND shares > 0", (account_id,))
        codes = [row["code"] for row in cursor.fetchall()]
        

        if not codes:
            return {"ok": True, "message": "无持仓基金", "updated": 0, "pending": 0, "failed": 0}

        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")

        # Update NAV for each fund
        updated = 0  # 当日净值已更新
        pending = 0  # 当日净值未公布
        failed = []  # 拉取失败

        for code in codes:
            try:
                history = get_fund_history(code, limit=5)
                if history:
                    # Check if latest NAV is today's
                    latest_date = history[-1]["date"]
                    if latest_date == today:
                        updated += 1
                    else:
                        pending += 1
                else:
                    failed.append({"code": code, "error": "无历史数据"})
                time.sleep(0.3)  # Avoid API rate limiting
            except Exception as e:
                failed.append({"code": code, "error": str(e)})

        # Build message
        msg_parts = []
        if updated > 0:
            msg_parts.append(f"{updated} 个已更新当日净值")
        if pending > 0:
            msg_parts.append(f"{pending} 个净值未公布")
        if failed:
            msg_parts.append(f"{len(failed)} 个拉取失败")

        message = "、".join(msg_parts) if msg_parts else "无数据"

        return {
            "ok": True,
            "message": message,
            "updated": updated,
            "pending": pending,
            "failed_count": len(failed),
            "total": len(codes),
            "failed": failed if failed else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/account/positions")
def update_position(
    data: PositionModel,
    account_id: int = Query(..., description="账户 ID"),
    current_user: Optional[User] = Depends(get_current_user)
):
    """更新持仓（指定账户）"""
    # 验证所有权
    verify_account_ownership(account_id, current_user)

    try:
        user_id = get_user_id_for_query(current_user)
        upsert_position(account_id, data.code, data.cost, data.shares, user_id)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/account/positions/{code}")
def delete_position(
    code: str,
    account_id: int = Query(..., description="账户 ID"),
    current_user: Optional[User] = Depends(get_current_user)
):
    """删除持仓（指定账户）"""
    # 验证所有权
    verify_account_ownership(account_id, current_user)

    try:
        user_id = get_user_id_for_query(current_user)
        remove_position(account_id, code, user_id)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/account/positions/{code}/add")
def add_trade(
    code: str,
    data: AddTradeModel,
    account_id: int = Query(..., description="账户 ID"),
    current_user: Optional[User] = Depends(get_current_user)
):
    """加仓（指定账户）"""
    # 验证所有权
    verify_account_ownership(account_id, current_user)

    from datetime import datetime
    trade_ts = None
    if data.trade_time:
        try:
            trade_ts = datetime.fromisoformat(data.trade_time.replace("Z", "+00:00"))
            if trade_ts.tzinfo:
                trade_ts = trade_ts.replace(tzinfo=None)
        except Exception:
            pass
    try:
        user_id = get_user_id_for_query(current_user)
        result = add_position_trade(account_id, code, data.amount, trade_ts, user_id)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("message", "加仓失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/account/positions/{code}/reduce")
def reduce_trade(
    code: str,
    data: ReduceTradeModel,
    account_id: int = Query(..., description="账户 ID"),
    current_user: Optional[User] = Depends(get_current_user)
):
    """减仓（指定账户）"""
    # 验证所有权
    verify_account_ownership(account_id, current_user)

    from datetime import datetime
    trade_ts = None
    if data.trade_time:
        try:
            trade_ts = datetime.fromisoformat(data.trade_time.replace("Z", "+00:00"))
            if trade_ts.tzinfo:
                trade_ts = trade_ts.replace(tzinfo=None)
        except Exception:
            pass
    try:
        user_id = get_user_id_for_query(current_user)
        result = reduce_position_trade(account_id, code, data.shares, trade_ts, user_id)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("message", "减仓失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/account/transactions")
def get_transactions(
    account_id: int = Query(..., description="账户 ID"),
    code: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    current_user: Optional[User] = Depends(get_current_user)
):
    """获取交易记录（指定账户）"""
    # 验证所有权
    verify_account_ownership(account_id, current_user)

    try:
        user_id = get_user_id_for_query(current_user)
        return {"transactions": list_transactions(account_id, code, limit, user_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
