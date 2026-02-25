import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Fund(models.Model):
    """基金模型"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fund_code = models.CharField(max_length=10, unique=True, db_index=True)
    fund_name = models.CharField(max_length=100)
    fund_type = models.CharField(max_length=50, null=True, blank=True)

    # 净值数据（由数据源更新）
    latest_nav = models.DecimalField(
        max_digits=10, decimal_places=4,
        null=True, blank=True,
        help_text='最新净值'
    )
    latest_nav_date = models.DateField(
        null=True, blank=True,
        help_text='最新净值日期'
    )

    # 实时估值数据（缓存）
    estimate_nav = models.DecimalField(
        max_digits=10, decimal_places=4,
        null=True, blank=True,
        help_text='实时估值净值'
    )
    estimate_growth = models.DecimalField(
        max_digits=10, decimal_places=4,
        null=True, blank=True,
        help_text='估值涨跌幅（%）'
    )
    estimate_time = models.DateTimeField(
        null=True, blank=True,
        help_text='估值更新时间'
    )

    # 元数据
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fund'
        verbose_name = '基金'
        verbose_name_plural = '基金'

    def __str__(self):
        return f'{self.fund_code} - {self.fund_name}'


class Account(models.Model):
    """账户模型"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'account'
        verbose_name = '账户'
        verbose_name_plural = '账户'
        unique_together = [['user', 'name']]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(is_default=False) | models.Q(parent__isnull=True),
                name='default_account_must_be_parent',
                violation_error_message='默认账户必须是父账户'
            ),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.name}'

    def clean(self):
        """模型验证"""
        from django.core.exceptions import ValidationError

        # 验证：默认账户必须是父账户
        if self.is_default and self.parent is not None:
            raise ValidationError('默认账户必须是父账户（parent 必须为 NULL）')

        # 验证：每个用户只能有一个默认账户
        if self.is_default:
            existing_default = Account.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(id=self.id).first()

            if existing_default:
                raise ValidationError(f'用户 {self.user.username} 已有默认账户：{existing_default.name}')

        # 验证：最多两层（父账户 -> 子账户）
        if self.parent is not None and self.parent.parent is not None:
            raise ValidationError('账户层级最多两层：父账户 -> 子账户，不支持孙账户')

    def save(self, *args, **kwargs):
        """保存前自动处理默认账户切换"""
        # 如果设置为默认账户，自动取消同用户的其他默认账户
        if self.is_default:
            Account.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)

        # 调用 clean 进行验证
        self.full_clean()
        super().save(*args, **kwargs)

    # 汇总字段（@property）
    @property
    def holding_cost(self):
        """持仓成本"""
        from decimal import Decimal
        if self.parent is None:
            # 父账户：汇总所有子账户
            return sum(
                (child.holding_cost for child in self.children.all()),
                Decimal('0')
            )
        else:
            # 子账户：汇总所有持仓
            return sum(
                (pos.holding_cost for pos in self.positions.all()),
                Decimal('0')
            )

    @property
    def holding_value(self):
        """持仓市值（latest_nav）"""
        from decimal import Decimal
        if self.parent is None:
            # 父账户：汇总所有子账户
            return sum(
                (child.holding_value for child in self.children.all()),
                Decimal('0')
            )
        else:
            # 子账户：汇总所有持仓
            return sum(
                (pos.fund.latest_nav * pos.holding_share
                 for pos in self.positions.all() if pos.fund.latest_nav),
                Decimal('0')
            )

    @property
    def pnl(self):
        """总盈亏"""
        from decimal import Decimal
        return self.holding_value - self.holding_cost

    @property
    def pnl_rate(self):
        """收益率"""
        from decimal import Decimal
        if self.holding_cost == 0:
            return None
        return (self.pnl / self.holding_cost).quantize(Decimal('0.0001'))

    @property
    def estimate_value(self):
        """预估市值"""
        from decimal import Decimal
        if self.parent is None:
            # 父账户：汇总所有子账户
            values = [child.estimate_value for child in self.children.all()]
            if None in values:
                return None
            return sum(values, Decimal('0'))
        else:
            # 子账户：汇总所有持仓
            total = Decimal('0')
            for pos in self.positions.all():
                if pos.fund.estimate_nav is None:
                    return None  # 任一持仓缺失估值，返回 None
                total += pos.fund.estimate_nav * pos.holding_share
            return total if self.positions.exists() else Decimal('0')

    @property
    def estimate_pnl(self):
        """预估盈亏"""
        from decimal import Decimal
        if self.estimate_value is None:
            return None
        return self.estimate_value - self.holding_cost

    @property
    def estimate_pnl_rate(self):
        """预估收益率"""
        from decimal import Decimal
        if self.estimate_pnl is None or self.holding_cost == 0:
            return None
        return (self.estimate_pnl / self.holding_cost).quantize(Decimal('0.0001'))

    @property
    def today_pnl(self):
        """今日盈亏"""
        from decimal import Decimal
        if self.parent is None:
            # 父账户：汇总所有子账户
            values = [child.today_pnl for child in self.children.all()]
            if None in values:
                return None
            return sum(values, Decimal('0'))
        else:
            # 子账户：汇总所有持仓
            total = Decimal('0')
            for pos in self.positions.all():
                if pos.fund.estimate_nav is None or pos.fund.latest_nav is None:
                    return None  # 任一持仓缺失估值，返回 None
                total += pos.holding_share * (pos.fund.estimate_nav - pos.fund.latest_nav)
            return total if self.positions.exists() else Decimal('0')

    @property
    def today_pnl_rate(self):
        """今日收益率"""
        from decimal import Decimal
        if self.today_pnl is None or self.holding_value == 0:
            return None
        return (self.today_pnl / self.holding_value).quantize(Decimal('0.0001'))


