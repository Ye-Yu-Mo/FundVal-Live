"""
M3 测试：手机号登录 API 端点

测试点：
1. POST /phone/send-sms/ — 正常、数据源不存在、不支持手机登录、缺少参数
2. POST /phone/verify/ — 正常（凭证写库）、验证码错误、不支持手机登录
3. POST /import/ — xiaobeiyangji 导入、yangjibao 默认兼容、未登录
4. GET /status/ — 登录后返回 login_type=phone
"""
import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def client_auth(db):
    user = User.objects.create_user(username='testuser_m3', password='pass')
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def mock_req(payload):
    m = MagicMock()
    m.json.return_value = payload
    m.raise_for_status.return_value = None
    return m


# ─────────────────────────────────────────────
# send-sms
# ─────────────────────────────────────────────

class TestPhoneSendSms:
    @patch('requests.request')
    def test_success(self, mock_request, client_auth):
        mock_request.return_value = mock_req({'code': 200, 'data': 'ok', 'msg': '成功'})
        client, _ = client_auth
        resp = client.post('/api/source-credentials/phone/send-sms/', {
            'source_name': 'xiaobeiyangji',
            'phone': '13800138000',
        }, format='json')
        assert resp.status_code == 200
        assert resp.data['message'] == '验证码已发送'

    def test_source_not_found(self, client_auth):
        client, _ = client_auth
        resp = client.post('/api/source-credentials/phone/send-sms/', {
            'source_name': 'nonexistent',
            'phone': '13800138000',
        }, format='json')
        assert resp.status_code == 404

    def test_source_not_phone_type(self, client_auth):
        """yangjibao 是 qrcode 类型，不支持手机登录"""
        client, _ = client_auth
        resp = client.post('/api/source-credentials/phone/send-sms/', {
            'source_name': 'yangjibao',
            'phone': '13800138000',
        }, format='json')
        assert resp.status_code == 400
        assert '不支持手机号登录' in resp.data['error']

    def test_missing_phone(self, client_auth):
        client, _ = client_auth
        resp = client.post('/api/source-credentials/phone/send-sms/', {
            'source_name': 'xiaobeiyangji',
        }, format='json')
        assert resp.status_code == 400

    def test_missing_source_name(self, client_auth):
        client, _ = client_auth
        resp = client.post('/api/source-credentials/phone/send-sms/', {
            'phone': '13800138000',
        }, format='json')
        assert resp.status_code == 400

    @patch('requests.request')
    def test_api_error_returns_500(self, mock_request, client_auth):
        mock_request.side_effect = Exception('网络超时')
        client, _ = client_auth
        resp = client.post('/api/source-credentials/phone/send-sms/', {
            'source_name': 'xiaobeiyangji',
            'phone': '13800138000',
        }, format='json')
        assert resp.status_code == 500


# ─────────────────────────────────────────────
# phone/verify
# ─────────────────────────────────────────────

class TestPhoneVerify:
    @patch('requests.request')
    def test_success_saves_credential(self, mock_request, client_auth):
        """登录成功后 UserSourceCredential 被写入数据库"""
        from api.models import UserSourceCredential
        mock_request.return_value = mock_req({
            'code': 200,
            'data': {
                'accessToken': 'tok-abc',
                'refreshToken': 'ref-xyz',
                'expiresIn': 2592000,
                'user': {'unionId': '13800138000', 'phone': '13800138000'},
            }
        })
        client, user = client_auth
        resp = client.post('/api/source-credentials/phone/verify/', {
            'source_name': 'xiaobeiyangji',
            'phone': '13800138000',
            'code': '123456',
        }, format='json')
        assert resp.status_code == 200
        assert resp.data['source_name'] == 'xiaobeiyangji'

        cred = UserSourceCredential.objects.filter(
            user=user, source_name='xiaobeiyangji', is_active=True
        ).first()
        assert cred is not None
        assert cred.token == 'tok-abc'

    @patch('requests.request')
    def test_status_returns_logged_in_after_verify(self, mock_request, client_auth):
        """verify 成功后 /status/ 返回 logged_in=true, login_type=phone"""
        mock_request.return_value = mock_req({
            'code': 200,
            'data': {
                'accessToken': 'tok-abc',
                'refreshToken': 'ref-xyz',
                'expiresIn': 2592000,
                'user': {'unionId': '13800138000', 'phone': '13800138000'},
            }
        })
        client, _ = client_auth
        client.post('/api/source-credentials/phone/verify/', {
            'source_name': 'xiaobeiyangji',
            'phone': '13800138000',
            'code': '123456',
        }, format='json')

        resp = client.get('/api/source-credentials/status/?source_name=xiaobeiyangji')
        assert resp.status_code == 200
        assert resp.data['logged_in'] is True
        assert resp.data['login_type'] == 'phone'

    def test_source_not_phone_type(self, client_auth):
        client, _ = client_auth
        resp = client.post('/api/source-credentials/phone/verify/', {
            'source_name': 'yangjibao',
            'phone': '13800138000',
            'code': '123456',
        }, format='json')
        assert resp.status_code == 400

    def test_missing_code(self, client_auth):
        client, _ = client_auth
        resp = client.post('/api/source-credentials/phone/verify/', {
            'source_name': 'xiaobeiyangji',
            'phone': '13800138000',
        }, format='json')
        assert resp.status_code == 400

    @patch('requests.request')
    def test_wrong_code_returns_500(self, mock_request, client_auth):
        mock_request.return_value = mock_req({'code': 400, 'msg': '验证码错误'})
        client, _ = client_auth
        resp = client.post('/api/source-credentials/phone/verify/', {
            'source_name': 'xiaobeiyangji',
            'phone': '13800138000',
            'code': '000000',
        }, format='json')
        assert resp.status_code == 500


# ─────────────────────────────────────────────
# import（通用化）
# ─────────────────────────────────────────────

class TestImportHoldings:
    def test_not_logged_in_returns_400(self, client_auth):
        client, _ = client_auth
        resp = client.post('/api/source-credentials/import/', {
            'source_name': 'xiaobeiyangji',
        }, format='json')
        assert resp.status_code == 400

    def test_yangjibao_default_not_logged_in(self, client_auth):
        """不传 source_name 默认 yangjibao，未登录返回 400"""
        client, _ = client_auth
        resp = client.post('/api/source-credentials/import/', {}, format='json')
        assert resp.status_code == 400

    @patch('api.services.import_xiaobeiyangji.import_from_xiaobeiyangji')
    def test_xiaobeiyangji_import_called(self, mock_import, client_auth):
        """已登录时调用 import_from_xiaobeiyangji"""
        from api.models import UserSourceCredential
        mock_import.return_value = {
            'accounts_created': 1, 'accounts_skipped': 0,
            'holdings_created': 3, 'holdings_skipped': 0,
        }
        _, user = client_auth
        UserSourceCredential.objects.create(
            user=user, source_name='xiaobeiyangji', token='tok-abc', is_active=True
        )
        client, _ = client_auth
        resp = client.post('/api/source-credentials/import/', {
            'source_name': 'xiaobeiyangji',
        }, format='json')
        assert resp.status_code == 200
        assert resp.data['holdings_created'] == 3
        assert mock_import.called
