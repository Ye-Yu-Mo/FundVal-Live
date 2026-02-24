"""
更新基金净值命令

从数据源更新基金的最新净值
"""
import logging
from datetime import date
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
        parser.add_argument(
            '--today',
            action='store_true',
            help='获取当日确认净值（从历史净值接口），只有当日净值才更新',
        )

    def handle(self, *args, **options):
        fund_code = options.get('fund_code')
        use_today = options.get('today', False)

        if fund_code:
            self.stdout.write(f'开始更新基金 {fund_code} 的净值...')
            funds = Fund.objects.filter(fund_code=fund_code)
            if not funds.exists():
                self.stdout.write(self.style.ERROR(f'基金 {fund_code} 不存在'))
                return
        else:
            mode = '当日净值' if use_today else '昨日净值'
            self.stdout.write(f'开始更新所有基金的{mode}...')
            funds = Fund.objects.all()

        source = SourceRegistry.get_source('eastmoney')
        if not source:
            self.stdout.write(self.style.ERROR('数据源 eastmoney 未注册'))
            return

        success_count = 0
        error_count = 0
        skip_count = 0
        today = date.today()

        for fund in funds:
            try:
                if use_today:
                    # 使用 fetch_today_nav 获取当日净值
                    data = source.fetch_today_nav(fund.fund_code)

                    if not data:
                        skip_count += 1
                        continue

                    # 日期校验：只有当日净值才更新
                    if data['nav_date'] != today:
                        skip_count += 1
                        if fund_code:
                            self.stdout.write(
                                f'  {fund.fund_code}: 跳过（净值日期 {data["nav_date"]} 不是今天）'
                            )
                        continue

                    fund.latest_nav = data['nav']
                    fund.latest_nav_date = data['nav_date']
                else:
                    # 使用 fetch_realtime_nav 获取昨日净值
                    data = source.fetch_realtime_nav(fund.fund_code)

                    if not data:
                        skip_count += 1
                        continue

                    fund.latest_nav = data['nav']
                    fund.latest_nav_date = data['nav_date']

                fund.save()
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
            f'更新完成：成功 {success_count} 个，跳过 {skip_count} 个，失败 {error_count} 个'
        ))
