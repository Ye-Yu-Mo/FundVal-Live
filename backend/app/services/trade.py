# -*- coding: utf-8 -*-
"""
加仓/减仓：T+1 确认后用真实净值更新持仓，并写入操作记录。
"""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from ..db import get_db_connection
from .fund import get_nav_on_date
from .account import upsert_position, remove_position
from .trading_calendar import get_confirm_date, confirm_date_to_str

logger = logging.getLogger(__name__)


def _get_position(code: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT code, cost, shares FROM positions WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"code": row["code"], "cost": float(row["cost"]), "shares": float(row["shares"])}


def add_position_trade(code: str, amount_cny: float, trade_ts: Optional[datetime] = None) -> Dict[str, Any]:
    """
    加仓：按交易时间确定确认日，若该日净值已公布则立即更新持仓并记流水；
    否则写入待确认流水，等定时任务用真实净值补算。
    """
    if amount_cny <= 0:
        return {"ok": False, "message": "加仓金额必须大于 0"}
    confirm_d = get_confirm_date(trade_ts)
    confirm_date_str = confirm_date_to_str(confirm_d)
    nav = get_nav_on_date(code, confirm_date_str)

    conn = get_db_connection()
    cursor = conn.cursor()

    if nav and nav > 0:
        shares_added = round(amount_cny / nav, 4)
        pos = _get_position(code)
        if pos:
            old_cost, old_shares = pos["cost"], pos["shares"]
            new_shares = old_shares + shares_added
            new_cost = round((old_cost * old_shares + nav * shares_added) / new_shares, 4)
        else:
            new_shares = shares_added
            new_cost = nav
        upsert_position(code, new_cost, new_shares)
        cursor.execute(
            """
            INSERT INTO transactions (code, op_type, amount_cny, confirm_date, confirm_nav, shares_added, cost_after, applied_at)
            VALUES (?, 'add', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (code, amount_cny, confirm_date_str, nav, shares_added, new_cost),
        )
        conn.commit()
        conn.close()
        return {
            "ok": True,
            "confirm_date": confirm_date_str,
            "confirm_nav": nav,
            "shares_added": shares_added,
            "cost_after": new_cost,
            "shares_after": new_shares,
        }
    else:
        cursor.execute(
            """
            INSERT INTO transactions (code, op_type, amount_cny, confirm_date, confirm_nav, shares_added, cost_after, applied_at)
            VALUES (?, 'add', ?, ?, NULL, NULL, NULL, NULL)
            """,
            (code, amount_cny, confirm_date_str),
        )
        conn.commit()
        conn.close()
        return {
            "ok": True,
            "pending": True,
            "message": f"已记录加仓，确认日为 {confirm_date_str}，待净值公布后自动更新持仓",
            "confirm_date": confirm_date_str,
        }


def reduce_position_trade(code: str, shares_redeemed: float, trade_ts: Optional[datetime] = None) -> Dict[str, Any]:
    """
    减仓：按交易时间确定确认日，若该日净值已公布则立即扣减份额并记流水；否则待确认。
    """
    if shares_redeemed <= 0:
        return {"ok": False, "message": "减仓份额必须大于 0"}
    pos = _get_position(code)
    if not pos or pos["shares"] <= 0:
        return {"ok": False, "message": "该基金无持仓或份额为 0"}
    if shares_redeemed > pos["shares"]:
        return {"ok": False, "message": f"减仓份额不能大于当前持仓 {pos['shares']}"}

    confirm_d = get_confirm_date(trade_ts)
    confirm_date_str = confirm_date_to_str(confirm_d)
    nav = get_nav_on_date(code, confirm_date_str)

    conn = get_db_connection()
    cursor = conn.cursor()

    if nav and nav > 0:
        amount_cny = round(shares_redeemed * nav, 2)
        new_shares = round(pos["shares"] - shares_redeemed, 4)
        new_cost = pos["cost"]
        if new_shares <= 0:
            remove_position(code)
            cost_after = 0.0
        else:
            upsert_position(code, new_cost, new_shares)
            cost_after = new_cost
        cursor.execute(
            """
            INSERT INTO transactions (code, op_type, amount_cny, shares_redeemed, confirm_date, confirm_nav, cost_after, applied_at)
            VALUES (?, 'reduce', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (code, amount_cny, shares_redeemed, confirm_date_str, nav, cost_after),
        )
        conn.commit()
        conn.close()
        return {
            "ok": True,
            "confirm_date": confirm_date_str,
            "confirm_nav": nav,
            "amount_cny": amount_cny,
            "shares_after": new_shares,
        }
    else:
        cursor.execute(
            """
            INSERT INTO transactions (code, op_type, amount_cny, shares_redeemed, confirm_date, confirm_nav, cost_after, applied_at)
            VALUES (?, 'reduce', NULL, ?, ?, NULL, NULL, NULL)
            """,
            (code, shares_redeemed, confirm_date_str),
        )
        conn.commit()
        conn.close()
        return {
            "ok": True,
            "pending": True,
            "message": f"已记录减仓，确认日为 {confirm_date_str}，待净值公布后自动更新持仓",
            "confirm_date": confirm_date_str,
        }


def list_transactions(code: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """操作记录列表，可选按基金筛选。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if code:
        cursor.execute(
            """
            SELECT id, code, op_type, amount_cny, shares_redeemed, confirm_date, confirm_nav,
                   shares_added, cost_after, created_at, applied_at
            FROM transactions WHERE code = ? ORDER BY id DESC LIMIT ?
            """,
            (code, limit),
        )
    else:
        cursor.execute(
            """
            SELECT id, code, op_type, amount_cny, shares_redeemed, confirm_date, confirm_nav,
                   shares_added, cost_after, created_at, applied_at
            FROM transactions ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        )
    rows = cursor.fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "code": r["code"],
            "op_type": r["op_type"],
            "amount_cny": r["amount_cny"],
            "shares_redeemed": r["shares_redeemed"],
            "confirm_date": r["confirm_date"],
            "confirm_nav": r["confirm_nav"],
            "shares_added": r["shares_added"],
            "cost_after": r["cost_after"],
            "created_at": r["created_at"],
            "applied_at": r["applied_at"],
        })
    return out


