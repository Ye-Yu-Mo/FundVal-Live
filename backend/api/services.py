"""
持仓计算服务

核心逻辑：
- Position 是汇总表，只读
- 所有计算基于 PositionOperation 流水
- 支持回溯重算
"""
from decimal import Decimal
from typing import Optional
from django.db import transaction

from .models import Position, PositionOperation


def recalculate_position(account_id, fund_id) -> Position:
    """
    重新计算持仓汇总

    Args:
        account_id: 账户 ID
        fund_id: 基金 ID

    Returns:
        Position: 更新后的持仓对象
    """
    from .models import Account, Fund

    # 获取账户和基金对象（用于 Position 验证）
    account = Account.objects.get(id=account_id)
    fund = Fund.objects.get(id=fund_id)

    # 获取所有流水（按时间排序）
    operations = PositionOperation.objects.filter(
        account_id=account_id,
        fund_id=fund_id
    ).order_by('operation_date', 'created_at')

    total_share = Decimal('0')
    total_cost = Decimal('0')

    for op in operations:
        if op.operation_type == 'BUY':
            # 买入：增加份额和成本
            total_share += op.share
            total_cost += op.amount
        elif op.operation_type == 'SELL':
            # 卖出：按比例减少成本
            if total_share > 0:
                cost_per_share = total_cost / total_share
                total_share -= op.share
                total_cost -= op.share * cost_per_share
                # 四舍五入到 2 位小数
                total_cost = total_cost.quantize(Decimal('0.01'))

    # 计算持仓净值（加权平均）
    if total_share > 0:
        holding_nav = total_cost / total_share
        # 四舍五入到 4 位小数
        holding_nav = holding_nav.quantize(Decimal('0.0001'))
    else:
        holding_nav = Decimal('0')

    # 更新或创建 Position（使用对象而不是 ID）
    with transaction.atomic():
        position, created = Position.objects.update_or_create(
            account=account,
            fund=fund,
            defaults={
                'holding_share': total_share,
                'holding_cost': total_cost,
                'holding_nav': holding_nav,
            }
        )

    return position


def recalculate_all_positions(account_id: Optional[str] = None):
    """
    重算所有持仓

    Args:
        account_id: 可选，只重算指定账户的持仓
    """
    if account_id:
        operations = PositionOperation.objects.filter(account_id=account_id)
    else:
        operations = PositionOperation.objects.all()

    # 获取所有需要重算的 (account_id, fund_id) 组合
    account_fund_pairs = operations.values_list('account_id', 'fund_id').distinct()

    for account_id, fund_id in account_fund_pairs:
        recalculate_position(account_id, fund_id)
