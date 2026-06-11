"""
Celery 任务

定义所有后台异步任务
"""

from celery import shared_task
from django.core.management import call_command
import logging
import requests
from datetime import date

logger = logging.getLogger(__name__)


@shared_task
def update_fund_nav():
    """
    定时更新基金净值（昨日净值）

    默认从数据源获取最新可用的历史净值并同步到基金主表。
    """
    try:
        call_command("update_nav")
        logger.info("基金昨日/最新净值同步完成")
        return "净值同步完成"
    except Exception as e:
        logger.error(f"基金净值自动更新失败: {str(e)}")
        raise


@shared_task
def update_fund_today_nav():
    """
    定时更新基金当日确认净值

    每天晚间执行，尝试从确权接口抓取今日净值。
    """
    try:
        call_command("update_nav", "--today")
        logger.info("基金今日净值确权完成")
        return "当日净值更新完成"
    except Exception as e:
        logger.error(f"基金当日净值确权失败: {str(e)}")
        raise


@shared_task
def capture_estimate_snapshot():
    """
    捕捉 15:00 收盘估值快照

    每个交易日 15:05 执行，将收盘估值锁定，用于晚间与真实净值对比计算误差。
    """
    from api.models import Fund, EstimateAccuracy
    from api.utils.trading_calendar import is_trading_day
    from django.utils import timezone

    today = timezone.localdate()
    if not is_trading_day(today):
        logger.info(f"{today} 不是交易日，跳过估值捕捉")
        return "非交易日"

    funds = Fund.objects.exclude(estimate_nav__isnull=True)
    count = 0
    for fund in funds:
        # 只捕捉当天的预估
        if fund.estimate_time and fund.estimate_time.date() == today:
            EstimateAccuracy.objects.update_or_create(
                source_name="eastmoney",
                fund=fund,
                estimate_date=today,
                defaults={"estimate_nav": fund.estimate_nav},
            )
            count += 1

    logger.info(f"已捕捉 {count} 个基金的收盘估值快照")
    return f"捕捉完成：{count}"


@shared_task
def check_notification_rules():
    """
    检查通知规则并发送通知

    每 5 分钟执行一次，检查所有激活的通知规则，
    判断是否触发条件，发送通知并记录日志。
    """
    from django.utils import timezone
    from datetime import timedelta
    from decimal import Decimal
    from api.models import NotificationRule, NotificationLog
    from api.notifications import ChannelRegistry

    rules = (
        NotificationRule.objects.filter(is_active=True)
        .select_related("fund", "user")
        .prefetch_related("channels")
    )

    triggered = 0
    sent = 0

    for rule in rules:
        fund = rule.fund
        if fund.estimate_growth is None:
            continue

        growth = Decimal(str(fund.estimate_growth))

        # 判断是否触发
        triggered_flag = False
        if rule.rule_type == "growth_up" and growth >= rule.threshold:
            triggered_flag = True
        elif rule.rule_type == "growth_down" and growth <= -rule.threshold:
            triggered_flag = True

        if not triggered_flag:
            continue

        triggered += 1

        # 检查冷却时间
        cooldown_cutoff = timezone.now() - timedelta(minutes=rule.cooldown_minutes)
        recent_log = NotificationLog.objects.filter(
            rule=rule,
            trigger_time__gte=cooldown_cutoff,
            status="success",
        ).exists()

        if recent_log:
            logger.debug(f"规则 {rule.id} 在冷却期内，跳过")
            continue

        # 构建通知内容
        direction = "涨幅" if rule.rule_type == "growth_up" else "跌幅"
        title = f"基金{direction}提醒：{fund.fund_name}"
        content = (
            f"{fund.fund_name}（{fund.fund_code}）当前{direction} {abs(growth):.2f}%，"
            f"已超过您设定的阈值 {rule.threshold}%。"
        )

        # 逐渠道发送
        for channel_obj in rule.channels.filter(is_active=True):
            channel_impl = ChannelRegistry.get_channel(channel_obj.channel_type)
            if not channel_impl:
                logger.warning(f"未找到渠道实现：{channel_obj.channel_type}")
                continue

            success = False
            error_msg = None
            try:
                success = channel_impl.send(title, content, channel_obj.config)
            except Exception as e:
                error_msg = str(e)
                logger.error(
                    f"发送通知异常：rule={rule.id}, channel={channel_obj.id}, 错误：{e}"
                )

            NotificationLog.objects.create(
                rule=rule,
                channel=channel_obj,
                fund_code=fund.fund_code,
                fund_name=fund.fund_name,
                growth=growth,
                status="success" if success else "failed",
                error_message=error_msg,
            )

            if success:
                sent += 1

    logger.info(f"通知检查完成：触发 {triggered} 条规则，发送 {sent} 条通知")
    return f"触发 {triggered} 条，发送 {sent} 条"


@shared_task
def audit_accuracy():
    """
    审计估值准确率

    每个交易晚间执行，计算所有捕捉到的快照与最终净值的误差。
    """
    from api.utils.trading_calendar import is_trading_day
    from django.utils import timezone

    today = timezone.localdate()
    if not is_trading_day(today):
        logger.info(f"{today} 不是交易日，跳过准确率审计")
        return "非交易日"

    try:
        call_command("calculate_accuracy", date=today.isoformat())
        logger.info(f"{today} 准确率审计完成")
        return "审计完成"
    except Exception as e:
        logger.error(f"准确率审计失败: {str(e)}")
        raise


