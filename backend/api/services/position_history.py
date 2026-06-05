"""
账户历史市值计算服务

核心逻辑：
1. 回放流水，计算每日持仓（份额和成本）
2. 查询每日净值
3. 计算每日市值 = Σ(份额 × 净值)
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Set
from ..models import PositionOperation, FundNavHistory, Fund


def calculate_account_history(account_id: str, days: int = 30) -> List[Dict]:
    """
    计算账户历史市值

    参数:
        account_id: 账户 ID
        days: 天数（默认 30）

    返回:
        [
            {'date': '2026-02-01', 'value': 10000.00, 'cost': 9500.00},
            {'date': '2026-02-02', 'value': 10200.00, 'cost': 9500.00},
            ...
        ]
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # 1. 获取所有操作流水（包括查询范围之前的操作）
    operations = (
        PositionOperation.objects.filter(
            account_id=account_id, operation_date__lte=end_date
        )
        .select_related("fund")
        .order_by("operation_date")
    )

    if not operations.exists():
        return []

    # 2. 回放流水，计算每日持仓
    daily_positions = _replay_operations(operations, start_date, end_date)

    # 3. 获取所有基金 ID
    fund_ids = set(daily_positions.keys())

    # 4. 查询每日净值
    daily_nav = _get_daily_nav(fund_ids, start_date, end_date)

    # 5. 计算每日市值
    result = _calculate_daily_value(daily_positions, daily_nav, start_date, end_date)

    return result


def _replay_operations(operations, start_date, end_date):
    """
    回放流水，计算每日持仓

    返回: {
        fund_id: {
            date(2026, 2, 1): {'share': Decimal('100'), 'cost': Decimal('1000')},
            date(2026, 2, 2): {'share': Decimal('150'), 'cost': Decimal('1500')},
        }
    }
    """
    # 当前持仓状态 {fund_id: {'share': Decimal, 'cost': Decimal}}
    current_positions = {}

    # 每日持仓快照 {fund_id: {date: {'share': Decimal, 'cost': Decimal}}}
    daily_positions = {}

    # 回放所有操作
    for op in operations:
        fund_id = str(op.fund_id)

        # 初始化基金持仓
        if fund_id not in current_positions:
            current_positions[fund_id] = {"share": Decimal("0"), "cost": Decimal("0")}

        # 更新持仓
        if op.operation_type == "BUY":
            # 买入：增加份额和成本
            current_positions[fund_id]["share"] += op.share
            current_positions[fund_id]["cost"] += op.amount
        else:  # SELL
            # 卖出：按每份成本计算，与 Position 汇总逻辑一致
            if current_positions[fund_id]["share"] > 0:
                # 计算每份成本
                cost_per_share = (
                    current_positions[fund_id]["cost"]
                    / current_positions[fund_id]["share"]
                )
                # 减少份额
                current_positions[fund_id]["share"] -= op.share
                # 减少成本（卖出份额 × 每份成本）
                current_positions[fund_id]["cost"] -= op.share * cost_per_share
            else:
                # 如果没有持仓，只减少份额（可能出现负数）
                current_positions[fund_id]["share"] -= op.share

        # 记录当日持仓（只记录操作日期的持仓）
        if fund_id not in daily_positions:
            daily_positions[fund_id] = {}

        daily_positions[fund_id][op.operation_date] = {
            "share": current_positions[fund_id]["share"],
            "cost": current_positions[fund_id]["cost"],
        }

    # 填充日期：为每个基金填充查询范围内的所有日期
    return _fill_dates(daily_positions, start_date, end_date)


def _fill_dates(daily_positions, start_date, end_date):
    """
    填充日期：为每个基金填充查询范围内的所有日期

    逻辑：
    - 如果某日有操作，使用操作后的持仓
    - 如果某日无操作，使用最近一次操作后的持仓
    - 如果该日之前没有任何操作，持仓为 0
    """
    filled_positions = {}

    for fund_id, positions in daily_positions.items():
        filled_positions[fund_id] = {}

        # 获取所有操作日期（排序）
        operation_dates = sorted(positions.keys())

        # 遍历查询范围内的每一天
        current_date = start_date
        while current_date <= end_date:
            # 找到当日或之前最近的一次操作
            latest_position = None
            for op_date in operation_dates:
                if op_date <= current_date:
                    latest_position = positions[op_date]
                else:
                    break

            # 如果找到了操作，使用该持仓；否则持仓为 0
            if latest_position:
                filled_positions[fund_id][current_date] = latest_position
            else:
                filled_positions[fund_id][current_date] = {
                    "share": Decimal("0"),
                    "cost": Decimal("0"),
                }

            current_date += timedelta(days=1)

    return filled_positions


def _get_daily_nav(fund_ids: Set[str], start_date, end_date):
    """
    查询每日净值

    返回: {
        fund_id: {
            date(2026, 2, 1): Decimal('1.2345'),
            date(2026, 2, 2): Decimal('1.2400'),
        }
    }
    """
    # 查询历史净值
    nav_records = FundNavHistory.objects.filter(
        fund_id__in=fund_ids, nav_date__gte=start_date, nav_date__lte=end_date
    ).select_related("fund")

    # 组织成字典
    daily_nav = {}
    for record in nav_records:
        fund_id = str(record.fund_id)
        if fund_id not in daily_nav:
            daily_nav[fund_id] = {}
        daily_nav[fund_id][record.nav_date] = record.unit_nav

    # 查询 Fund.latest_nav 作为 fallback
    funds = Fund.objects.filter(id__in=fund_ids)
    fund_latest_nav = {str(f.id): f.latest_nav for f in funds if f.latest_nav}

    # 填充缺失的净值（使用 latest_nav）
    for fund_id in fund_ids:
        if fund_id not in daily_nav:
            daily_nav[fund_id] = {}

        # 为每个日期填充净值（如果缺失，使用 latest_nav）
        if fund_id in fund_latest_nav:
            current_date = start_date
            while current_date <= end_date:
                # 如果当日没有历史净值，使用 latest_nav
                if current_date not in daily_nav[fund_id]:
                    daily_nav[fund_id][current_date] = fund_latest_nav[fund_id]
                current_date += timedelta(days=1)

    return daily_nav


def _calculate_daily_value(daily_positions, daily_nav, start_date, end_date):
    """
    计算每日市值

    返回: [
        {'date': '2026-02-01', 'value': 10000.00, 'cost': 9500.00},
        {'date': '2026-02-02', 'value': 10200.00, 'cost': 9500.00},
    ]
    """
    result = []
    current_date = start_date

    while current_date <= end_date:
        total_value = Decimal("0")
        total_cost = Decimal("0")

        # 遍历所有基金
        for fund_id, positions in daily_positions.items():
            # 获取当日持仓
            position = positions.get(current_date)
            if not position or position["share"] == 0:
                continue

            # 成本始终计入
            total_cost += position["cost"]

            # 获取当日净值
            nav = daily_nav.get(fund_id, {}).get(current_date)
            if nav:
                # 如果有净值，计算市值
                total_value += position["share"] * nav
            else:
                # 如果没有净值，使用持仓净值估算市值
                # 持仓净值 = 成本 / 份额
                if position["share"] > 0:
                    holding_nav = position["cost"] / position["share"]
                    total_value += position["share"] * holding_nav

        # 添加到结果
        result.append(
            {
                "date": current_date.isoformat(),
                "value": float(total_value),
                "cost": float(total_cost),
            }
        )

        current_date += timedelta(days=1)

    return result
