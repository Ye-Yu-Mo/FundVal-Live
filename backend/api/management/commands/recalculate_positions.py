"""
重算持仓命令

重新计算持仓汇总数据
"""

import logging
from django.core.management.base import BaseCommand
from api.services import recalculate_all_positions

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "重新计算持仓汇总"

    def add_arguments(self, parser):
        parser.add_argument(
            "--account_id",
            type=str,
            help="指定账户 ID（可选，不指定则重算所有账户）",
        )

    def handle(self, *args, **options):
        account_id = options.get("account_id")

        if account_id:
            self.stdout.write(f"开始重算账户 {account_id} 的持仓...")
            recalculate_all_positions(account_id=account_id)
            self.stdout.write(self.style.SUCCESS("重算完成"))
        else:
            self.stdout.write("开始重算所有账户的持仓...")
            recalculate_all_positions()
            self.stdout.write(self.style.SUCCESS("重算完成"))