def process_pending_transactions() -> int:
    """处理待确认流水：对 confirm_nav 为空的记录拉取确认日净值并更新持仓。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, code, op_type, amount_cny, shares_redeemed, confirm_date FROM transactions WHERE applied_at IS NULL AND confirm_nav IS NULL"
    )
    pending = cursor.fetchall()
    conn.close()
    applied = 0
    for row in pending:
        tid, code, op_type, amount_cny, shares_redeemed, confirm_date = (
            row["id"], row["code"], row["op_type"], row["amount_cny"], row["shares_redeemed"], row["confirm_date"]
        )
        nav = get_nav_on_date(code, confirm_date) if confirm_date else None
        if not nav or nav <= 0:
            continue
        conn = get_db_connection()
        cursor = conn.cursor()
        if op_type == "add" and amount_cny:
            shares_added = round(amount_cny / nav, 4)
            pos = _get_position(code)
            if pos:
                old_c, old_s = pos["cost"], pos["shares"]
                new_shares = old_s + shares_added
                new_cost = round((old_c * old_s + nav * shares_added) / new_shares, 4)
            else:
                new_shares = shares_added
                new_cost = nav
            upsert_position(code, new_cost, new_shares)
            cursor.execute(
                "UPDATE transactions SET confirm_nav = ?, shares_added = ?, cost_after = ?, applied_at = CURRENT_TIMESTAMP WHERE id = ?",
                (nav, shares_added, new_cost, tid),
            )
        elif op_type == "reduce" and shares_redeemed:
            pos = _get_position(code)
            if not pos:
                conn.close()
                continue
            amount_cny = round(shares_redeemed * nav, 2)
            new_shares = round(pos["shares"] - shares_redeemed, 4)
            cost_after = pos["cost"] if new_shares > 0 else 0.0
            if new_shares <= 0:
                remove_position(code)
            else:
                upsert_position(code, pos["cost"], new_shares)
            cursor.execute(
                "UPDATE transactions SET confirm_nav = ?, amount_cny = ?, cost_after = ?, applied_at = CURRENT_TIMESTAMP WHERE id = ?",
                (nav, amount_cny, cost_after, tid),
            )
        else:
            conn.close()
            continue
        conn.commit()
        conn.close()
        applied += 1
    return applied
