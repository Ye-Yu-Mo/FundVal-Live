"""
更新基金净值命令

从数据源更新基金的最新净值
"""
import logging
from django.core.management.base import BaseCommand
from api.sources import SourceRegistry
from api.models import Fund

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '更新基金净值'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fund_code',
            type=str,
            help='指定基金代码（可选，不指定则更新所有基金）',
        )

    def handle(self, *args, **options):
        fund_code = options.get('fund_code')

        if fund_code:
            self.stdout.write(f'开始更新基金 {fund_code} 的净值...')
            funds = Fund.objects.filter(fund_code=fund_code)
            if not funds.exists():
                self.stdout.write(self.style.ERROR(f'基金 {fund_code} 不存在'))
                return
        else:
            self.stdout.write('开始更新所有基金的净值...')
            funds = Fund.objects.all()

        source = SourceRegistry.get_source('eastmoney')
        if not source:
            self.stdout.write(self.style.ERROR('数据源 eastmoney 未注册'))
            return

        success_count = 0
        error_count = 0

        for fund in funds:
            try:
                data = source.fetch_realtime_nav(fund.fund_code)
                new_date = data.get('nav_date')
                if not fund.latest_nav_date or (new_date and new_date >= fund.latest_nav_date):
                    fund.latest_nav = data['nav']
                    fund.latest_nav_date = new_date
                    fund.save(update_fields=['latest_nav', 'latest_nav_date', 'updated_at'])
                success_count += 1

                if fund_code:
                    self.stdout.write(
                        f'  {fund.fund_code}: {data["nav"]} ({data["nav_date"]})'
                    )

            except Exception as e:
                error_count += 1
                logger.error(f'更新基金 {fund.fund_code} 净值失败: {e}')
                if fund_code:
                    self.stdout.write(self.style.ERROR(f'  更新失败: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'更新完成：成功 {success_count} 个，失败 {error_count} 个'
        ))