class Position(models.Model):
    """持仓汇总模型（只读，由流水计算）"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='positions')
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name='positions')

    # 汇总数据（只读，由流水计算）
    holding_share = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    holding_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    holding_nav = models.DecimalField(max_digits=10, decimal_places=4, default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'position'
        verbose_name = '持仓'
        verbose_name_plural = '持仓'
        unique_together = [['account', 'fund']]

    def __str__(self):
        return f'{self.account.name} - {self.fund.fund_name}'

    def clean(self):
        """模型验证"""
        from django.core.exceptions import ValidationError

        # 验证：持仓账户必须是子账户（parent 不能为 NULL）
        if self.account.parent is None:
            raise ValidationError('持仓只能创建在子账户上，父账户不能持有持仓')

    def save(self, *args, **kwargs):
        """保存前验证"""
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def pnl(self):
        """盈亏（实时计算）"""
        if not self.fund.latest_nav or self.holding_share == 0:
            return 0
        return (self.fund.latest_nav - self.holding_nav) * self.holding_share


class PositionOperation(models.Model):
    """持仓操作流水"""

    OPERATION_TYPE_CHOICES = [
        ('BUY', '建仓/加仓'),
        ('SELL', '减仓'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='operations')
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name='operations')

    operation_type = models.CharField(max_length=10, choices=OPERATION_TYPE_CHOICES)
    operation_date = models.DateField()
    before_15 = models.BooleanField(default=True, help_text='是否 15:00 前操作')

    amount = models.DecimalField(max_digits=20, decimal_places=2)
    share = models.DecimalField(max_digits=20, decimal_places=4)
    nav = models.DecimalField(max_digits=10, decimal_places=4, help_text='操作时的净值')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'position_operation'
        verbose_name = '持仓操作'
        verbose_name_plural = '持仓操作'
        ordering = ['operation_date', 'created_at']

    def __str__(self):
        return f'{self.get_operation_type_display()} - {self.fund.fund_name} - {self.operation_date}'

    def clean(self):
        """模型验证"""
        from django.core.exceptions import ValidationError

        # 验证：操作账户必须是子账户（parent 不能为 NULL）
        if self.account.parent is None:
            raise ValidationError('持仓操作只能在子账户上进行，父账户不能进行持仓操作')

    def save(self, *args, **kwargs):
        """保存前验证，新建操作时自动重算持仓"""
        self.full_clean()
        is_new = self._state.adding
        super().save(*args, **kwargs)

        # 新建操作后自动重算持仓
        if is_new:
            from .services import recalculate_position
            recalculate_position(self.account.id, self.fund.id)


class Watchlist(models.Model):
    """自选列表"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watchlists')
    name = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'watchlist'
        verbose_name = '自选列表'
        verbose_name_plural = '自选列表'
        unique_together = [['user', 'name']]

    def __str__(self):
        return f'{self.user.username} - {self.name}'


