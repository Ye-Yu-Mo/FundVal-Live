from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional

from ..services.account import get_all_positions, upsert_position, remove_position
from ..services.trade import add_position_trade, reduce_position_trade, list_transactions

router = APIRouter()

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

@router.get("/account/positions")
def get_positions():
    try:
        return get_all_positions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/account/positions")
def update_position(data: PositionModel):
    try:
        upsert_position(data.code, data.cost, data.shares)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/account/positions/{code}")
def delete_position(code: str):
    try:
        remove_position(code)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/account/positions/{code}/add")
def add_trade(code: str, data: AddTradeModel):
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
        result = add_position_trade(code, data.amount, trade_ts)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("message", "加仓失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/account/positions/{code}/reduce")
def reduce_trade(code: str, data: ReduceTradeModel):
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
        result = reduce_position_trade(code, data.shares, trade_ts)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("message", "减仓失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/account/transactions")
def get_transactions(code: Optional[str] = Query(None), limit: int = Query(100, le=500)):
    try:
        return {"transactions": list_transactions(code=code, limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
