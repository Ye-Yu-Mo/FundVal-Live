from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model, authenticate
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
import json
import requests

from fundval.config import config
from fundval.bootstrap import verify_bootstrap_key, get_bootstrap_key


def health(request):
    """健康检查接口"""
    # 检查数据库连接
    db_status = 'disconnected'
    try:
        connection.ensure_connection()
        db_status = 'connected'
    except Exception:
        pass

    return JsonResponse({
        'status': 'ok',
        'database': db_status,
        'system_initialized': config.get('system_initialized', False),
    })


# Bootstrap 相关视图

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def bootstrap_verify(request):
    """验证 bootstrap_key"""
    # 如果已初始化，返回 410 Gone
    if config.get('system_initialized'):
        return Response({'error': 'System already initialized'}, status=410)

    data = json.loads(request.body)
    key = data.get('bootstrap_key')

    if verify_bootstrap_key(key):
        return Response({'valid': True, 'message': '密钥验证成功'})
    else:
        return Response({'valid': False, 'error': '密钥无效'}, status=400)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def bootstrap_initialize(request):
    """初始化系统"""
    # 如果已初始化，返回 410 Gone
    if config.get('system_initialized'):
        return Response({'error': 'System already initialized'}, status=410)

    data = json.loads(request.body)
    key = data.get('bootstrap_key')
    admin_username = data.get('admin_username')
    admin_password = data.get('admin_password')
    allow_register = data.get('allow_register', False)

    # 验证 bootstrap_key
    if not verify_bootstrap_key(key):
        return Response({'error': '密钥无效'}, status=400)

    # 创建管理员账户
    User = get_user_model()
    try:
        admin = User.objects.create_superuser(
            username=admin_username,
            password=admin_password,
            email=f'{admin_username}@fundval.local'
        )
    except Exception as e:
        return Response({'error': f'创建管理员失败: {str(e)}'}, status=400)

    # 更新配置
    config.set('system_initialized', True)
    config.set('allow_register', allow_register)
    config.save()

    return Response({
        'message': '系统初始化成功',
        'admin_created': True
    })


# 认证相关视图

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """用户登录"""
    data = json.loads(request.body)
    username = data.get('username')
    password = data.get('password')

    user = authenticate(username=username, password=password)

    if user is None:
        return Response({'error': '用户名或密码错误'}, status=401)

    # 生成 JWT token
    refresh = RefreshToken.for_user(user)

    return Response({
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
        'user': {
            'id': str(user.id),
            'username': user.username,
            'role': 'admin' if user.is_superuser else 'user'
        }
    })


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """刷新 token"""
    data = json.loads(request.body)
    refresh_token_str = data.get('refresh_token')

    try:
        refresh = RefreshToken(refresh_token_str)
        return Response({
            'access_token': str(refresh.access_token)
        })
    except Exception as e:
        return Response({'error': 'Invalid refresh token'}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """获取当前用户信息"""
    user = request.user
    return Response({
        'id': str(user.id),
        'username': user.username,
        'email': user.email,
        'role': 'admin' if user.is_superuser else 'user',
        'created_at': user.date_joined.isoformat()
    })


@csrf_exempt
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """修改密码"""
    data = json.loads(request.body)
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    user = request.user

    if not user.check_password(old_password):
        return Response({'error': '旧密码错误'}, status=400)

    user.set_password(new_password)
    user.save()

    return Response({'message': '密码修改成功'})


def _replace_placeholders(template: str, context_data: dict) -> str:
    """将模板中的 {{key}} 占位符替换为 context_data 中的值"""
    for key, value in context_data.items():
        template = template.replace(f'{{{{{key}}}}}', str(value) if value is not None else '')
    return template


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_analyze(request):
    """
    POST /api/ai/analyze/
    {
        "template_id": 1,
        "context_type": "fund" | "position",
        "context_data": { ... }
    }
    """
    from .models import AIConfig, AIPromptTemplate

    template_id = request.data.get('template_id')
    context_data = request.data.get('context_data', {})

    if not template_id:
        return Response({'error': '缺少 template_id'}, status=status.HTTP_400_BAD_REQUEST)

    # 取模板（只能用自己的）
    try:
        template = AIPromptTemplate.objects.get(id=template_id, user=request.user)
    except AIPromptTemplate.DoesNotExist:
        return Response({'error': '模板不存在'}, status=status.HTTP_404_NOT_FOUND)

    # 取AI配置
    ai_config = AIConfig.objects.filter(user=request.user).first()
    if not ai_config:
        return Response({'error': '未配置AI接口，请先在设置中配置'}, status=status.HTTP_400_BAD_REQUEST)

    # 替换占位符
    system_prompt = _replace_placeholders(template.system_prompt, context_data)
    user_prompt = _replace_placeholders(template.user_prompt, context_data)

    # 调用 OpenAI 协议接口
    try:
        endpoint = ai_config.api_endpoint.rstrip('/')
        resp = requests.post(
            f'{endpoint}/chat/completions',
            headers={
                'Authorization': f'Bearer {ai_config.api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': ai_config.model_name,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        content = result['choices'][0]['message']['content']
        return Response({'result': content})
    except Exception as e:
        return Response({'error': f'AI接口调用失败: {str(e)}'}, status=status.HTTP_502_BAD_GATEWAY)
