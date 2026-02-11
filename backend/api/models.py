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
    yesterday_nav = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    yesterday_date = models.DateField(null=True, blank=True)

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

    def __str__(self):
        return f'{self.user.username} - {self.name}'


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

    @property
    def pnl(self):
        """盈亏（实时计算）"""
        if not self.fund.yesterday_nav or self.holding_share == 0:
            return 0
        return (self.fund.yesterday_nav - self.holding_nav) * self.holding_share


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

