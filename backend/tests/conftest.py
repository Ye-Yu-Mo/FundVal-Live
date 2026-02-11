import pytest
import os
import django
from django.conf import settings

# 配置 Django 设置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fundval.settings')

def pytest_configure(config):
    """配置 pytest-django"""
    if not settings.configured:
        django.setup()


@pytest.fixture
def create_child_account():
    """
    创建子账户的辅助 fixture

    用法：
        child_account = create_child_account(user, '子账户名')
    """
    def _create_child_account(user, name='测试子账户'):
        from api.models import Account
        # 创建父账户
        parent = Account.objects.create(user=user, name=f'{name}-父账户')
        # 创建子账户
        return Account.objects.create(user=user, name=name, parent=parent)

    return _create_child_account
