"""
系统管理相关 API 端点
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from ..db import (
    check_database_version,
    drop_all_tables,
    init_db,
    CURRENT_SCHEMA_VERSION
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


# ============================================================================
# Response Models
# ============================================================================

class DBStatusResponse(BaseModel):
    """数据库状态响应"""
    version: int
    current_version: int
    needs_rebuild: bool
    table_count: int


class RebuildResponse(BaseModel):
    """重建响应"""
    message: str
    version: int


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/db-status", response_model=DBStatusResponse)
def get_db_status():
    """
    获取数据库状态

    Returns:
        DBStatusResponse: 数据库状态信息

    Note:
        此端点无需认证，因为在数据库需要重建时可能还没有用户
    """
    try:
        from ..db import get_all_tables

        version = check_database_version()
        needs_rebuild = version > 0 and version != CURRENT_SCHEMA_VERSION
        table_count = len(get_all_tables())

        return DBStatusResponse(
            version=version,
            current_version=CURRENT_SCHEMA_VERSION,
            needs_rebuild=needs_rebuild,
            table_count=table_count
        )
    except Exception as e:
        logger.error(f"Error checking database status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check database status: {str(e)}"
        )


@router.post("/rebuild-db", response_model=RebuildResponse)
def rebuild_database():
    """
    重建数据库（删除所有表并重新初始化）

    Returns:
        RebuildResponse: 重建结果

    Raises:
        HTTPException: 400 如果数据库不需要重建
        HTTPException: 500 如果重建失败

    Warning:
        此操作会删除所有数据！请确保已备份重要数据。

    Note:
        此端点无需认证，因为在数据库需要重建时可能还没有用户
    """
    try:
        version = check_database_version()

        # 检查是否需要重建
        if version == CURRENT_SCHEMA_VERSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database is already at current version, no rebuild needed"
            )

        logger.warning(f"Rebuilding database (current version: {version}, target version: {CURRENT_SCHEMA_VERSION})")

        # 删除所有表
        drop_all_tables()

        # 重新初始化
        init_db()

        # 验证重建成功
        new_version = check_database_version()
        if new_version != CURRENT_SCHEMA_VERSION:
            raise Exception(f"Rebuild failed: version is {new_version}, expected {CURRENT_SCHEMA_VERSION}")

        logger.info(f"Database rebuilt successfully to version {new_version}")

        return RebuildResponse(
            message="Database rebuilt successfully",
            version=new_version
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rebuilding database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rebuild database: {str(e)}"
        )
