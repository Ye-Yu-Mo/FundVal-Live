"""
更新基金净值命令

从数据源更新基金的最新净值
"""
import logging
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.management.base import BaseCommand
from api.sources import SourceRegistry
from api.models import Fund

logger = logging.getLogger(__name__)


def _fetch_nav_from_source(source, fund_code, use_today, today):
    """从单个数据源获取净值，失败返回 None"""
    try:
        if use_today:
            # 某些数据源可能没有 fetch_today_nav，需要判断
            if hasattr(source, 'fetch_today_nav'):
                data = source.fetch_today_nav(fund_code)
            else:
                data = source.fetch_realtime_nav(fund_code)
            
            if not data or data['nav_date'] != today:
                return None
        else:
            data = source.fetch_realtime_nav(fund_code)
            if not data:
                return None
        return data
    except Exception:
        return None


def _fetch_best_nav(fund_code, use_today, today):
    """
    并发从所有数据源获取净值，返回 nav_date 最新的那条。
    """
    source_names = SourceRegistry.list_sources()
    # 排除 sina 等行情类源，只保留净值类源用于更新
    sources = [SourceRegistry.get_source(n) for n in source_names 
               if SourceRegistry.get_source(n) and n != 'sina']

    results = []
    with ThreadPoolExecutor(max_workers=len(sources) or 1) as executor:
        futures = {executor.submit(_fetch_nav_from_source, s, fund_code, use_today, today): s for s in sources}
        for future in as_completed(futures):
            try:
                data = future.result()
                if data:
                    results.append(data)
            except Exception:
                continue

    if not results:
        return None

    # 取 nav_date 最新的
    return max(results, key=lambda d: d['nav_date'])


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
            self.stdout.write(f'开始更新所有基金的{mode}（多源取最新）...')
            funds = Fund.objects.all()

        today = date.today()
        success_count = 0
        error_count = 0
        skip_count = 0

        for fund in funds:
            try:
                data = _fetch_best_nav(fund.fund_code, use_today, today)

                if not data:
                    skip_count += 1
                    continue

                new_date = data.get('nav_date')
                # 核心保护：只在日期更新或相等时保存，防止旧数据覆盖新数据
                if not fund.latest_nav_date or (new_date and new_date >= fund.latest_nav_date):
                    fund.latest_nav = data['nav']
                    fund.latest_nav_date = new_date
                    fund.save(update_fields=['latest_nav', 'latest_nav_date', 'updated_at'])
                    success_count += 1
                else:
                    skip_count += 1

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
