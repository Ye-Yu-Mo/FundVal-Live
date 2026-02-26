"""
测试 AIConfigSerializer 和 AIPromptTemplateSerializer
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from api.models import AIConfig, AIPromptTemplate

User = get_user_model()


@pytest.mark.django_db
class TestAIConfigSerializer:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def request_context(self, user):
        factory = APIRequestFactory()
        request = factory.get('/')
        request.user = user
        return {'request': request}

    def test_serialize_masks_api_key(self, user, request_context):
        """读取时 api_key 返回脱敏"""
        from api.serializers import AIConfigSerializer

        config = AIConfig.objects.create(
            user=user,
            api_endpoint='https://api.openai.com/v1',
            api_key='sk-real-secret-key',
            model_name='gpt-4o-mini',
        )
        serializer = AIConfigSerializer(config, context=request_context)
        assert serializer.data['api_key'] == '****'

    def test_serialize_returns_endpoint_and_model(self, user, request_context):
        """读取时返回 endpoint 和 model_name"""
        from api.serializers import AIConfigSerializer

        config = AIConfig.objects.create(
            user=user,
            api_endpoint='https://api.openai.com/v1',
            api_key='sk-test',
            model_name='gpt-4o',
        )
        serializer = AIConfigSerializer(config, context=request_context)
        assert serializer.data['api_endpoint'] == 'https://api.openai.com/v1'
        assert serializer.data['model_name'] == 'gpt-4o'

    def test_deserialize_accepts_plaintext_key(self, user, request_context):
        """写入时接受明文 api_key"""
        from api.serializers import AIConfigSerializer

        data = {
            'api_endpoint': 'https://api.openai.com/v1',
            'api_key': 'sk-new-key',
            'model_name': 'gpt-4o-mini',
        }
        serializer = AIConfigSerializer(data=data, context=request_context)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['api_key'] == 'sk-new-key'

    def test_deserialize_requires_endpoint(self, user, request_context):
        """api_endpoint 必填"""
        from api.serializers import AIConfigSerializer

        data = {
            'api_key': 'sk-test',
            'model_name': 'gpt-4o-mini',
        }
        serializer = AIConfigSerializer(data=data, context=request_context)
        assert not serializer.is_valid()
        assert 'api_endpoint' in serializer.errors

    def test_deserialize_requires_api_key(self, user, request_context):
        """api_key 必填"""
        from api.serializers import AIConfigSerializer

        data = {
            'api_endpoint': 'https://api.openai.com/v1',
            'model_name': 'gpt-4o-mini',
        }
        serializer = AIConfigSerializer(data=data, context=request_context)
        assert not serializer.is_valid()
        assert 'api_key' in serializer.errors

    def test_deserialize_model_name_optional(self, user, request_context):
        """model_name 有默认值，可不传"""
        from api.serializers import AIConfigSerializer

        data = {
            'api_endpoint': 'https://api.openai.com/v1',
            'api_key': 'sk-test',
        }
        serializer = AIConfigSerializer(data=data, context=request_context)
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestAIPromptTemplateSerializer:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def request_context(self, user):
        factory = APIRequestFactory()
        request = factory.get('/')
        request.user = user
        return {'request': request}

    def test_serialize_fund_template(self, user, request_context):
        """序列化基金模板"""
        from api.serializers import AIPromptTemplateSerializer

        tpl = AIPromptTemplate.objects.create(
            user=user,
            name='基金模板',
            context_type='fund',
            system_prompt='你是基金分析师',
            user_prompt='分析 {{fund_code}}',
        )
        serializer = AIPromptTemplateSerializer(tpl, context=request_context)
        data = serializer.data
        assert data['name'] == '基金模板'
        assert data['context_type'] == 'fund'
        assert data['system_prompt'] == '你是基金分析师'
        assert data['user_prompt'] == '分析 {{fund_code}}'
        assert data['is_default'] is False

    def test_deserialize_valid_template(self, user, request_context):
        """反序列化合法模板"""
        from api.serializers import AIPromptTemplateSerializer

        data = {
            'name': '持仓模板',
            'context_type': 'position',
            'system_prompt': '你是投资顾问',
            'user_prompt': '分析 {{account_name}}',
        }
        serializer = AIPromptTemplateSerializer(data=data, context=request_context)
        assert serializer.is_valid(), serializer.errors

    def test_deserialize_invalid_context_type(self, user, request_context):
        """context_type 只能是 fund 或 position"""
        from api.serializers import AIPromptTemplateSerializer

        data = {
            'name': '非法模板',
            'context_type': 'invalid_type',
            'system_prompt': 'sys',
            'user_prompt': 'user',
        }
        serializer = AIPromptTemplateSerializer(data=data, context=request_context)
        assert not serializer.is_valid()
        assert 'context_type' in serializer.errors

    def test_deserialize_requires_name(self, user, request_context):
        """name 必填"""
        from api.serializers import AIPromptTemplateSerializer

        data = {
            'context_type': 'fund',
            'system_prompt': 'sys',
            'user_prompt': 'user',
        }
        serializer = AIPromptTemplateSerializer(data=data, context=request_context)
        assert not serializer.is_valid()
        assert 'name' in serializer.errors

    def test_deserialize_requires_prompts(self, user, request_context):
        """system_prompt 和 user_prompt 必填"""
        from api.serializers import AIPromptTemplateSerializer

        data = {
            'name': '模板',
            'context_type': 'fund',
        }
        serializer = AIPromptTemplateSerializer(data=data, context=request_context)
        assert not serializer.is_valid()
        assert 'system_prompt' in serializer.errors
        assert 'user_prompt' in serializer.errors

    def test_serialize_includes_id_and_timestamps(self, user, request_context):
        """序列化包含 id、created_at、updated_at"""
        from api.serializers import AIPromptTemplateSerializer

        tpl = AIPromptTemplate.objects.create(
            user=user,
            name='时间戳模板',
            context_type='fund',
            system_prompt='sys',
            user_prompt='user',
        )
        serializer = AIPromptTemplateSerializer(tpl, context=request_context)
        data = serializer.data
        assert 'id' in data
        assert 'created_at' in data
        assert 'updated_at' in data
