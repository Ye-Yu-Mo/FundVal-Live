"""
计算估值准确率命令

计算估值数据的准确率
"""

import logging
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from api.sources import SourceRegistry
from api.models import EstimateAccuracy

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "计算估值准确率"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="指定日期（格式：YYYY-MM-DD，默认为昨天）",
        )

    def handle(self, *args, **options):
        date_str = options.get("date")

        if date_str:
            target_date = date.fromisoformat(date_str)
            self.stdout.write(f"开始计算 {target_date} 的准确率...")
        else:
            target_date = date.today() - timedelta(days=1)
            self.stdout.write(f"开始计算昨天（{target_date}）的准确率...")

        # 获取指定日期的未计算准确率的记录
        records = EstimateAccuracy.objects.filter(
            estimate_date=target_date, actual_nav__isnull=True
        )

        if not records.exists():
            self.stdout.write(self.style.WARNING("没有需要计算的记录"))
            return

        self.stdout.write(f"找到 {records.count()} 条记录")

        # 并发从所有数据源获取实际净值
        from api.models import UserSourceCredential

        from api.models import UserSourceCredential

        source_names = SourceRegistry.list_sources()
        sources = []
        for name in source_names:
            s = SourceRegistry.get_source(name)
            if not s or name == "sina":
                continue
            if name == "yangjibao":
                continue  # 需要持仓上下文
            if name == "xiaobeiyangji":
                cred = UserSourceCredential.objects.filter(
                    source_name=name, is_active=True
                ).first()
                if not cred:
                    continue
                s.set_token(cred.token)
            sources.append(s)
        if not sources:
            self.stdout.write(self.style.ERROR("没有可用的数据源"))
            return

        success_count = 0
        error_count = 0

        for record in records:
            try:
                # 多源尝试获取实际净值（不强制日期精确匹配，QDII T+2 延迟场景）
                data = None
                for s in sources:
                    try:
                        d = s.fetch_realtime_nav(record.fund.fund_code)
                        if d and d.get("nav_date"):
                            # 优先精确匹配，否则取最新的
                            if not data or d["nav_date"] == record.estimate_date:
                                data = d
                            elif d["nav_date"] > data["nav_date"]:
                                data = d
                    except Exception:
                        continue
                if not data:
                    continue

                record.actual_nav = data["nav"]

                # 计算误差率
                record.calculate_error_rate()

                success_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"计算准确率失败 {record.fund.fund_code}: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"计算完成：成功 {success_count} 个，失败 {error_count} 个"
            )
        )
