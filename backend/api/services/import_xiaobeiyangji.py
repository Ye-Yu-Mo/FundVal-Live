"""
小倍养基持仓导入服务

逻辑：
1. 获取账户列表，建立 accountId → 账户名映射
2. 确保父账户（小倍养基）存在
3. 按 accountId 分组，每个账户创建对应子账户
   - accountId=None 或 0 → 子账户名「默认账户」
4. 创建 Fund + PositionOperation
   - overwrite=False：同账户+基金+日期已存在则跳过
   - overwrite=True：清空该账户所有持仓流水后重新导入
"""
from decimal import Decimal, ROUND_DOWN
from django.db import transaction

from ..models import Account, Fund, PositionOperation


PARENT_ACCOUNT_NAME = '小倍养基'
DEFAULT_SUB_ACCOUNT_NAME = '默认账户'


def import_from_xiaobeiyangji(user, source, overwrite: bool = False) -> dict:
    result = {
        'accounts_created': 0,
        'accounts_skipped': 0,
        'holdings_created': 0,
        'holdings_skipped': 0,
    }

    with transaction.atomic():
        # 1. 父账户
        parent_account, parent_created = Account.objects.get_or_create(
            user=user,
            name=PARENT_ACCOUNT_NAME,
            defaults={'parent': None, 'is_default': False},
        )
        if parent_created:
            result['accounts_created'] += 1
        else:
            result['accounts_skipped'] += 1

        # 2. 账户列表：建立 accountId → 名称映射
        raw_accounts = source.fetch_accounts()
        account_id_to_name = {
            str(a['accountId']): a['name']
            for a in raw_accounts
            if a.get('accountId') not in (None, 0, '0')
        }

        # 3. 获取持仓
        holdings = source.fetch_holdings()
        if not holdings:
            return result

        # 4. 按 account_id 分组
        groups: dict = {}
        for h in holdings:
            aid = h.get('account_id')
            key = str(aid) if aid not in (None, 0, '0') else None
            groups.setdefault(key, []).append(h)

        # 5. 逐组导入
        for aid_key, group_holdings in groups.items():
            sub_name = account_id_to_name.get(aid_key, DEFAULT_SUB_ACCOUNT_NAME) if aid_key else DEFAULT_SUB_ACCOUNT_NAME

            sub_account, sub_created = Account.objects.get_or_create(
                user=user,
                name=sub_name,
                defaults={'parent': parent_account, 'is_default': False},
            )
            if sub_created:
                result['accounts_created'] += 1
            else:
                result['accounts_skipped'] += 1

            if overwrite:
                PositionOperation.objects.filter(account=sub_account).delete()

            for holding in group_holdings:
                fund_code = holding.get('fund_code', '').strip()
                if not fund_code:
                    result['holdings_skipped'] += 1
                    continue

                fund, _ = Fund.objects.get_or_create(
                    fund_code=fund_code,
                    defaults={'fund_name': holding.get('fund_name', fund_code)},
                )

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
