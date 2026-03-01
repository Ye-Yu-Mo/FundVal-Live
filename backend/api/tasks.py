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
    定时更新基金净值（昨日净值）
    
    默认从数据源获取最新可用的历史净值并同步到基金主表。
    """
    try:
        call_command('update_nav')
        logger.info('基金昨日/最新净值同步完成')
        return '净值同步完成'
    except Exception as e:
        logger.error(f'基金净值自动更新失败: {str(e)}')
        raise


@shared_task
def update_fund_today_nav():
    """
    定时更新基金当日确认净值
    
    每天晚间执行，尝试从确权接口抓取今日净值。
    """
    try:
        call_command('update_nav', '--today')
        logger.info('基金今日净值确权完成')
        return '当日净值更新完成'
    except Exception as e:
        logger.error(f'基金当日净值确权失败: {str(e)}')
        raise


@shared_task
def capture_estimate_snapshot():
    """
    捕捉 15:00 收盘估值快照
    
    每个交易日 15:05 执行，将收盘估值锁定，用于晚间与真实净值对比计算误差。
    """
    from api.models import Fund, EstimateAccuracy
    from api.utils.trading_calendar import is_trading_day
    from django.utils import timezone

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
    
    每个交易晚间执行，计算所有捕捉到的快照与最终净值的误差。
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
