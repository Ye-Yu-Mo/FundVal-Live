from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from contextlib import asynccontextmanager
import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler

from .routers import funds, ai, account, settings, data
from .db import init_db
from .services.scheduler import start_scheduler

# Request size limit (10MB)
MAX_REQUEST_SIZE = 10 * 1024 * 1024

# 配置日志系统
def setup_logging():
    """配置日志：控制台 INFO，文件 WARNING+"""
    # 获取根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 根 logger 接收所有级别

    # 清除已有的 handlers（避免重复）
    root_logger.handlers.clear()

    # 控制台 handler：INFO 及以上
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 文件 handler：WARNING 及以上
    # 日志文件路径：与数据库同目录
    if getattr(sys, 'frozen', False):
        # 打包后：用户目录
        log_dir = os.path.expanduser("~/.fundval-live")
    else:
        # 开发模式：项目根目录
        log_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "fundval.log")

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.WARNING)  # 只记录 WARNING 及以上
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    logging.info(f"日志系统已初始化，文件路径: {log_file}")

# 初始化日志
setup_logging()


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size"""
    async def dispatch(self, request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body too large. Maximum size is {MAX_REQUEST_SIZE / 1024 / 1024}MB"}
            )
        return await call_next(request)

# 读取版本号
def get_version():
    """从 package.json 读取版本号"""
    try:
        if getattr(sys, 'frozen', False):
            # 打包后的应用
            base_path = sys._MEIPASS
        else:
            # 开发模式
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        package_json_path = os.path.join(base_path, "package.json")
        if os.path.exists(package_json_path):
            with open(package_json_path, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
                return package_data.get('version', '1.0.0')
    except Exception as e:
        print(f"Failed to read version from package.json: {e}")
    return '1.0.0'

APP_VERSION = get_version()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    start_scheduler()
    yield
    # Shutdown
    pass

app = FastAPI(title="Fund Intraday Valuation API", lifespan=lifespan)

# Request size limit middleware
app.add_middleware(RequestSizeLimitMiddleware)

# CORS: allow all for MVP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(funds.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(account.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(data.router, prefix="/api")

# Project info endpoint
@app.get("/api/info")
async def get_project_info():
    """返回项目信息"""
    return {
        "name": "FundVal Live",
        "version": APP_VERSION,
        "description": "盘中基金实时估值与逻辑审计系统",
        "github": "https://github.com/Ye-Yu-Mo/FundVal-Live",
        "issues": "https://github.com/Ye-Yu-Mo/FundVal-Live/issues",
        "releases": "https://github.com/Ye-Yu-Mo/FundVal-Live/releases"
    }

# 静态文件服务（前端）
# 判断是否为打包后的应用
if getattr(sys, 'frozen', False):
    # 打包后：fundval-live 在 _internal 目录下
    base_path = sys._MEIPASS
    frontend_dir = os.path.join(base_path, "fundval-live")
else:
    # 开发模式：frontend/dist
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend", "dist")

print(f"Frontend directory: {frontend_dir}")
print(f"Frontend exists: {os.path.exists(frontend_dir)}")

if os.path.exists(frontend_dir):
    # 挂载 assets 目录
    assets_dir = os.path.join(frontend_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    async def serve_frontend():
        index_path = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "Frontend not found"}

    @app.get("/{full_path:path}")
    async def serve_frontend_routes(full_path: str):
        # 如果是 API 路由，跳过
        if full_path.startswith("api/"):
            return {"error": "Not found"}

        # 尝试返回文件
        file_path = os.path.join(frontend_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # 否则返回 index.html（SPA 路由）
        index_path = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "Frontend not found"}
else:
    print(f"Warning: Frontend directory not found at {frontend_dir}")