@shared_task
def capture_intraday_snapshots():
    """
    盘中定时抓取估值快照

    交易日内每 5 分钟执行一次（9:30-15:00），为所有有持仓/自选的基金抓取估值快照，
    用于绘制当日估值曲线。当天收盘后保留 7 天自动清理。
    """
    from datetime import timedelta
    from django.utils import timezone
    from api.models import Fund, EstimateSnapshot, Position
    from api.sources import SourceRegistry
    from api.utils.trading_calendar import is_trading_day

    today = timezone.localdate()
    if not is_trading_day(today):
        logger.info(f"{today} 不是交易日，跳过估值快照抓取")
        return "非交易日"

    now = timezone.localtime()
    # 只在交易时段执行（北京时间）
    market_open = now.replace(hour=9, minute=30, second=0)
    market_close = now.replace(hour=15, minute=5, second=0)
    if now < market_open or now > market_close:
        logger.info(f"{now.time()} 不在交易时段")
        return "非交易时段"

    # 清理 7 天前的旧快照
    cutoff = today - timedelta(days=7)
    deleted, _ = EstimateSnapshot.objects.filter(timestamp__date__lt=cutoff).delete()
    if deleted:
        logger.info(f"清理了 {deleted} 条过期快照")

    # 获取所有有持仓的基金
    fund_ids = Position.objects.values_list("fund_id", flat=True).distinct()
    funds = Fund.objects.filter(id__in=fund_ids)

    # 注入凭证到需要登录的数据源
    from api.models import UserSourceCredential

    source_names = SourceRegistry.list_sources()
    sources = []
    for name in source_names:
        s = SourceRegistry.get_source(name)
        if not s or name == "sina":
            continue
        # 注入凭证
        if s.get_login_type() != "none":
            cred = UserSourceCredential.objects.filter(
                source_name=name, is_active=True
            ).first()
            if cred:
                if hasattr(s, "set_token"):
                    s.set_token(cred.token)
                else:
                    s._token = cred.token
        sources.append(s)

    count = 0
    for fund in funds:
        for source in sources:
            try:
                data = source.fetch_estimate(fund.fund_code)
                if data and data.get("estimate_nav"):
                    EstimateSnapshot.objects.create(
                        fund=fund,
                        source=source.get_source_name(),
                        timestamp=now,
                        estimate_nav=data["estimate_nav"],
                        estimate_growth=data.get("estimate_growth"),
                    )
                    count += 1
                    break  # 一个源成功就不再尝试其他源
            except Exception as e:
                continue

    logger.info(f"已抓取 {count} 个基金的估值快照")
    return f"已抓取 {count} 个快照"


@shared_task
def generate_investment_reports():
    """
    定时生成投资报告

    遍历所有开启了报告的用户，生成 AI 投资周报/月报/年报并推送。
    根据用户设置的 report_frequency 判断是否应该生成（周报=周一，月报=1日，年报=1月1日）。
    """
    from django.contrib.auth import get_user_model
    from api.models import AIConfig, UserPreference
    from api.views import build_report_context, _replace_placeholders

    today = date.today()
    generated = 0
    skip_ai = 0
    skip_disabled = 0

    for pref in UserPreference.objects.filter(report_enabled=True).select_related(
        "user"
    ):
        user = pref.user

        # 检查频率是否匹配今天（支持逗号分隔多选）
        frequencies = [f.strip() for f in pref.report_frequency.split(",")]
        should_run = False
        if "weekly" in frequencies and today.weekday() == 0:
            should_run = True
        if "monthly" in frequencies and today.day == 1:
            should_run = True
        if "yearly" in frequencies and today.month == 1 and today.day == 1:
            should_run = True

        if not should_run:
            continue

        ai_config = AIConfig.objects.filter(user=user).first()
        if not ai_config:
            skip_ai += 1
            continue

        try:
            context_data = build_report_context(user, pref.report_frequency)
            system_prompt = "你是一位专业的基金投资顾问，请根据提供的持仓数据，生成一份结构清晰、客观专业的投资报告。使用 Markdown 格式，报告标题下方标注生成日期。"
            user_prompt = (
                f'请根据以下数据生成一份投资报告（报告日期：{today.strftime("%Y年%m月%d日")}）：\n\n'
                f'## 账户总览\n{context_data.get("account_summary", "")}\n\n'
                f'## 持仓明细\n{context_data.get("position_summary", "")}\n\n'
                f'## 期间表现\n{context_data.get("period_pnl", "")}\n\n'
                f'## 表现最佳\n{context_data.get("top_performers", "")}\n\n'
                f'## 表现最差\n{context_data.get("worst_performers", "")}\n'
            )

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

            # 推送报告到用户通知渠道
            from api.models import NotificationChannel
            from api.notifications import ChannelRegistry

            channels = NotificationChannel.objects.filter(user=user, is_active=True)
            for ch in channels:
                impl = ChannelRegistry.get_channel(ch.channel_type)
                if impl:
                    try:
                        impl.send(
                            f"Fundval 投资{pref.report_frequency}报",
                            content[:4000],  # 截断避免过长
                            ch.config,
                        )
                    except Exception as e:
                        logger.warning(f"推送报告到渠道 {ch.id} 失败: {e}")

            generated += 1
        except Exception as e:
            logger.error(f"为用户 {user.username} 生成报告失败: {e}")

    summary = f"{generated} reports generated, {skip_ai} skipped (no AI config), {skip_disabled} skipped (disabled)"
    logger.info(summary)
    return summary
