"""
测试 BaseEstimateSource 多登录类型扩展（M1）

测试点：
1. get_login_type() 各数据源返回正确值
2. send_sms() / verify_phone() 在非 phone 类型数据源抛 NotImplementedError
3. get_qrcode() / check_qrcode_state() / logout() 有默认实现（不抛 TypeError）
4. /status/ 接口返回 login_type 字段
"""
import pytest
from unittest.mock import patch, MagicMock


class TestGetLoginType:
    """各数据源 get_login_type() 返回值"""

    def test_eastmoney_login_type_is_none(self):
        from api.sources.eastmoney import EastMoneySource
        assert EastMoneySource().get_login_type() == 'none'

    def test_sina_login_type_is_none(self):
        from api.sources.sina import SinaStockSource
        assert SinaStockSource().get_login_type() == 'none'

    def test_yangjibao_login_type_is_qrcode(self):
        from api.sources.yangjibao import YangJiBaoSource
        assert YangJiBaoSource().get_login_type() == 'qrcode'


class TestBaseDefaults:
    """BaseEstimateSource 默认实现（非抽象方法）"""

    def test_eastmoney_get_qrcode_returns_none(self):
        """EastMoney 删掉 stub 后，走 base 默认实现，返回 None"""
        from api.sources.eastmoney import EastMoneySource
        assert EastMoneySource().get_qrcode() is None

    def test_eastmoney_check_qrcode_state_returns_none(self):
        from api.sources.eastmoney import EastMoneySource
        assert EastMoneySource().check_qrcode_state('any-id') is None

    def test_eastmoney_logout_no_exception(self):
        from api.sources.eastmoney import EastMoneySource
        EastMoneySource().logout()  # 不应抛出任何异常

    def test_sina_get_qrcode_returns_none(self):
        from api.sources.sina import SinaStockSource
        assert SinaStockSource().get_qrcode() is None

    def test_sina_logout_no_exception(self):
        from api.sources.sina import SinaStockSource
        SinaStockSource().logout()


class TestSendSmsVerifyPhone:
    """非 phone 类型数据源调用 send_sms/verify_phone 抛 NotImplementedError"""

    def test_eastmoney_send_sms_raises(self):
        from api.sources.eastmoney import EastMoneySource
        with pytest.raises(NotImplementedError):
            EastMoneySource().send_sms('13800138000')

    def test_eastmoney_verify_phone_raises(self):
        from api.sources.eastmoney import EastMoneySource
        with pytest.raises(NotImplementedError):
            EastMoneySource().verify_phone('13800138000', '123456')

    def test_yangjibao_send_sms_raises(self):
        from api.sources.yangjibao import YangJiBaoSource
        with pytest.raises(NotImplementedError):
            YangJiBaoSource().send_sms('13800138000')


class TestStatusApiLoginType:
    """GET /api/source-credentials/status/ 返回 login_type 字段"""

    @pytest.fixture
    def auth_client(self, db):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        User = get_user_model()
        user = User.objects.create_user(username='testuser', password='pass')
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_status_returns_login_type_for_eastmoney(self, auth_client):
        from api.sources.registry import SourceRegistry
        from api.sources.eastmoney import EastMoneySource
        SourceRegistry.register(EastMoneySource())

        res = auth_client.get('/api/source-credentials/status/', {'source_name': 'eastmoney'})
        assert res.status_code == 200
        assert 'login_type' in res.data
        assert res.data['login_type'] == 'none'

    def test_status_returns_login_type_for_yangjibao(self, auth_client):
        from api.sources.registry import SourceRegistry
        from api.sources.yangjibao import YangJiBaoSource
        SourceRegistry.register(YangJiBaoSource())

        res = auth_client.get('/api/source-credentials/status/', {'source_name': 'yangjibao'})
        assert res.status_code == 200
        assert res.data['login_type'] == 'qrcode'
