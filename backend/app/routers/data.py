from fastapi import APIRouter, HTTPException, Body, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel
import json
import io
import datetime

from ..services.data_io import export_data, import_data
from ..auth import get_current_user, User, require_auth

router = APIRouter()

# Valid module names
VALID_MODULES = ["accounts", "positions", "transactions", "ai_prompts", "subscriptions", "settings"]


class ImportRequest(BaseModel):
    data: dict
    modules: List[str]
    mode: str = "merge"


@router.get("/data/export")
def export_data_endpoint(
    modules: Optional[str] = None,
    current_user: User = Depends(require_auth)
):
    """
    导出数据到 JSON 文件（需要认证）

    Query Parameters:
        modules: 逗号分隔的模块列表，如 "accounts,positions,transactions"
                 如果不传则导出所有模块
    """
    try:
        # 解析模块列表
        if modules:
            module_list = [m.strip() for m in modules.split(",")]
            # 验证模块名
            invalid = [m for m in module_list if m not in VALID_MODULES]
            if invalid:
                raise HTTPException(status_code=400, detail=f"Invalid modules: {', '.join(invalid)}")
        else:
            module_list = VALID_MODULES

        # 导出数据（传入 current_user 用于过滤）
        data = export_data(module_list, current_user)

        # 生成文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fundval_export_{timestamp}.json"

        # 转换为 JSON 字符串
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        json_bytes = json_str.encode("utf-8")

        # 返回文件流
        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/import")
def import_data_endpoint(
    request: ImportRequest = Body(...),
    current_user: User = Depends(require_auth)
):
    """
    从 JSON 导入数据（需要认证）

    Body:
        data: 完整的 JSON 数据对象
        modules: 要导入的模块列表
        mode: 导入模式（merge 或 replace）
    """
    try:
        # 验证模式
        if request.mode not in ["merge", "replace"]:
            raise HTTPException(status_code=400, detail="Invalid mode. Must be 'merge' or 'replace'")

        # 验证模块列表
        invalid = [m for m in request.modules if m not in VALID_MODULES]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid modules: {', '.join(invalid)}")

        # 导入数据（传入 current_user 用于设置 user_id）
        result = import_data(request.data, request.modules, request.mode, current_user)

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
