"""
养基宝账户数据导入服务

逻辑：
1. 获取养基宝账户列表
2. 在本地创建父账户（养基宝）+ 子账户（各券商/平台）
3. 获取每个账户的持仓
4. 创建 Fund + PositionOperation
   - overwrite=False：同账户+基金+日期已存在则跳过
   - overwrite=True：清空该账户所有持仓流水后重新导入
"""
from decimal import Decimal, ROUND_DOWN
from django.db import transaction

from ..models import Account, Fund, PositionOperation


PARENT_ACCOUNT_NAME = '养基宝'


def import_from_yangjibao(user, source, overwrite: bool = False) -> dict:
    """
    从养基宝导入账户和持仓数据

    Args:
        user: Django User 对象
        source: YangJiBaoSource 实例（已登录）
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
        # 1. 确保父账户存在
        parent_account, _ = Account.objects.get_or_create(
            user=user,
            name=PARENT_ACCOUNT_NAME,
            defaults={'parent': None, 'is_default': False},
        )

        # 2. 获取养基宝账户列表
        yjb_accounts = source.fetch_accounts()

        for yjb_account in yjb_accounts:
            account_id = yjb_account['account_id']
            account_name = yjb_account['name']

            # 3. 创建/获取子账户
            sub_account, created = Account.objects.get_or_create(
                user=user,
                name=account_name,
                defaults={'parent': parent_account, 'is_default': False},
            )

            if created:
                result['accounts_created'] += 1
            else:
                result['accounts_skipped'] += 1

            # 4. overwrite 模式：清空该子账户所有持仓流水
            if overwrite:
                PositionOperation.objects.filter(account=sub_account).delete()

            # 5. 获取该账户的持仓
            holdings = source.fetch_holdings(account_id)

            for holding in holdings:
                fund_code = holding.get('fund_code', '').strip()
                if not fund_code:
                    result['holdings_skipped'] += 1
                    continue

                # 6. 创建/获取基金
                fund, _ = Fund.objects.get_or_create(
                    fund_code=fund_code,
                    defaults={'fund_name': holding.get('fund_name', fund_code)},
                )

                # 7. 幂等（非 overwrite 模式）：同账户+基金+日期已存在则跳过
                op_date = holding['operation_date']
                if not overwrite:
                    exists = PositionOperation.objects.filter(
                        account=sub_account,
                        fund=fund,
                        operation_date=op_date,
                        operation_type='BUY',
                    ).exists()
                    if exists:
                        result['holdings_skipped'] += 1
                        continue

                # 8. nav/share/amount 截断到合法精度
                nav = Decimal(str(holding['nav'])).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
                share = Decimal(str(holding['share'])).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
                amount = Decimal(str(holding['amount'])).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

                PositionOperation.objects.create(
                    account=sub_account,
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
