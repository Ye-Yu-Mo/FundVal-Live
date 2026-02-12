from django.contrib import admin
from .models import Fund, Account, Position, PositionOperation, Watchlist, WatchlistItem


@admin.register(Fund)
class FundAdmin(admin.ModelAdmin):
    list_display = ['fund_code', 'fund_name', 'fund_type', 'latest_nav', 'latest_nav_date']
    search_fields = ['fund_code', 'fund_name']
    list_filter = ['fund_type']


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'parent', 'is_default', 'created_at']
    list_filter = ['is_default']
    search_fields = ['name', 'user__username']


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    """Position 只读 Admin"""
    list_display = ['account', 'fund', 'holding_share', 'holding_cost', 'holding_nav', 'updated_at']
    readonly_fields = ['account', 'fund', 'holding_share', 'holding_cost', 'holding_nav', 'updated_at']
    search_fields = ['account__name', 'fund__fund_name', 'fund__fund_code']

    def has_add_permission(self, request):
        """禁止添加"""
        return False

    def has_change_permission(self, request, obj=None):
        """禁止修改"""
        return False

    def has_delete_permission(self, request, obj=None):
        """禁止删除"""
        return False


@admin.register(PositionOperation)
class PositionOperationAdmin(admin.ModelAdmin):
    list_display = ['account', 'fund', 'operation_type', 'operation_date', 'amount', 'share', 'nav', 'created_at']
    list_filter = ['operation_type', 'before_15']
    search_fields = ['account__name', 'fund__fund_name', 'fund__fund_code']
    date_hierarchy = 'operation_date'


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'created_at']
    search_fields = ['name', 'user__username']


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ['watchlist', 'fund', 'order', 'created_at']
    list_filter = ['watchlist']
    search_fields = ['fund__fund_name', 'fund__fund_code']
