"""
认证相关 API 端点
"""
from fastapi import APIRouter, HTTPException, status, Response, Request, Depends
from pydantic import BaseModel
from typing import Optional
from ..auth import (
    hash_password,
    verify_password,
    create_session,
    delete_session,
    get_current_user,
    require_auth,
    require_admin,
    has_admin_user,
    User,
    SESSION_COOKIE_NAME,
    SESSION_EXPIRY_DAYS
)
from ..db import get_db_connection, check_database_version, CURRENT_SCHEMA_VERSION


router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================================
# Helper Functions
# ============================================================================

def get_user_default_account_id(user_id: int) -> Optional[int]:
    """
    获取用户的默认账户 ID

    优先级：
    1. user_settings 中的 default_account_id
    2. 用户的第一个账户
    3. None（如果用户没有账户）
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. 尝试从 settings 获取
    cursor.execute(
        "SELECT value FROM settings WHERE user_id = ? AND key = 'default_account_id'",
        (user_id,)
    )
    row = cursor.fetchone()
    if row:
        try:
            return int(row[0])
        except (ValueError, TypeError):
            pass

    # 2. 获取用户的第一个账户
    cursor.execute(
        "SELECT id FROM accounts WHERE user_id = ? ORDER BY id LIMIT 1",
        (user_id,)
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # 3. 没有账户
    return None

# ============================================================================
# Request/Response Models
# ============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    default_account_id: Optional[int] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class InitAdminRequest(BaseModel):
    username: str
    password: str


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/init-status")
def init_status():
    """
    获取系统初始化状态（无需认证）

    Returns:
        dict: {
            "needs_init": bool,  # 是否需要初始化（没有管理员用户）
            "needs_rebuild": bool  # 是否需要重建数据库（版本不匹配）
        }
    """
    needs_init = not has_admin_user()

    # 检查数据库版本
    current_version = check_database_version()
    needs_rebuild = current_version != CURRENT_SCHEMA_VERSION

    return {
        "needs_init": needs_init,
        "needs_rebuild": needs_rebuild
    }


@router.post("/init-admin")
def init_admin(request: InitAdminRequest):
    """
    创建初始管理员用户（无需认证，只能在未初始化时调用）

    Args:
        request: 初始管理员信息（username, password）

    Returns:
        dict: 成功消息和管理员信息

    Raises:
        HTTPException: 400 已存在管理员用户
    """
    # 检查是否已经有管理员
    if has_admin_user():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系统已初始化，无法创建初始管理员"
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 创建管理员用户
        password_hash = hash_password(request.password)
        cursor.execute("""
            INSERT INTO users (username, password_hash, is_admin)
            VALUES (?, ?, 1)
        """, (request.username, password_hash))
        admin_id = cursor.lastrowid

        # 为管理员创建默认账户
        cursor.execute("""
            INSERT INTO accounts (name, description, user_id)
            VALUES (?, ?, ?)
        """, ("默认账户", "管理员默认账户", admin_id))
        account_id = cursor.lastrowid

        conn.commit()

        return {
            "message": "初始管理员创建成功",
            "admin_id": admin_id,
            "username": request.username,
            "default_account_id": account_id
        }
    except Exception as e:
        conn.rollback()
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建管理员失败: {str(e)}"
        )


@router.get("/registration-enabled")
def get_registration_enabled():
    """
    获取注册是否开启（不需要认证，公开接口）

    Returns:
        dict: { registration_enabled: bool }
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT value FROM settings WHERE key = 'allow_registration' AND user_id IS NULL"
    )
    row = cursor.fetchone()
    enabled = row and row[0] == '1'

    return {
        "registration_enabled": enabled
    }


