from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        """应用启动时执行"""
        from fundval.config import config
        from fundval.bootstrap import get_bootstrap_key

        # 如果系统未初始化，输出 bootstrap_key
        if not config.get("system_initialized"):
            key = get_bootstrap_key()
            logger.warning("=" * 80)
            logger.warning("系统未初始化！")
            logger.warning(f"Bootstrap Key: {key}")
            logger.warning("请使用此密钥初始化系统")
            logger.warning("=" * 80)
