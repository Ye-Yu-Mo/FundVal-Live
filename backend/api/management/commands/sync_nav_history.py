"""
同步基金历史净值管理命令
"""

from django.core.management.base import BaseCommand
from datetime import datetime

from api.services.nav_history import sync_nav_history, batch_sync_nav_history
from api.models import Fund


class Command(BaseCommand):
    help = "同步基金历史净值"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fund-code", type=str, help="基金代码（可选，不指定则同步所有基金）"
        )
        parser.add_argument(
            "--start-date", type=str, help="开始日期（格式：YYYY-MM-DD）"
        )
        parser.add_argument("--end-date", type=str, help="结束日期（格式：YYYY-MM-DD）")
        parser.add_argument("--force", action="store_true", help="强制全量同步")

    def handle(self, *args, **options):
        fund_code = options.get("fund_code")
        start_date = options.get("start_date")
        end_date = options.get("end_date")
        force = options.get("force", False)

        # 转换日期
        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        if fund_code:
            # 同步单个基金
            self.stdout.write(f"开始同步基金 {fund_code}...")
            count = sync_nav_history(fund_code, start_date, end_date, force)
            self.stdout.write(self.style.SUCCESS(f"同步完成，新增/更新 {count} 条记录"))
        else:
            # 同步所有基金
            fund_codes = Fund.objects.values_list("fund_code", flat=True)
            self.stdout.write(f"开始同步 {len(fund_codes)} 个基金...")
            results = batch_sync_nav_history(list(fund_codes), start_date, end_date)

            success_count = sum(1 for r in results.values() if r["success"])
            total_records = sum(
                r.get("count", 0) for r in results.values() if r["success"]
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"同步完成：成功 {success_count}/{len(fund_codes)} 个基金，"
                    f"新增/更新 {total_records} 条记录"
                )
            )
