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

    每天 18:30 执行，从数据源获取昨日净值并更新数据库
    """
    try:
        call_command('update_nav')
        logger.info('基金净值更新完成')
        return '净值更新完成'
    except Exception as e:
        logger.error(f'基金净值更新失败: {str(e)}')
        raise


@shared_task
def update_fund_today_nav():
    """
    定时更新基金当日确认净值

    每天 21:30 和 23:00 执行，从历史净值接口获取当日净值并更新数据库
    只有当日净值才会更新，非当日净值会跳过
    """
    try:
        call_command('update_nav', '--today')
        logger.info('基金当日净值更新完成')
        return '当日净值更新完成'
    except Exception as e:
        logger.error(f'基金当日净值更新失败: {str(e)}')
        raise
