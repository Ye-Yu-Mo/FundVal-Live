"""
小倍养基持仓导入服务

逻辑：
1. 调用 source.fetch_holdings() 获取扁平持仓列表
2. 确保父账户（小倍养基）存在
3. 所有持仓写入同一个账户
4. 创建 Fund + PositionOperation
   - overwrite=False：同账户+基金+日期已存在则跳过
   - overwrite=True：清空该账户所有持仓流水后重新导入
"""
from decimal import Decimal, ROUND_DOWN
from django.db import transaction

from ..models import Account, Fund, PositionOperation


PARENT_ACCOUNT_NAME = '小倍养基'


def import_from_xiaobeiyangji(user, source, overwrite: bool = False) -> dict:
    """
    从小倍养基导入持仓数据

    Args:
        user: Django User 对象
        source: XiaoBeiYangJiSource 实例（已登录）
        overwrite: True = 清空已有持仓流水后重新导入；False = 跳过已有记录

    Returns:
        dict: {
            'accounts_created': int,
            'accounts_skipped': int,
            'holdings_created': int,
            'holdings_skipped': int,
        }
    """
    result = {
        'accounts_created': 0,
        'accounts_skipped': 0,
        'holdings_created': 0,
        'holdings_skipped': 0,
    }

    with transaction.atomic():
        # 1. 确保账户存在
        account, created = Account.objects.get_or_create(
            user=user,
            name=PARENT_ACCOUNT_NAME,
            defaults={'parent': None, 'is_default': False},
        )
        if created:
            result['accounts_created'] += 1
        else:
            result['accounts_skipped'] += 1

        # 2. overwrite 模式：清空持仓流水
        if overwrite:
            PositionOperation.objects.filter(account=account).delete()

        # 3. 获取持仓
        holdings = source.fetch_holdings()

        for holding in holdings:
            fund_code = holding.get('fund_code', '').strip()
            if not fund_code:
                result['holdings_skipped'] += 1
                continue

            # 4. 创建/获取基金
            fund, _ = Fund.objects.get_or_create(
                fund_code=fund_code,
                defaults={'fund_name': holding.get('fund_name', fund_code)},
            )

            # 5. 幂等（非 overwrite 模式）
            op_date = holding['operation_date']
            if not overwrite:
                exists = PositionOperation.objects.filter(
                    account=account,
                    fund=fund,
                    operation_date=op_date,
                    operation_type='BUY',
                ).exists()
                if exists:
                    result['holdings_skipped'] += 1
                    continue

            # 6. 精度截断
            nav = Decimal(str(holding['nav'])).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            share = Decimal(str(holding['share'])).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
            amount = Decimal(str(holding['amount'])).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

            PositionOperation.objects.create(
                account=account,
                fund=fund,
                operation_type='BUY',
                operation_date=op_date,
                before_15=True,
                share=share,
                nav=nav,
                amount=amount,
            )
            result['holdings_created'] += 1

    return result
