#!/usr/bin/env python3
"""
FundVal Live Backend Entry Point
用于 PyInstaller 打包
"""
import sys
import os

# 添加 backend 目录到 Python 路径
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 使用绝对导入
import uvicorn
from app.main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "21345"))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