class WatchlistItem(models.Model):
    """自选列表项"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    watchlist = models.ForeignKey(Watchlist, on_delete=models.CASCADE, related_name='items')
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name='watchlist_items')
    order = models.IntegerField(default=0, help_text='排序')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'watchlist_item'
        verbose_name = '自选项'
        verbose_name_plural = '自选项'
        unique_together = [['watchlist', 'fund']]
        ordering = ['order']

    def __str__(self):
        return f'{self.watchlist.name} - {self.fund.fund_name}'


class EstimateAccuracy(models.Model):
    """估值准确率记录"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_name = models.CharField(max_length=50, db_index=True)
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name='accuracy_records')

    estimate_date = models.DateField()
    estimate_nav = models.DecimalField(max_digits=10, decimal_places=4)
    actual_nav = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    error_rate = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True, help_text='误差率')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'estimate_accuracy'
        verbose_name = '估值准确率'
        verbose_name_plural = '估值准确率'
        unique_together = [['source_name', 'fund', 'estimate_date']]
        indexes = [
            models.Index(fields=['fund', 'estimate_date']),
            models.Index(fields=['source_name', 'estimate_date']),
        ]

    def __str__(self):
        return f'{self.source_name} - {self.fund.fund_code} - {self.estimate_date}'

    def calculate_error_rate(self):
        """计算误差率"""
        if self.actual_nav and self.actual_nav > 0:
            error = abs(self.estimate_nav - self.actual_nav)
            self.error_rate = error / self.actual_nav
            self.save()


class FundNavHistory(models.Model):
    """基金历史净值"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name='nav_history')

    # 净值数据
    nav_date = models.DateField(help_text='净值日期')
    unit_nav = models.DecimalField(
        max_digits=10, decimal_places=4,
        help_text='单位净值'
    )
    accumulated_nav = models.DecimalField(
        max_digits=10, decimal_places=4,
        null=True, blank=True,
        help_text='累计净值'
    )
    daily_growth = models.DecimalField(
        max_digits=10, decimal_places=4,
        null=True, blank=True,
        help_text='日增长率（%）'
    )

    # 元数据
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fund_nav_history'
        verbose_name = '基金历史净值'
        verbose_name_plural = '基金历史净值'
        unique_together = [['fund', 'nav_date']]
        ordering = ['-nav_date']
        indexes = [
            models.Index(fields=['fund', '-nav_date']),
            models.Index(fields=['nav_date']),
        ]

    def __str__(self):
        return f'{self.fund.fund_code} - {self.nav_date}'


class UserSourceCredential(models.Model):
    """用户数据源凭证"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='source_credentials')
    source_name = models.CharField(max_length=50, help_text='数据源名称（如 yangjibao）')
    token = models.TextField(help_text='加密存储的 token')
    is_active = models.BooleanField(default=True, help_text='是否激活')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_source_credential'
        verbose_name = '用户数据源凭证'
        verbose_name_plural = '用户数据源凭证'
        unique_together = [['user', 'source_name']]
        indexes = [
            models.Index(fields=['user', 'source_name', 'is_active']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.source_name}'


class UserPreference(models.Model):
    """用户偏好设置"""

    SOURCE_CHOICES = [
        ('eastmoney', '东方财富'),
        ('yangjibao', '养基宝'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preference')
    preferred_source = models.CharField(
        max_length=50,
        choices=SOURCE_CHOICES,
        default='eastmoney',
    )

    class Meta:
        db_table = 'user_preference'
        verbose_name = '用户偏好'
        verbose_name_plural = '用户偏好'

    def __str__(self):
        return f'{self.user.username} - {self.preferred_source}'


# Signal handlers
from django.db.models.signals import post_delete
from django.dispatch import receiver


@receiver(post_delete, sender=PositionOperation)
def recalculate_position_on_delete(sender, instance, **kwargs):
    """删除操作后自动重算持仓"""
    from .services import recalculate_position
    recalculate_position(instance.account.id, instance.fund.id)
