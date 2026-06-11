from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model, authenticate
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
import json
import requests

from fundval.config import config
from fundval.bootstrap import verify_bootstrap_key, get_bootstrap_key


def health(request):
    """健康检查接口"""
    # 检查数据库连接
    db_status = "disconnected"
    try:
        connection.ensure_connection()
        db_status = "connected"
    except Exception:
        pass

    return JsonResponse(
        {
            "status": "ok",
            "database": db_status,
            "system_initialized": config.get("system_initialized", False),
            "version": "2.5.3",
        }
    )


# Bootstrap 相关视图


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def bootstrap_verify(request):
    """验证 bootstrap_key"""
    # 如果已初始化，返回 410 Gone
    if config.get("system_initialized"):
        return Response({"error": "System already initialized"}, status=410)

    data = json.loads(request.body)
    key = data.get("bootstrap_key")

    if verify_bootstrap_key(key):
        return Response({"valid": True, "message": "密钥验证成功"})
    else:
        return Response({"valid": False, "error": "密钥无效"}, status=400)


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def bootstrap_initialize(request):
    """初始化系统"""
    # 如果已初始化，返回 410 Gone
    if config.get("system_initialized"):
        return Response({"error": "System already initialized"}, status=410)

    data = json.loads(request.body)
    key = data.get("bootstrap_key")
    admin_username = data.get("admin_username")
    admin_password = data.get("admin_password")
    allow_register = data.get("allow_register", False)

    # 验证 bootstrap_key
    if not verify_bootstrap_key(key):
        return Response({"error": "密钥无效"}, status=400)

    # 创建管理员账户
    User = get_user_model()
    try:
        admin = User.objects.create_superuser(
            username=admin_username,
            password=admin_password,
            email=f"{admin_username}@fundval.local",
        )
    except Exception as e:
        return Response({"error": f"创建管理员失败: {str(e)}"}, status=400)

    # 更新配置
    config.set("system_initialized", True)
    config.set("allow_register", allow_register)
    config.save()

    return Response({"message": "系统初始化成功", "admin_created": True})


# 认证相关视图


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    """用户登录"""
    data = json.loads(request.body)
    username = data.get("username")
    password = data.get("password")

    user = authenticate(username=username, password=password)

    if user is None:
        return Response({"error": "用户名或密码错误"}, status=401)

    # 生成 JWT token
    refresh = RefreshToken.for_user(user)

    return Response(
        {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": {
                "id": str(user.id),
                "username": user.username,
                "role": "admin" if user.is_superuser else "user",
            },
        }
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_token(request):
    """刷新 token"""
    data = json.loads(request.body)
    refresh_token_str = data.get("refresh_token")

    try:
        refresh = RefreshToken(refresh_token_str)
        return Response({"access_token": str(refresh.access_token)})
    except Exception as e:
        return Response({"error": "Invalid refresh token"}, status=400)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """获取当前用户信息"""
    user = request.user
    return Response(
        {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": "admin" if user.is_superuser else "user",
            "created_at": user.date_joined.isoformat(),
        }
    )


@csrf_exempt
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """修改密码"""
    data = json.loads(request.body)
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    user = request.user

    if not user.check_password(old_password):
        return Response({"error": "旧密码错误"}, status=400)

    user.set_password(new_password)
    user.save()

    return Response({"message": "密码修改成功"})


def _replace_placeholders(template: str, context_data: dict) -> str:
    """将模板中的 {{key}} 占位符替换为 context_data 中的值"""
    for key, value in context_data.items():
        template = template.replace(
            f"{{{{{key}}}}}", str(value) if value is not None else ""
        )
    return template


