"""
更新基金净值命令

使用东方财富移动端批量 API (FundMNFInfo) 一次性获取数百只基金的净值。
"""

import logging
import requests
from datetime import date
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from api.models import Fund

logger = logging.getLogger(__name__)

BATCH_API_URL = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo"
BATCH_SIZE = 200
MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_3 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
        "eastmoney/6.2.8"
    ),
}


def _fetch_batch_nav(fund_codes):
    """
    批量获取基金净值。

    返回: {fund_code: {'nav': Decimal, 'nav_date': date}}
    """
    result = {}
    url = BATCH_API_URL
    params = {
        "Fcodes": ",".join(fund_codes),
        "pageIndex": "1",
        "pageSize": str(len(fund_codes) + 10),
        "Sort": "",
        "SortColumn": "",
        "IsShowSE": "false",
        "P": "F",
        "deviceid": "3EA024C2-7F22-408B-95E4-383D38160FB3",
        "plat": "Iphone",
        "product": "EFund",
        "version": "6.2.8",
    }
    try:
        resp = requests.get(url, params=params, headers=MOBILE_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data or not data.get("Datas"):
            return result

        for item in data["Datas"]:
            code = item.get("FCODE")
            nav_str = item.get("ACCNAV")
            date_str = item.get("PDATE")
            if not code or not nav_str or not date_str:
                continue
            try:
                nav_date = date.fromisoformat(date_str)
                nav = Decimal(str(nav_str))
                result[code] = {"nav": nav, "nav_date": nav_date}
            except (InvalidOperation, ValueError, TypeError):
                continue
    except Exception as e:
        logger.warning(f"批量获取净值失败: {e}")

    return result


class Command(BaseCommand):
    help = "更新基金净值（批量模式，200只/请求）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fund_code", type=str, help="指定基金代码（可选）"
        )
        parser.add_argument(
            "--today",
            action="store_true",
            help="仅更新当日确认净值（nav_date == today）",
        )

    def handle(self, *args, **options):
        fund_code = options.get("fund_code")
        use_today = options.get("today", False)
        today = date.today()

        if fund_code:
            funds = list(Fund.objects.filter(fund_code=fund_code))
            if not funds:
                self.stdout.write(self.style.ERROR(f"基金 {fund_code} 不存在"))
                return
        else:
            funds = list(Fund.objects.all())
            count = len(funds)
            mode = "当日净值" if use_today else "最新净值"
            self.stdout.write(f"开始更新 {count} 个基金的{mode}（{BATCH_SIZE}只/批）...")

        if not funds:
            self.stdout.write(self.style.WARNING("没有基金"))
            return

        # --- 批量模式 ---
        if not fund_code:
            codes = [f.fund_code for f in funds]
            code_map = {f.fund_code: f for f in funds}

            success_count = 0
            skip_count = 0

            for i in range(0, len(codes), BATCH_SIZE):
                batch = codes[i : i + BATCH_SIZE]
                nav_data = _fetch_batch_nav(batch)

                for code, nav_info in nav_data.items():
                    fund = code_map.get(code)
                    if not fund:
                        continue

                    new_date = nav_info["nav_date"]

                    if use_today and new_date != today:
                        continue

                    if fund.latest_nav_date and new_date < fund.latest_nav_date:
                        skip_count += 1
                        continue

                    fund.latest_nav = nav_info["nav"]
                    fund.latest_nav_date = new_date
                    fund.save(
                        update_fields=["latest_nav", "latest_nav_date", "updated_at"]
                    )
                    success_count += 1

                skip_count += len(batch) - len(nav_data)
                self.stdout.write(
                    f"  批次 {i // BATCH_SIZE + 1}: "
                    f"获取 {len(nav_data)}/{len(batch)} 净值"
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"更新完成：成功 {success_count} 个，跳过/无数据 {skip_count} 个"
                )
            )
            return

        # --- 单基金模式（保留多源 fallback） ---
        from api.sources import SourceRegistry

        source_names = SourceRegistry.list_sources()
        sources = [
            SourceRegistry.get_source(n)
            for n in source_names
            if SourceRegistry.get_source(n) and n != "sina"
        ]

        fund = funds[0]
        data = None
        for s in sources:
            try:
                if use_today:
                    d = s.fetch_today_nav(fund_code)
                else:
                    d = s.fetch_realtime_nav(fund_code)
                if d and (not data or d["nav_date"] > data["nav_date"]):
                    data = d
            except Exception:
                continue

        if not data:
            self.stdout.write(self.style.WARNING(f"未获取到基金 {fund_code} 的净值"))
            return

        new_date = data["nav_date"]
        if fund.latest_nav_date and new_date < fund.latest_nav_date:
            self.stdout.write(f"日期未更新（{new_date} <= {fund.latest_nav_date}），跳过")
            return

        fund.latest_nav = data["nav"]
        fund.latest_nav_date = new_date
        fund.save(update_fields=["latest_nav", "latest_nav_date", "updated_at"])
        self.stdout.write(
            self.style.SUCCESS(
                f'{fund_code}: {data["nav"]} ({data["nav_date"]})'
            )
        )
