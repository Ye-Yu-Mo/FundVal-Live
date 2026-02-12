"""
基金历史净值同步服务
"""
from datetime import date, timedelta
from typing import List, Optional
from django.db import transaction
import logging

from ..models import Fund, FundNavHistory
from ..sources import SourceRegistry

logger = logging.getLogger(__name__)


def sync_nav_history(
    fund_code: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    force: bool = False
) -> int:
    """
    同步基金历史净值

    Args:
        fund_code: 基金代码
        start_date: 开始日期（可选，默认从最后一条记录开始）
        end_date: 结束日期（可选，默认今天）
        force: 是否强制全量同步

    Returns:
        新增/更新的记录数
    """
    try:
        fund = Fund.objects.get(fund_code=fund_code)
    except Fund.DoesNotExist:
        raise ValueError(f'基金不存在：{fund_code}')

    # 如果不是强制同步，从最后一条记录开始
    if not force and not start_date:
        last_record = FundNavHistory.objects.filter(fund=fund).first()
        if last_record:
            start_date = last_record.nav_date + timedelta(days=1)

    if not end_date:
        end_date = date.today()

    # 从数据源获取数据
    source = SourceRegistry.get_source('eastmoney')
    nav_data = source.fetch_nav_history(fund_code, start_date, end_date)

    if not nav_data:
        logger.info(f'没有新的历史净值数据：{fund_code}')
        return 0

    # 批量导入
    count = 0
    with transaction.atomic():
        for item in nav_data:
            _, created = FundNavHistory.objects.update_or_create(
                fund=fund,
                nav_date=item['nav_date'],
                defaults={
                    'unit_nav': item['unit_nav'],
                    'accumulated_nav': item.get('accumulated_nav'),
                    'daily_growth': item.get('daily_growth'),
                }
            )
            if created:
                count += 1

    logger.info(f'同步历史净值完成：{fund_code}，新增 {count} 条记录')
    return count


def batch_sync_nav_history(
    fund_codes: List[str],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> dict:
    """
    批量同步历史净值

    Args:
        fund_codes: 基金代码列表
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）

    Returns:
        {fund_code: {'success': bool, 'count': int, 'error': str}} 字典
    """
    results = {}
    for fund_code in fund_codes:
        try:
            count = sync_nav_history(fund_code, start_date, end_date)
            results[fund_code] = {'success': True, 'count': count}
        except Exception as e:
            logger.error(f'同步历史净值失败：{fund_code}, 错误：{e}')
            results[fund_code] = {'success': False, 'error': str(e)}

    return results