@router.post("/login", response_model=UserResponse)
def login(request: LoginRequest, response: Response):
    """
    登录

    Args:
        request: 登录请求（username, password）
        response: FastAPI Response 对象

    Returns:
        UserResponse: 用户信息

    Raises:
        HTTPException: 400 单用户模式不支持登录，401 用户名或密码错误
    """
    # 查询用户
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, password_hash, is_admin FROM users WHERE username = ?",
        (request.username,)
    )
    row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    user_id = row[0]
    username = row[1]
    password_hash = row[2]
    is_admin = row[3]

    # 验证密码
    if not verify_password(request.password, password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # 创建 session
    session_id = create_session(user_id)

    # 设置 cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_EXPIRY_DAYS * 24 * 60 * 60,  # 秒
        httponly=True,
        samesite="lax"
    )

    # 获取默认账户 ID
    default_account_id = get_user_default_account_id(user_id)

    return UserResponse(
        id=user_id,
        username=username,
        is_admin=bool(is_admin),
        default_account_id=default_account_id
    )

@router.post("/logout")
def logout(request: Request, response: Response, user: User = Depends(require_auth)):
    """
    登出

    Args:
        request: FastAPI Request 对象
        response: FastAPI Response 对象
        user: 当前用户（通过 require_auth 获取）

    Returns:
        dict: 成功消息
    """
    # 删除服务端 session
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        delete_session(session_id)

    # 清除客户端 cookie
    response.delete_cookie(key=SESSION_COOKIE_NAME)

    return {"message": "登出成功"}


@router.post("/register", response_model=UserResponse)
def register(request: LoginRequest, response: Response):
    """
    用户注册（需要开启注册功能）

    Args:
        request: 注册请求（username, password）
        response: FastAPI Response 对象

    Returns:
        UserResponse: 新用户信息

    Raises:
        HTTPException: 403 注册功能未开启
        HTTPException: 400 用户名已存在
        HTTPException: 400 密码长度不足
    """
    # 检查是否允许注册
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'allow_registration' AND user_id IS NULL")
    row = cursor.fetchone()
    allow_registration = row and row[0] == '1'

    if not allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="注册功能未开启，请联系管理员"
        )

    # 验证密码长度
    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码长度至少为 6 位"
        )

    # 检查用户名是否已存在
    cursor.execute(
        "SELECT id FROM users WHERE username = ?",
        (request.username,)
    )
    if cursor.fetchone() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    # 创建用户（普通用户，非管理员）
    password_hash = hash_password(request.password)
    cursor.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 0)",
        (request.username, password_hash)
    )
    user_id = cursor.lastrowid

    # 为新用户创建默认账户
    cursor.execute(
        "INSERT INTO accounts (name, description, user_id) VALUES (?, ?, ?)",
        ("默认账户", "系统自动创建的默认账户", user_id)
    )
    account_id = cursor.lastrowid

    # 设置默认账户 ID
    cursor.execute(
        "INSERT INTO settings (key, value, user_id) VALUES (?, ?, ?)",
        ("default_account_id", str(account_id), user_id)
    )

    conn.commit()

    # 自动登录：创建 session
    session_id = create_session(user_id)

    # 设置 cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_EXPIRY_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax"
    )

    return UserResponse(
        id=user_id,
        username=request.username,
        is_admin=False,
        default_account_id=account_id
    )



@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(require_auth)):
    """
    获取当前用户信息

    Args:
        user: 当前用户（通过 require_auth 获取）

    Returns:
        UserResponse: 用户信息（包含默认账户 ID）
    """
    default_account_id = get_user_default_account_id(user.id)

    return UserResponse(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        default_account_id=default_account_id
    )


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    user: User = Depends(require_auth)
):
    """
    修改密码

    Args:
        request: 修改密码请求（old_password, new_password）
        user: 当前用户（通过 require_auth 获取）

    Returns:
        dict: 成功消息

    Raises:
        HTTPException: 400 旧密码错误
    """
    # 查询用户密码哈希
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT password_hash FROM users WHERE id = ?",
        (user.id,)
    )
    row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    password_hash = row[0]

    # 验证旧密码
    if not verify_password(request.old_password, password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )

    # 更新密码
    new_password_hash = hash_password(request.new_password)
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_password_hash, user.id)
    )
    conn.commit()

    return {"message": "密码修改成功"}

