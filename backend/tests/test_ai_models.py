from django.test import TestCase
from django.contrib.auth import get_user_model
from api.models import AIConfig, AIPromptTemplate

User = get_user_model()


class AIConfigModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_create_ai_config(self):
        config = AIConfig.objects.create(
            user=self.user,
            api_endpoint='https://api.openai.com/v1',
            api_key='sk-test-key',
            model_name='gpt-4o-mini',
        )
        self.assertEqual(config.user, self.user)
        self.assertEqual(config.model_name, 'gpt-4o-mini')
        self.assertEqual(str(config), 'testuser - gpt-4o-mini')

    def test_ai_config_one_to_one(self):
        AIConfig.objects.create(
            user=self.user,
            api_endpoint='https://api.openai.com/v1',
            api_key='sk-test',
            model_name='gpt-4o',
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            AIConfig.objects.create(
                user=self.user,
                api_endpoint='https://api.openai.com/v1',
                api_key='sk-test2',
                model_name='gpt-4o',
            )

    def test_ai_config_default_model(self):
        config = AIConfig.objects.create(
            user=self.user,
            api_endpoint='https://api.openai.com/v1',
            api_key='sk-test',
        )
        self.assertEqual(config.model_name, 'gpt-4o-mini')


class AIPromptTemplateModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_create_fund_template(self):
        tpl = AIPromptTemplate.objects.create(
            user=self.user,
            name='基金分析模板',
            context_type='fund',
            system_prompt='你是一个基金分析师。',
            user_prompt='请分析基金 {{fund_code}} {{fund_name}}，当前净值 {{latest_nav}}。',
        )
        self.assertEqual(tpl.context_type, 'fund')
        self.assertFalse(tpl.is_default)
        self.assertEqual(str(tpl), 'testuser - 基金分析模板')

    def test_create_position_template(self):
        tpl = AIPromptTemplate.objects.create(
            user=self.user,
            name='持仓分析模板',
            context_type='position',
            system_prompt='你是一个投资顾问。',
            user_prompt='账户 {{account_name}} 持仓如下：{{positions}}',
        )
        self.assertEqual(tpl.context_type, 'position')

    def test_template_unique_name_per_user(self):
        AIPromptTemplate.objects.create(
            user=self.user,
            name='重复名称',
            context_type='fund',
            system_prompt='sys',
            user_prompt='user',
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            AIPromptTemplate.objects.create(
                user=self.user,
                name='重复名称',
                context_type='position',
                system_prompt='sys2',
                user_prompt='user2',
            )

    def test_different_users_same_name(self):
        user2 = User.objects.create_user(username='testuser2', password='testpass')
        AIPromptTemplate.objects.create(
            user=self.user,
            name='共用名称',
            context_type='fund',
            system_prompt='sys',
            user_prompt='user',
        )
        # 不同用户可以用相同名称
        tpl2 = AIPromptTemplate.objects.create(
            user=user2,
            name='共用名称',
            context_type='fund',
            system_prompt='sys',
            user_prompt='user',
        )
        self.assertEqual(tpl2.user, user2)

    def test_is_default_flag(self):
        tpl = AIPromptTemplate.objects.create(
            user=self.user,
            name='默认模板',
            context_type='fund',
            system_prompt='sys',
            user_prompt='user',
            is_default=True,
        )
        self.assertTrue(tpl.is_default)

    def test_context_type_choices(self):
        valid_types = ['fund', 'position']
        for ct in valid_types:
            tpl = AIPromptTemplate.objects.create(
                user=self.user,
                name=f'模板_{ct}',
                context_type=ct,
                system_prompt='sys',
                user_prompt='user',
            )
            self.assertEqual(tpl.context_type, ct)
