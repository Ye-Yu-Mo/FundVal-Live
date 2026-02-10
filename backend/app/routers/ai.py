from fastapi import APIRouter, Body, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from ..services.ai import ai_service
from ..db import get_db_connection
from ..auth import get_current_user, User
from ..utils import get_user_id_for_query

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
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    分析基金（需要认证）
    """
    user_id = get_user_id_for_query(current_user)
    return await ai_service.analyze_fund(fund_info, prompt_id=prompt_id, user_id=user_id)

@router.get("/ai/prompts")
def get_prompts(current_user: Optional[User] = Depends(get_current_user)):
    """
    获取 AI 提示词模板（按用户隔离）

    单用户模式：返回 user_id IS NULL 的 prompts
    多用户模式：返回当前用户的 prompts
    """
    user_id = get_user_id_for_query(current_user)

    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id is None:
        # 单用户模式：查询系统级 prompts
        cursor.execute("""
            SELECT id, name, system_prompt, user_prompt, is_default, created_at, updated_at
            FROM ai_prompts
            WHERE user_id IS NULL
            ORDER BY is_default DESC, id ASC
        """)
    else:
        # 多用户模式：查询当前用户的 prompts
        cursor.execute("""
            SELECT id, name, system_prompt, user_prompt, is_default, created_at, updated_at
            FROM ai_prompts
            WHERE user_id = ?
            ORDER BY is_default DESC, id ASC
        """, (user_id,))

    prompts = [dict(row) for row in cursor.fetchall()]
    return {"prompts": prompts}

@router.post("/ai/prompts")
def create_prompt(
    data: PromptModel,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    创建新的 AI 提示词模板（需要认证）
    """
    user_id = get_user_id_for_query(current_user)

    conn = get_db_connection()
    cursor = conn.cursor()

    # If this is set as default, unset other defaults for this user
    if data.is_default:
        if user_id is None:
            cursor.execute("UPDATE ai_prompts SET is_default = 0 WHERE user_id IS NULL")
        else:
            cursor.execute("UPDATE ai_prompts SET is_default = 0 WHERE user_id = ?", (user_id,))

    # Insert with user_id
    cursor.execute("""
        INSERT INTO ai_prompts (name, system_prompt, user_prompt, user_id, is_default)
        VALUES (?, ?, ?, ?, ?)
    """, (data.name, data.system_prompt, data.user_prompt, user_id, 1 if data.is_default else 0))

    prompt_id = cursor.lastrowid
    conn.commit()

    return {"ok": True, "id": prompt_id}

@router.put("/ai/prompts/{prompt_id}")
def update_prompt(
    prompt_id: int,
    data: PromptModel,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    更新 AI 提示词模板（需要认证，只能更新自己的）
    """
    user_id = get_user_id_for_query(current_user)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if prompt exists and belongs to user
    if user_id is None:
        cursor.execute("SELECT id FROM ai_prompts WHERE id = ? AND user_id IS NULL", (prompt_id,))
    else:
        cursor.execute("SELECT id FROM ai_prompts WHERE id = ? AND user_id = ?", (prompt_id, user_id))

    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Prompt not found or access denied")

    # If this is set as default, unset other defaults for this user
    if data.is_default:
        if user_id is None:
            cursor.execute("UPDATE ai_prompts SET is_default = 0 WHERE id != ? AND user_id IS NULL", (prompt_id,))
        else:
            cursor.execute("UPDATE ai_prompts SET is_default = 0 WHERE id != ? AND user_id = ?", (prompt_id, user_id))

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
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    删除 AI 提示词模板（需要认证，只能删除自己的）
    """
    user_id = get_user_id_for_query(current_user)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if prompt exists and belongs to user
    if user_id is None:
        cursor.execute("SELECT is_default FROM ai_prompts WHERE id = ? AND user_id IS NULL", (prompt_id,))
    else:
        cursor.execute("SELECT is_default FROM ai_prompts WHERE id = ? AND user_id = ?", (prompt_id, user_id))

    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Prompt not found or access denied")

    if row["is_default"]:
        raise HTTPException(status_code=400, detail="不能删除默认模板")

    cursor.execute("DELETE FROM ai_prompts WHERE id = ?", (prompt_id,))
    conn.commit()

    return {"ok": True}
