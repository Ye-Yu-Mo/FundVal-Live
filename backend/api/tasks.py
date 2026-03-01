"""
Celery 任务

定义所有后台异步任务
"""
from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


@shared_task
def update_fund_nav():
    """
    定时更新基金净值

    每天从数据源获取最新净值并更新数据库
    """
    try:
        call_command('update_nav')
        logger.info('基金净值更新完成')
        return '净值更新完成'
    except Exception as e:
        logger.error(f'基金净值更新失败: {str(e)}')
        raise


@shared_task
def capture_estimate_snapshot():
    """
    捕捉 15:00 收盘估值快照

    每个交易日 15:00 执行，将当前的实时估值存入准确率审计表
    """
    from api.models import Fund, EstimateAccuracy
    from api.utils.trading_calendar import is_trading_day
    from django.utils import timezone
    from decimal import Decimal

    today = timezone.localdate()
    if not is_trading_day(today):
        logger.info(f'{today} 不是交易日，跳过估值捕捉')
        return '非交易日'

    funds = Fund.objects.exclude(estimate_nav__isnull=True)
    count = 0
    for fund in funds:
        # 只捕捉当天的预估
        if fund.estimate_time and fund.estimate_time.date() == today:
            EstimateAccuracy.objects.update_or_create(
                source_name='eastmoney',
                fund=fund,
                estimate_date=today,
                defaults={
                    'estimate_nav': fund.estimate_nav
                }
            )
            count += 1

    logger.info(f'已捕捉 {count} 个基金的收盘估值快照')
    return f'捕捉完成：{count}'


@shared_task
def audit_accuracy():
    """
    审计估值准确率

    每个交易晚间执行，撮合当天的估值快照与最终公布的净值
    """
    from api.utils.trading_calendar import is_trading_day
    from django.utils import timezone

    today = timezone.localdate()
    if not is_trading_day(today):
        logger.info(f'{today} 不是交易日，跳过准确率审计')
        return '非交易日'

    try:
        # 调用 management command 执行审计
        call_command('calculate_accuracy', date=today.isoformat())
        logger.info(f'{today} 准确率审计完成')
        return '审计完成'
    except Exception as e:
        logger.error(f'准确率审计失败: {str(e)}')
        raise
