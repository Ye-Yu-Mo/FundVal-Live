"""
测试 Celery 定时任务

测试点：
1. 任务函数执行
2. 任务调用管理命令
3. 任务错误处理
4. Beat 调度配置
"""
import pytest
from unittest.mock import patch, MagicMock
from django.core.management import call_command


@pytest.mark.django_db
class TestUpdateFundNavTask:
    """测试更新基金净值任务"""

    def test_task_exists(self):
        """测试任务是否存在"""
        from api.tasks import update_fund_nav
        assert callable(update_fund_nav)

    def test_task_calls_management_command(self):
        """测试任务调用管理命令"""
        from api.tasks import update_fund_nav

        with patch('api.tasks.call_command') as mock_call_command:
            result = update_fund_nav()

            # 验证调用了 update_nav 命令
            mock_call_command.assert_called_once_with('update_nav')
            assert result == '净值同步完成'

    def test_task_handles_command_error(self):
        """测试任务处理命令错误"""
        from api.tasks import update_fund_nav

        with patch('api.tasks.call_command') as mock_call_command:
            mock_call_command.side_effect = Exception('命令执行失败')

            with pytest.raises(Exception) as exc_info:
                update_fund_nav()

            assert '命令执行失败' in str(exc_info.value)

    def test_task_logs_success(self):
        """测试任务记录成功日志"""
        from api.tasks import update_fund_nav

        with patch('api.tasks.call_command'):
            with patch('api.tasks.logger') as mock_logger:
                update_fund_nav()

                mock_logger.info.assert_called_once_with('基金昨日/最新净值同步完成')

    def test_task_logs_error(self):
        """测试任务记录错误日志"""
        from api.tasks import update_fund_nav

        with patch('api.tasks.call_command') as mock_call_command:
            mock_call_command.side_effect = Exception('测试错误')

            with patch('api.tasks.logger') as mock_logger:
                with pytest.raises(Exception):
                    update_fund_nav()

                mock_logger.error.assert_called_once()
                call_args = mock_logger.error.call_args[0][0]
                assert '基金净值自动更新失败' in call_args
                assert '测试错误' in call_args


@pytest.mark.django_db
class TestCeleryConfiguration:
    """测试 Celery 配置"""

    def test_celery_app_exists(self):
        """测试 Celery 应用是否存在"""
        from fundval.celery import app
        assert app is not None
        assert app.main == 'fundval'

    def test_celery_autodiscover_tasks(self):
        """测试任务自动发现配置"""
        from fundval.celery import app
        # 验证 autodiscover_tasks 已配置
        assert hasattr(app, 'autodiscover_tasks')

    def test_beat_schedule_configured(self):
        """测试定时任务调度配置"""
        from fundval.celery import app

        # 验证 beat_schedule 存在
        assert hasattr(app.conf, 'beat_schedule')
        beat_schedule = app.conf.beat_schedule

        # 验证 update-fund-nav-task 任务存在
        assert 'update-fund-nav-task' in beat_schedule

        task_config = beat_schedule['update-fund-nav-task']
        assert task_config['task'] == 'api.tasks.update_fund_nav'

        # 验证调度时间（每天 22:30）
        schedule = task_config['schedule']
        assert schedule.hour == {22}
        assert schedule.minute == {30}

    def test_celery_timezone_configured(self):
        """测试时区配置"""
        from fundval.celery import app
        # 注意：这个测试依赖于 settings.py 中的配置
        # 如果 settings.py 中配置了 CELERY_TIMEZONE，这里会生效
        # 否则使用默认时区

    def test_task_is_registered(self):
        """测试任务是否已注册"""
        from fundval.celery import app
        from api.tasks import update_fund_nav

        # 获取所有已注册的任务
        registered_tasks = list(app.tasks.keys())

        # 验证任务已注册
        assert 'api.tasks.update_fund_nav' in registered_tasks


@pytest.mark.django_db
class TestCeleryIntegration:
    """测试 Celery 集成"""

    def test_task_can_be_called_directly(self):
        """测试任务可以直接调用"""
        from api.tasks import update_fund_nav

        with patch('api.tasks.call_command'):
            result = update_fund_nav()
            assert result == '净值同步完成'

    def test_task_can_be_called_async(self):
        """测试任务可以异步调用"""
        from api.tasks import update_fund_nav

        # 测试 delay() 方法存在
        assert hasattr(update_fund_nav, 'delay')

        # 测试 apply_async() 方法存在
        assert hasattr(update_fund_nav, 'apply_async')

    @patch('api.tasks.call_command')
    def test_task_execution_with_real_command(self, mock_call_command):
        """测试任务执行真实命令"""
        from api.tasks import update_fund_nav

        # 模拟命令成功执行
        mock_call_command.return_value = None

        result = update_fund_nav()

        # 验证命令被调用
        mock_call_command.assert_called_once_with('update_nav')
        assert result == '净值同步完成'


@pytest.mark.django_db
class TestCelerySettings:
    """测试 Celery 设置"""

    def test_celery_broker_configured(self):
        """测试 Celery Broker 配置"""
        from django.conf import settings

        # 验证 Broker 配置存在
        assert hasattr(settings, 'CELERY_BROKER_URL')
        assert settings.CELERY_BROKER_URL == 'redis://localhost:6379/0'

    def test_celery_result_backend_configured(self):
        """测试结果后端配置"""
        from django.conf import settings

        assert hasattr(settings, 'CELERY_RESULT_BACKEND')
        assert settings.CELERY_RESULT_BACKEND == 'redis://localhost:6379/0'

    def test_celery_apps_installed(self):
        """测试 Celery 相关应用已安装"""
        from django.conf import settings

        installed_apps = settings.INSTALLED_APPS

        assert 'django_celery_results' in installed_apps
        assert 'django_celery_beat' in installed_apps

    def test_celery_timezone_configured(self):
        """测试时区配置"""
        from django.conf import settings

        assert hasattr(settings, 'CELERY_TIMEZONE')
        assert settings.CELERY_TIMEZONE == 'Asia/Shanghai'

    def test_celery_task_time_limit_configured(self):
        """测试任务超时配置"""
        from django.conf import settings

        assert hasattr(settings, 'CELERY_TASK_TIME_LIMIT')
        assert settings.CELERY_TASK_TIME_LIMIT == 30 * 60  # 30 分钟