# ============================================================================
# Admin API Endpoints
# ============================================================================

class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


@router.post("/admin/users", response_model=UserResponse)
def create_user(request: CreateUserRequest, admin: User = Depends(require_admin)):
    """
    创建用户（需要管理员权限）

    Args:
        request: 创建用户请求（username, password, is_admin）
        admin: 当前管理员（通过 require_admin 获取）

    Returns:
        UserResponse: 新用户信息

    Raises:
        HTTPException: 400 用户名已存在
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查用户名是否已存在
    cursor.execute(
        "SELECT id FROM users WHERE username = ?",
        (request.username,)
    )
    if cursor.fetchone() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    # 创建用户
    password_hash = hash_password(request.password)
    cursor.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
        (request.username, password_hash, int(request.is_admin))
    )
    user_id = cursor.lastrowid

    # 为新用户创建默认账户
    cursor.execute(
        "INSERT INTO accounts (name, description, user_id) VALUES (?, ?, ?)",
        ("默认账户", "系统自动创建的默认账户", user_id)
    )
    account_id = cursor.lastrowid

    # 设置默认账户 ID
    cursor.execute(
        "INSERT INTO settings (key, value, user_id) VALUES (?, ?, ?)",
        ("default_account_id", str(account_id), user_id)
    )

    conn.commit()

    return UserResponse(
        id=user_id,
        username=request.username,
        is_admin=request.is_admin,
        default_account_id=account_id
    )


@router.get("/admin/users", response_model=list[UserResponse])
def list_users(admin: User = Depends(require_admin)):
    """
    列出所有用户（需要管理员权限）

    Args:
        admin: 当前管理员（通过 require_admin 获取）

    Returns:
        list[UserResponse]: 用户列表（包含默认账户 ID）
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, is_admin, created_at FROM users ORDER BY id"
    )
    rows = cursor.fetchall()

    return [
        UserResponse(
            id=row[0],
            username=row[1],
            is_admin=bool(row[2]),
            default_account_id=get_user_default_account_id(row[0])
        )
        for row in rows
    ]

@router.delete("/admin/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin)):
    """
    删除用户（需要管理员权限）

    Args:
        user_id: 要删除的用户 ID
        admin: 当前管理员（通过 require_admin 获取）

    Returns:
        dict: 成功消息

    Raises:
        HTTPException: 400 不允许删除自己或最后一个管理员，404 用户不存在
    """
    # 不允许删除自己
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不允许删除自己"
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查用户是否存在
    cursor.execute(
        "SELECT is_admin FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    is_admin = bool(row[0])

    # 如果要删除的是管理员，检查是否是最后一个管理员
    if is_admin:
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        admin_count = cursor.fetchone()[0]
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不允许删除最后一个管理员"
            )

    # 级联删除用户的所有数据
    # 1. 删除持仓（通过 account_id）
    cursor.execute("""
        DELETE FROM positions
        WHERE account_id IN (SELECT id FROM accounts WHERE user_id = ?)
    """, (user_id,))

    # 2. 删除交易记录（通过 account_id）
    cursor.execute("""
        DELETE FROM transactions
        WHERE account_id IN (SELECT id FROM accounts WHERE user_id = ?)
    """, (user_id,))

    # 3. 删除用户的账户
    cursor.execute("DELETE FROM accounts WHERE user_id = ?", (user_id,))

    # 4. 删除用户的配置
    cursor.execute("DELETE FROM settings WHERE user_id = ?", (user_id,))

    # 5. 删除用户的订阅
    cursor.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))

    # 6. 删除用户的 AI prompts
    cursor.execute("DELETE FROM ai_prompts WHERE user_id = ?", (user_id,))

    # 7. 删除用户
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

    conn.commit()

    return {"message": "用户已删除"}

