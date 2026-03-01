import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_add_user_preference'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AIConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_endpoint', models.CharField(help_text='OpenAI协议接口地址', max_length=500)),
                ('api_key', models.CharField(help_text='API Key', max_length=500)),
                ('model_name', models.CharField(default='gpt-4o-mini', help_text='模型名称', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ai_config', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'AI配置',
                'verbose_name_plural': 'AI配置',
                'db_table': 'ai_config',
            },
        ),
        migrations.CreateModel(
            name='AIPromptTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='模板名称', max_length=100)),
                ('context_type', models.CharField(choices=[('fund', '基金分析'), ('position', '持仓分析')], help_text='分析维度', max_length=20)),
                ('system_prompt', models.TextField(help_text='系统提示词')),
                ('user_prompt', models.TextField(help_text='用户提示词（含占位符）')),
                ('is_default', models.BooleanField(default=False, help_text='是否为该类型的默认模板')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_templates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'AI提示词模板',
                'verbose_name_plural': 'AI提示词模板',
                'db_table': 'ai_prompt_template',
                'unique_together': {('user', 'name')},
            },
        ),
    ]
