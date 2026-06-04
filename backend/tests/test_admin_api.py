"""
测试管理员用户管理 API

测试点：
1. 管理员获取用户列表（分页、搜索）
2. 管理员禁用/启用用户
3. 管理员重置用户密码
4. 普通用户访问返回 403
5. 被禁用的用户无法登录
"""
import pytest
from django.test import Client
from django.contrib.auth import get_user_model


def _get_token(client, username, password):
    resp = client.post('/api/auth/login',
                       {'username': username, 'password': password},
                       content_type='application/json')
    return resp.json()['access_token']


@pytest.mark.django_db
class TestAdminUserList:
    def test_admin_can_list_users(self):
        User = get_user_model()
        admin = User.objects.create_superuser(username='admin', password='admin123')
        User.objects.create_user(username='user1', password='pass1')
        User.objects.create_user(username='user2', password='pass2')

        client = Client()
        token = _get_token(client, 'admin', 'admin123')
        resp = client.get('/api/admin/users/',
                          HTTP_AUTHORIZATION=f'Bearer {token}')
        assert resp.status_code == 200
        data = resp.json()
        assert data['count'] >= 3  # admin + user1 + user2
        usernames = [u['username'] for u in data['results']]
        assert 'user1' in usernames
        assert 'user2' in usernames

    def test_admin_can_search_users(self):
        User = get_user_model()
        admin = User.objects.create_superuser(username='admin', password='admin123')
        User.objects.create_user(username='alice', password='pass1')
        User.objects.create_user(username='bob', password='pass2')

        client = Client()
        token = _get_token(client, 'admin', 'admin123')
        resp = client.get('/api/admin/users/?search=ali',
                          HTTP_AUTHORIZATION=f'Bearer {token}')
        assert resp.status_code == 200
        data = resp.json()
        assert data['count'] == 1
        assert data['results'][0]['username'] == 'alice'

    def test_non_admin_cannot_list_users(self):
        User = get_user_model()
        admin = User.objects.create_superuser(username='admin', password='admin123')
        user = User.objects.create_user(username='normal', password='pass1')

        client = Client()
        token = _get_token(client, 'normal', 'pass1')
        resp = client.get('/api/admin/users/',
                          HTTP_AUTHORIZATION=f'Bearer {token}')
        assert resp.status_code == 403


@pytest.mark.django_db
class TestAdminToggleUser:
    def test_admin_can_disable_user(self):
        User = get_user_model()
        admin = User.objects.create_superuser(username='admin', password='admin123')
        user = User.objects.create_user(username='target', password='pass1')

        client = Client()
        token = _get_token(client, 'admin', 'admin123')
        resp = client.post(f'/api/admin/users/{user.id}/toggle/',
                           HTTP_AUTHORIZATION=f'Bearer {token}',
                           content_type='application/json')
        assert resp.status_code == 200
        assert resp.json()['is_active'] is False

        # 验证数据库中确实被禁用
        user.refresh_from_db()
        assert user.is_active is False

    def test_admin_can_re_enable_user(self):
        User = get_user_model()
        admin = User.objects.create_superuser(username='admin', password='admin123')
        user = User.objects.create_user(username='target', password='pass1', is_active=False)

        client = Client()
        token = _get_token(client, 'admin', 'admin123')
        resp = client.post(f'/api/admin/users/{user.id}/toggle/',
                           HTTP_AUTHORIZATION=f'Bearer {token}',
                           content_type='application/json')
        assert resp.status_code == 200
        assert resp.json()['is_active'] is True

    def test_non_admin_cannot_toggle(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(username='admin', password='admin123')
        normal = User.objects.create_user(username='normal', password='pass1')
        target = User.objects.create_user(username='target', password='pass1')

        client = Client()
        token = _get_token(client, 'normal', 'pass1')
        resp = client.post(f'/api/admin/users/{target.id}/toggle/',
                           HTTP_AUTHORIZATION=f'Bearer {token}',
                           content_type='application/json')
        assert resp.status_code == 403


@pytest.mark.django_db
class TestAdminResetPassword:
    def test_admin_can_reset_password(self):
        User = get_user_model()
        admin = User.objects.create_superuser(username='admin', password='admin123')
        user = User.objects.create_user(username='target', password='oldpass')

        client = Client()
        token = _get_token(client, 'admin', 'admin123')
        resp = client.post(f'/api/admin/users/{user.id}/reset-password/',
                           HTTP_AUTHORIZATION=f'Bearer {token}',
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.json()
        assert 'new_password' in data
        assert len(data['new_password']) >= 12

        # 验证新密码可以登录
        login_resp = client.post('/api/auth/login',
                                 {'username': 'target', 'password': data['new_password']},
                                 content_type='application/json')
        assert login_resp.status_code == 200

        # 验证旧密码不能登录
        login_resp_old = client.post('/api/auth/login',
                                     {'username': 'target', 'password': 'oldpass'},
                                     content_type='application/json')
        assert login_resp_old.status_code == 401

    def test_non_admin_cannot_reset_password(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(username='admin', password='admin123')
        normal = User.objects.create_user(username='normal', password='pass1')
        target = User.objects.create_user(username='target', password='pass1')

        client = Client()
        token = _get_token(client, 'normal', 'pass1')
        resp = client.post(f'/api/admin/users/{target.id}/reset-password/',
                           HTTP_AUTHORIZATION=f'Bearer {token}',
                           content_type='application/json')
        assert resp.status_code == 403


@pytest.mark.django_db
class TestDisabledUserCannotLogin:
    def test_disabled_user_login_fails(self):
        User = get_user_model()
        User.objects.create_user(username='disabled', password='pass1', is_active=False)

        client = Client()
        resp = client.post('/api/auth/login',
                           {'username': 'disabled', 'password': 'pass1'},
                           content_type='application/json')
        assert resp.status_code == 401