def build_report_context(user, period="weekly"):
    """构建投资报告占位符上下文数据"""
    from decimal import Decimal
    from datetime import timedelta
    from .models import Account, Position, PositionOperation

    today = timezone.localdate()

    # 计算期间范围
    if period == "weekly":
        start_date = today - timedelta(days=7)
        period_name = "本周"
    elif period == "yearly":
        start_date = today.replace(month=1, day=1)
        period_name = "本年"
    else:
        start_date = today.replace(day=1)
        period_name = "本月"

    # 账户总览
    accounts = Account.objects.filter(user=user, parent=None).prefetch_related(
        "children__positions__fund"
    )
    if not accounts.exists():
        return {
            "account_summary": "暂无账户",
            "position_summary": "暂无持仓",
            "period_pnl": "N/A",
            "top_performers": "无数据",
            "worst_performers": "无数据",
            "market_overview": "",
        }

    account_summary = []
    total_value = Decimal("0")
    total_cost = Decimal("0")
    total_pnl = Decimal("0")

    for acc in accounts:
        val = Decimal(acc.holding_value or 0)
        cost = Decimal(acc.holding_cost or 0)
        pnl = Decimal(acc.pnl or 0)
        total_value += val
        total_cost += cost
        total_pnl += pnl
        account_summary.append(
            f"- {acc.name}: 市值 ¥{val:.2f}, 成本 ¥{cost:.2f}, 盈亏 ¥{pnl:.2f}"
        )

    pnl_rate = f"{(total_pnl / total_cost * 100):.2f}%" if total_cost > 0 else "0%"

    # 持仓明细
    positions = Position.objects.filter(account__user=user).select_related(
        "account", "fund"
    )
    if not positions.exists():
        return {
            "account_summary": "\n".join(account_summary),
            "position_summary": "暂无持仓",
            "period_pnl": f"{period_name}盈亏: ¥{total_pnl:.2f} ({pnl_rate})",
            "top_performers": "无数据",
            "worst_performers": "无数据",
            "market_overview": "",
        }

    position_lines = []
    fund_perf = []
    for pos in positions:
        latest_nav = pos.fund.latest_nav or Decimal("0")
        market_value = pos.holding_share * latest_nav
        pnl_val = pos.pnl or 0
        pnl_r = (
            f"{(pnl_val / pos.holding_cost * 100):.2f}%"
            if pos.holding_cost > 0
            else "0%"
        )
        position_lines.append(
            f"- {pos.fund.fund_name}({pos.fund.fund_code}): "
            f"{pos.holding_share:.4f}份, 成本 ¥{pos.holding_cost:.2f}, "
            f"市值 ¥{market_value:.2f}, 盈亏 ¥{pnl_val:.2f}({pnl_r})"
        )
        fund_perf.append((pos.fund.fund_name, pnl_val, pnl_r))

    # Top/Worst performers
    sorted_perf = sorted(fund_perf, key=lambda x: x[1], reverse=True)
    top = sorted_perf[:3]
    worst = sorted_perf[-3:][::-1]

    top_str = "\n".join(
        [
            f"{i+1}. {name}: ¥{pnl:.2f}({rate})"
            for i, (name, pnl, rate) in enumerate(top)
        ]
    )
    worst_str = "\n".join(
        [
            f"{i+1}. {name}: ¥{pnl:.2f}({rate})"
            for i, (name, pnl, rate) in enumerate(worst)
        ]
    )

    return {
        "account_summary": f"总市值: ¥{total_value:.2f}\n总成本: ¥{total_cost:.2f}\n总盈亏: ¥{total_pnl:.2f}({pnl_rate})\n\n"
        + "\n".join(account_summary),
        "position_summary": "\n".join(position_lines),
        "period_pnl": f"{period_name}盈亏: ¥{total_pnl:.2f} ({pnl_rate})",
        "top_performers": top_str if top_str else "无数据",
        "worst_performers": worst_str if worst_str else "无数据",
        "market_overview": "",
    }


@api_view(["POST"])
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

    template_id = request.data.get("template_id")
    context_data = request.data.get("context_data", {})

    if not template_id:
        return Response(
            {"error": "缺少 template_id"}, status=status.HTTP_400_BAD_REQUEST
        )

    # 取模板（只能用自己的）
    try:
        template = AIPromptTemplate.objects.get(id=template_id, user=request.user)
    except AIPromptTemplate.DoesNotExist:
        return Response({"error": "模板不存在"}, status=status.HTTP_404_NOT_FOUND)

    # 取AI配置
    ai_config = AIConfig.objects.filter(user=request.user).first()
    if not ai_config:
        return Response(
            {"error": "未配置AI接口，请先在设置中配置"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 替换占位符
    system_prompt = _replace_placeholders(template.system_prompt, context_data)
    user_prompt = _replace_placeholders(template.user_prompt, context_data)

    # 调用 OpenAI 协议接口
    try:
        endpoint = ai_config.api_endpoint.rstrip("/")
        resp = requests.post(
            f"{endpoint}/chat/completions",
            headers={
                "Authorization": f"Bearer {ai_config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": ai_config.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        return Response({"result": content})
    except Exception as e:
        return Response(
            {"error": f"AI接口调用失败: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_report_preview(request):
    """
    POST /api/ai/report-preview/
    {
        "period": "weekly" | "monthly" | "yearly",
        "template_id": 1  // 可选，不传则用内置模板
    }
    """
    from .models import AIConfig, AIPromptTemplate

    period = request.data.get("period", "monthly")
    template_id = request.data.get("template_id")

    # 取 AI 配置
    ai_config = AIConfig.objects.filter(user=request.user).first()
    if not ai_config:
        return Response(
            {"error": "未配置AI接口，请先在设置中配置"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 构建上下文
    context_data = build_report_context(request.user, period)

    # 系统提示词
    system_prompt = "你是一位专业的基金投资顾问，擅长撰写投资分析报告。请根据提供的持仓数据，生成一份结构清晰、客观专业的投资报告。使用 Markdown 格式，报告标题下方标注生成日期。"
    user_prompt = (
        f'请根据以下数据生成一份投资报告（报告日期：{timezone.now().strftime("%Y年%m月%d日")}）：\n\n'
        f'## 账户总览\n{context_data.get("account_summary", "")}\n\n'
        f'## 持仓明细\n{context_data.get("position_summary", "")}\n\n'
        f'## 期间表现\n{context_data.get("period_pnl", "")}\n\n'
        f'## 表现最佳\n{context_data.get("top_performers", "")}\n\n'
        f'## 表现最差\n{context_data.get("worst_performers", "")}\n'
    )

    # 如果指定了模板，用模板替换
    if template_id:
        try:
            template = AIPromptTemplate.objects.get(id=template_id, user=request.user)
            system_prompt = _replace_placeholders(template.system_prompt, context_data)
            user_prompt = _replace_placeholders(template.user_prompt, context_data)
        except AIPromptTemplate.DoesNotExist:
            pass

    try:
        endpoint = ai_config.api_endpoint.rstrip("/")
        resp = requests.post(
            f"{endpoint}/chat/completions",
            headers={
                "Authorization": f"Bearer {ai_config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": ai_config.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        return Response({"result": content})
    except Exception as e:
        return Response(
            {"error": f"AI接口调用失败: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY
        )
