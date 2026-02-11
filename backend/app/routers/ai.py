from fastapi import APIRouter, Body, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from ..services.ai import ai_service
from ..db import get_db_connection
from ..auth import get_current_user, User, require_auth

router = APIRouter()

class PromptModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    system_prompt: str = Field(..., min_length=1, max_length=10000)
    user_prompt: str = Field(..., min_length=1, max_length=10000)
    is_default: bool = False

@router.post("/ai/analyze_fund")
async def analyze_fund(
    fund_info: Dict[str, Any] = Body(...),
    prompt_id: int = Body(None),
    current_user: User = Depends(require_auth)
):
    """
    分析基金（需要认证）
    """
    return await ai_service.analyze_fund(fund_info, prompt_id=prompt_id, user_id=current_user.id)

@router.get("/ai/prompts")
def get_prompts(current_user: User = Depends(require_auth)):
    """
    获取 AI 提示词模板（按用户隔离）
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, system_prompt, user_prompt, is_default, created_at, updated_at
        FROM ai_prompts
        WHERE user_id = ?
        ORDER BY is_default DESC, id ASC
    """, (current_user.id,))

    prompts = [dict(row) for row in cursor.fetchall()]
    return {"prompts": prompts}

@router.post("/ai/prompts")
def create_prompt(
    data: PromptModel,
    current_user: User = Depends(require_auth)
):
    """
    创建新的 AI 提示词模板（需要认证）
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # If this is set as default, unset other defaults for this user
    if data.is_default:
        cursor.execute("UPDATE ai_prompts SET is_default = 0 WHERE user_id = ?", (current_user.id,))

    # Insert with user_id
    cursor.execute("""
        INSERT INTO ai_prompts (name, system_prompt, user_prompt, user_id, is_default)
        VALUES (?, ?, ?, ?, ?)
    """, (data.name, data.system_prompt, data.user_prompt, current_user.id, 1 if data.is_default else 0))

    prompt_id = cursor.lastrowid
    conn.commit()

    return {"ok": True, "id": prompt_id}

@router.put("/ai/prompts/{prompt_id}")
def update_prompt(
    prompt_id: int,
    data: PromptModel,
    current_user: User = Depends(require_auth)
):
    """
    更新 AI 提示词模板（需要认证，只能更新自己的）
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if prompt exists and belongs to user
    cursor.execute("SELECT id FROM ai_prompts WHERE id = ? AND user_id = ?", (prompt_id, current_user.id))

    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Prompt not found or access denied")

    # If this is set as default, unset other defaults for this user
    if data.is_default:
        cursor.execute("UPDATE ai_prompts SET is_default = 0 WHERE id != ? AND user_id = ?", (prompt_id, current_user.id))

    cursor.execute("""
        UPDATE ai_prompts
        SET name = ?, system_prompt = ?, user_prompt = ?, is_default = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (data.name, data.system_prompt, data.user_prompt, 1 if data.is_default else 0, prompt_id))

    conn.commit()

    return {"ok": True}

@router.delete("/ai/prompts/{prompt_id}")
def delete_prompt(
    prompt_id: int,
    current_user: User = Depends(require_auth)
):
    """
    删除 AI 提示词模板（需要认证，只能删除自己的）
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if prompt exists and belongs to user
    cursor.execute("SELECT is_default FROM ai_prompts WHERE id = ? AND user_id = ?", (prompt_id, current_user.id))

    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Prompt not found or access denied")

    if row["is_default"]:
        raise HTTPException(status_code=400, detail="不能删除默认模板")

    cursor.execute("DELETE FROM ai_prompts WHERE id = ?", (prompt_id,))
    conn.commit()

    return {"ok": True}

@router.get("/ai/analysis_history")
def get_analysis_history(
    fund_code: str,
    account_id: int = 1,
    limit: int = 20,
    offset: int = 0,
    prompt_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(require_auth)
):
    """
    获取 AI 分析历史记录列表（不返回 markdown，减少数据量）
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Build query
    query = """
        SELECT id, fund_code, fund_name, prompt_name, status, created_at
        FROM ai_analysis_history
        WHERE account_id = ? AND fund_code = ? AND user_id = ?
    """
    params = [account_id, fund_code, current_user.id]

    # Add optional filters
    if prompt_id is not None:
        query += " AND prompt_id = ?"
        params.append(prompt_id)

    if date_from:
        query += " AND created_at >= ?"
        params.append(date_from)

    if date_to:
        query += " AND created_at <= ?"
        params.append(date_to)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    records = [dict(row) for row in cursor.fetchall()]

    return {"records": records}

@router.get("/ai/analysis_history/{history_id}")
def get_analysis_history_detail(
    history_id: int,
    current_user: User = Depends(require_auth)
):
    """
    获取单条 AI 分析历史记录详情（包含 markdown）
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM ai_analysis_history
        WHERE id = ? AND user_id = ?
    """, (history_id, current_user.id))

    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="History record not found or access denied")

    return dict(row)

@router.delete("/ai/analysis_history/{history_id}")
def delete_analysis_history(
    history_id: int,
    current_user: User = Depends(require_auth)
):
    """
    删除 AI 分析历史记录（只能删除自己的）
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if record exists and belongs to user
    cursor.execute("SELECT id FROM ai_analysis_history WHERE id = ? AND user_id = ?", (history_id, current_user.id))

    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="History record not found or access denied")

    try:
        cursor.execute("DELETE FROM ai_analysis_history WHERE id = ?", (history_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete record")

    return {"ok": True}
