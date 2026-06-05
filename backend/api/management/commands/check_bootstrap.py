from django.core.management.base import BaseCommand
from fundval.config import config
from fundval.bootstrap import get_bootstrap_key


class Command(BaseCommand):
    help = "检查系统初始化状态并输出 bootstrap key"

    def handle(self, *args, **options):
        system_initialized = config.get("system_initialized", False)

        if system_initialized:
            self.stdout.write(self.style.SUCCESS("✓ System already initialized"))
        else:
            bootstrap_key = get_bootstrap_key()
            self.stdout.write(self.style.WARNING("⚠ System NOT initialized"))
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(self.style.SUCCESS(f"  BOOTSTRAP KEY: {bootstrap_key}"))
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write("")
            self.stdout.write(
                "Copy this key and use it to initialize the system via web UI"
            )
