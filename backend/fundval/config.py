import json
import os
from pathlib import Path


class Config:
    """系统配置管理：JSON + 环境变量覆盖"""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._load_config()

    def _load_config(self):
        """加载配置：先读 JSON，再用环境变量覆盖"""
        base_dir = Path(__file__).resolve().parent.parent

        # 优先使用 /app/config/config.json（Docker volume）
        config_path = Path("/app/config/config.json")
        if not config_path.exists():
            # 回退到本地路径
            config_path = base_dir / "config.json"

        # 默认配置
        self._config = {
            "port": 8000,
            "db_type": "sqlite",
            "db_config": {},
            "allow_register": False,
            "system_initialized": False,
            "debug": False,
            "estimate_cache_ttl": 5,  # 估值缓存 TTL（分钟）
        }

        # 读取 JSON 配置
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                self._config.update(file_config)

        # 环境变量覆盖
        if os.getenv("PORT"):
            self._config["port"] = int(os.getenv("PORT"))
        if os.getenv("DB_TYPE"):
            self._config["db_type"] = os.getenv("DB_TYPE")
        if os.getenv("ALLOW_REGISTER"):
            self._config["allow_register"] = (
                os.getenv("ALLOW_REGISTER").lower() == "true"
            )
        if os.getenv("DEBUG"):
            self._config["debug"] = os.getenv("DEBUG").lower() == "true"

        # 保存配置路径供 save() 使用
        self._config_path = config_path

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        """运行时修改配置"""
        self._config[key] = value

    def save(self):
        """保存配置到 JSON 文件"""
        # 优先保存到 volume 路径
        config_path = Path("/app/config/config.json")

        # 如果 volume 目录不存在，回退到代码目录
        if not config_path.parent.exists():
            config_path = getattr(self, "_config_path", None)
            if config_path is None:
                base_dir = Path(__file__).resolve().parent.parent
                config_path = base_dir / "config.json"

        # 确保目录存在
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)


config = Config()
