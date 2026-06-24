"""
Celery 配置

定时任务系统，用于自动更新基金净值等后台任务。
任务调度统一在 settings.py 的 CELERY_BEAT_SCHEDULE 中配置。
"""

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fundval.settings")

app = Celery("fundval")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """调试任务"""
    print(f"Request: {self.request!r}")
