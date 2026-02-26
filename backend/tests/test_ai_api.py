"""
测试 AIConfigViewSet、AIPromptTemplateViewSet 和 ai_analyze 视图

测试点：
1. GET/PUT /api/ai/config/ — AI配置管理
2. CRUD /api/ai/templates/ — 提示词模板管理
3. POST /api/ai/analyze/ — AI分析（占位符替换 + OpenAI调用）
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from api.models import AIConfig, AIPromptTemplate, Fund, Account, Position, PositionOperation, FundNavHistory

User = get_user_model()


# ─────────────────────────────────────────────
# 1. AIConfigViewSet
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestAIConfigViewSet:

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client.force_authenticate(user=self.user)

    def test_get_config_not_exists(self):
        """未配置时返回空"""
        response = self.client.get('/api/ai/config/')
        assert response.status_code == 200
        assert response.data['api_endpoint'] == ''
        assert response.data['api_key'] == ''
        assert response.data['model_name'] == 'gpt-4o-mini'

    def test_get_config_exists(self):
        """已配置时返回脱敏数据"""
        AIConfig.objects.create(
            user=self.user,
            api_endpoint='https://api.openai.com/v1',
            api_key='sk-secret',
            model_name='gpt-4o',
        )
        response = self.client.get('/api/ai/config/')
        assert response.status_code == 200
        assert response.data['api_endpoint'] == 'https://api.openai.com/v1'
        assert response.data['api_key'] == '****'
        assert response.data['model_name'] == 'gpt-4o'

    def test_put_config_creates(self):
        """PUT 创建配置"""
        response = self.client.put('/api/ai/config/', {
            'api_endpoint': 'https://api.openai.com/v1',
            'api_key': 'sk-new-key',
            'model_name': 'gpt-4o-mini',
        }, format='json')
        assert response.status_code == 200
        config = AIConfig.objects.get(user=self.user)
        assert config.api_key == 'sk-new-key'

    def test_put_config_updates(self):
        """PUT 更新已有配置"""
        AIConfig.objects.create(
            user=self.user,
            api_endpoint='https://old.endpoint.com/v1',
            api_key='sk-old',
            model_name='gpt-3.5',
        )
        response = self.client.put('/api/ai/config/', {
            'api_endpoint': 'https://api.openai.com/v1',
            'api_key': 'sk-new',
            'model_name': 'gpt-4o',
        }, format='json')
        assert response.status_code == 200
        assert AIConfig.objects.filter(user=self.user).count() == 1
        config = AIConfig.objects.get(user=self.user)
        assert config.api_key == 'sk-new'
        assert config.model_name == 'gpt-4o'

    def test_put_config_missing_endpoint(self):
        """PUT 缺少 api_endpoint 返回 400"""
        response = self.client.put('/api/ai/config/', {
            'api_key': 'sk-test',
        }, format='json')
        assert response.status_code == 400

    def test_unauthenticated(self):
        """未认证返回 401"""
        client = APIClient()
        response = client.get('/api/ai/config/')
        assert response.status_code == 401


# ─────────────────────────────────────────────
# 2. AIPromptTemplateViewSet
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestAIPromptTemplateViewSet:

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client.force_authenticate(user=self.user)

    def test_list_templates_empty(self):
        """无模板时返回空列表"""
        response = self.client.get('/api/ai/templates/')
        assert response.status_code == 200
        assert response.data == []

    def test_list_templates_only_own(self):
        """只返回当前用户的模板"""
        other_user = User.objects.create_user(username='other', password='pass')
        AIPromptTemplate.objects.create(
            user=other_user, name='他人模板', context_type='fund',
            system_prompt='sys', user_prompt='user',
        )
        AIPromptTemplate.objects.create(
            user=self.user, name='我的模板', context_type='fund',
            system_prompt='sys', user_prompt='user',
        )
        response = self.client.get('/api/ai/templates/')
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['name'] == '我的模板'

    def test_list_filter_by_context_type(self):
        """按 context_type 过滤"""
        AIPromptTemplate.objects.create(
            user=self.user, name='基金模板', context_type='fund',
            system_prompt='sys', user_prompt='user',
        )
        AIPromptTemplate.objects.create(
            user=self.user, name='持仓模板', context_type='position',
            system_prompt='sys', user_prompt='user',
        )
        response = self.client.get('/api/ai/templates/?context_type=fund')
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['context_type'] == 'fund'

    def test_create_template(self):
        """创建模板"""
        response = self.client.post('/api/ai/templates/', {
            'name': '新模板',
            'context_type': 'fund',
            'system_prompt': '你是基金分析师',
            'user_prompt': '分析 {{fund_code}}',
        }, format='json')
        assert response.status_code == 201
        assert AIPromptTemplate.objects.filter(user=self.user, name='新模板').exists()

    def test_create_template_invalid_context_type(self):
        """非法 context_type 返回 400"""
        response = self.client.post('/api/ai/templates/', {
            'name': '非法模板',
            'context_type': 'invalid',
            'system_prompt': 'sys',
            'user_prompt': 'user',
        }, format='json')
        assert response.status_code == 400

    def test_update_template(self):
        """更新模板"""
        tpl = AIPromptTemplate.objects.create(
            user=self.user, name='旧名称', context_type='fund',
            system_prompt='旧sys', user_prompt='旧user',
        )
        response = self.client.put(f'/api/ai/templates/{tpl.id}/', {
            'name': '新名称',
            'context_type': 'fund',
            'system_prompt': '新sys',
            'user_prompt': '新user',
        }, format='json')
        assert response.status_code == 200
        tpl.refresh_from_db()
        assert tpl.name == '新名称'

    def test_delete_template(self):
        """删除模板"""
        tpl = AIPromptTemplate.objects.create(
            user=self.user, name='待删除', context_type='fund',
            system_prompt='sys', user_prompt='user',
        )
        response = self.client.delete(f'/api/ai/templates/{tpl.id}/')
        assert response.status_code == 204
        assert not AIPromptTemplate.objects.filter(id=tpl.id).exists()

    def test_cannot_access_other_user_template(self):
        """不能访问他人模板"""
        other_user = User.objects.create_user(username='other', password='pass')
        tpl = AIPromptTemplate.objects.create(
            user=other_user, name='他人模板', context_type='fund',
            system_prompt='sys', user_prompt='user',
        )
        response = self.client.get(f'/api/ai/templates/{tpl.id}/')
        assert response.status_code == 404

    def test_unauthenticated(self):
        """未认证返回 401"""
        client = APIClient()
        response = client.get('/api/ai/templates/')
        assert response.status_code == 401


# ─────────────────────────────────────────────
# 3. ai_analyze 视图
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestAIAnalyze:

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client.force_authenticate(user=self.user)
        AIConfig.objects.create(
            user=self.user,
            api_endpoint='https://api.openai.com/v1',
            api_key='sk-test',
            model_name='gpt-4o-mini',
        )

    def test_analyze_fund_placeholder_replacement(self):
        """基金维度占位符替换正确"""
        tpl = AIPromptTemplate.objects.create(
            user=self.user,
            name='基金模板',
            context_type='fund',
            system_prompt='你是基金分析师',
            user_prompt='基金代码:{{fund_code}} 名称:{{fund_name}} 净值:{{latest_nav}}',
        )
        context_data = {
            'fund_code': '000001',
            'fund_name': '华夏成长',
            'fund_type': '混合型',
            'latest_nav': '1.5000',
            'latest_nav_date': '2026-02-25',
            'estimate_nav': '1.52',
            'estimate_growth': '1.33',
            'nav_history': '2026-02-24:1.49,2026-02-25:1.50',
            'holding_share': '1000.00',
            'holding_cost': '1400.00',
            'holding_value': '1500.00',
            'pnl': '100.00',
            'pnl_rate': '7.14',
        }

        with patch('api.views.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                'choices': [{'message': {'content': 'AI分析结果'}}]
            }
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            response = self.client.post('/api/ai/analyze/', {
                'template_id': tpl.id,
                'context_type': 'fund',
                'context_data': context_data,
            }, format='json')

        assert response.status_code == 200
        assert response.data['result'] == 'AI分析结果'

        # 验证占位符被替换
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        user_msg = next(m['content'] for m in payload['messages'] if m['role'] == 'user')
        assert '000001' in user_msg
        assert '华夏成长' in user_msg
        assert '1.5000' in user_msg

    def test_analyze_position_placeholder_replacement(self):
        """持仓维度占位符替换正确"""
        tpl = AIPromptTemplate.objects.create(
            user=self.user,
            name='持仓模板',
            context_type='position',
            system_prompt='你是投资顾问',
            user_prompt='账户:{{account_name}} 持仓:{{positions}} 盈亏:{{pnl}}',
        )
        context_data = {
            'account_name': '我的账户',
            'holding_cost': '10000.00',
            'holding_value': '11000.00',
            'pnl': '1000.00',
            'pnl_rate': '10.00',
            'positions': '000001|华夏成长|1000|1400|1500|100\n000002|易方达|500|600|650|50',
        }

        with patch('api.views.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                'choices': [{'message': {'content': '持仓分析结果'}}]
            }
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            response = self.client.post('/api/ai/analyze/', {
                'template_id': tpl.id,
                'context_type': 'position',
                'context_data': context_data,
            }, format='json')

        assert response.status_code == 200
        assert response.data['result'] == '持仓分析结果'

        call_args = mock_post.call_args
        payload = call_args[1]['json']
        user_msg = next(m['content'] for m in payload['messages'] if m['role'] == 'user')
        assert '我的账户' in user_msg
        assert '1000.00' in user_msg

    def test_analyze_no_ai_config(self):
        """未配置AI返回 400"""
        AIConfig.objects.filter(user=self.user).delete()
        tpl = AIPromptTemplate.objects.create(
            user=self.user, name='模板', context_type='fund',
            system_prompt='sys', user_prompt='user',
        )
        response = self.client.post('/api/ai/analyze/', {
            'template_id': tpl.id,
            'context_type': 'fund',
            'context_data': {},
        }, format='json')
        assert response.status_code == 400

    def test_analyze_template_not_found(self):
        """模板不存在返回 404"""
        response = self.client.post('/api/ai/analyze/', {
            'template_id': 99999,
            'context_type': 'fund',
            'context_data': {},
        }, format='json')
        assert response.status_code == 404

    def test_analyze_other_user_template(self):
        """不能使用他人模板"""
        other_user = User.objects.create_user(username='other', password='pass')
        tpl = AIPromptTemplate.objects.create(
            user=other_user, name='他人模板', context_type='fund',
            system_prompt='sys', user_prompt='user',
        )
        response = self.client.post('/api/ai/analyze/', {
            'template_id': tpl.id,
            'context_type': 'fund',
            'context_data': {},
        }, format='json')
        assert response.status_code == 404

    def test_analyze_openai_error(self):
        """OpenAI 调用失败返回 502"""
        tpl = AIPromptTemplate.objects.create(
            user=self.user, name='模板', context_type='fund',
            system_prompt='sys', user_prompt='user',
        )
        with patch('api.views.requests.post') as mock_post:
            mock_post.side_effect = Exception('Network error')

            response = self.client.post('/api/ai/analyze/', {
                'template_id': tpl.id,
                'context_type': 'fund',
                'context_data': {'fund_code': '000001'},
            }, format='json')

        assert response.status_code == 502

    def test_analyze_unauthenticated(self):
        """未认证返回 401"""
        client = APIClient()
        response = client.post('/api/ai/analyze/', {}, format='json')
        assert response.status_code == 401
