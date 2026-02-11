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
        """保存前验证"""
        self.full_clean()
        super().save(*args, **kwargs)


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

