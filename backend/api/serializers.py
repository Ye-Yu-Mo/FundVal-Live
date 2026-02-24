"""
序列化器

用于 API 数据的序列化和反序列化
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from datetime import date
from .models import (
    Fund, Account, Position, PositionOperation,
    Watchlist, WatchlistItem, EstimateAccuracy, FundNavHistory,
    UserSourceCredential
)

User = get_user_model()


class FundSerializer(serializers.ModelSerializer):
    """基金序列化器"""

    class Meta:
        model = Fund
        fields = [
            'id', 'fund_code', 'fund_name', 'fund_type',
            'latest_nav', 'latest_nav_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AccountSerializer(serializers.ModelSerializer):
    """账户序列化器"""

    parent = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True
    )

    # 汇总字段
    holding_cost = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    holding_value = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    pnl = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    pnl_rate = serializers.DecimalField(max_digits=10, decimal_places=4, read_only=True, allow_null=True)
    estimate_value = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True, allow_null=True)
    estimate_pnl = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True, allow_null=True)
    estimate_pnl_rate = serializers.DecimalField(max_digits=10, decimal_places=4, read_only=True, allow_null=True)
    today_pnl = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True, allow_null=True)
    today_pnl_rate = serializers.DecimalField(max_digits=10, decimal_places=4, read_only=True, allow_null=True)

    # 父账户专用：子账户列表
    children = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            'id', 'name', 'parent', 'is_default',
            'holding_cost', 'holding_value', 'pnl', 'pnl_rate',
            'estimate_value', 'estimate_pnl', 'estimate_pnl_rate',
            'today_pnl', 'today_pnl_rate',
            'children',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_children(self, obj):
        """获取子账户列表（仅父账户）"""
        if obj.parent is not None:
            return None
        children = obj.children.all()
        return AccountSerializer(children, many=True, context=self.context).data

    def to_representation(self, instance):
        """序列化时将 UUID 转为字符串，移除子账户的 children 字段"""
        data = super().to_representation(instance)
        if data.get('parent'):
            data['parent'] = str(data['parent'])

        # 子账户不返回 children 字段
        if instance.parent is not None:
            data.pop('children', None)

        return data

    def validate(self, data):
        """验证账户名唯一性"""
        user = self.context['request'].user
        name = data.get('name')

        # 更新时排除自己
        if self.instance:
            if Account.objects.filter(user=user, name=name).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError({'name': '账户名已存在'})
        else:
            if Account.objects.filter(user=user, name=name).exists():
                raise serializers.ValidationError({'name': '账户名已存在'})

        return data


class PositionSerializer(serializers.ModelSerializer):
    """持仓序列化器"""

    fund_code = serializers.CharField(source='fund.fund_code', read_only=True)
    fund_name = serializers.CharField(source='fund.fund_name', read_only=True)
    fund_type = serializers.CharField(source='fund.fund_type', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    pnl = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    # 添加基金的估值和净值信息
    fund = serializers.SerializerMethodField()

    def get_fund(self, obj):
        """返回基金的详细信息"""
        return {
            'fund_code': obj.fund.fund_code,
            'fund_name': obj.fund.fund_name,
            'fund_type': obj.fund.fund_type,
            'latest_nav': str(obj.fund.latest_nav) if obj.fund.latest_nav else None,
            'latest_nav_date': obj.fund.latest_nav_date.isoformat() if obj.fund.latest_nav_date else None,
            'estimate_nav': str(obj.fund.estimate_nav) if obj.fund.estimate_nav else None,
            'estimate_growth': str(obj.fund.estimate_growth) if obj.fund.estimate_growth else None,
            'estimate_time': obj.fund.estimate_time.isoformat() if obj.fund.estimate_time else None,
        }

    class Meta:
        model = Position
        fields = [
            'id', 'account', 'account_name', 'fund', 'fund_code', 'fund_name', 'fund_type',
            'holding_share', 'holding_cost', 'holding_nav', 'pnl',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'holding_share', 'holding_cost', 'holding_nav', 'updated_at'
        ]


class PositionOperationSerializer(serializers.ModelSerializer):
    """持仓操作序列化器"""

    fund_code = serializers.CharField(write_only=True)
    fund_name = serializers.CharField(source='fund.fund_name', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = PositionOperation
        fields = [
            'id', 'account', 'account_name', 'fund', 'fund_code', 'fund_name',
            'operation_type', 'operation_date', 'before_15',
            'amount', 'share', 'nav',
            'created_at'
        ]
        read_only_fields = ['id', 'fund', 'created_at']

    def validate(self, data):
        """验证并设置 fund"""
        fund_code = data.pop('fund_code', None)
        if not fund_code:
            raise serializers.ValidationError({'fund_code': '基金代码不能为空'})

        try:
            fund = Fund.objects.get(fund_code=fund_code)
            data['fund'] = fund
        except Fund.DoesNotExist:
            raise serializers.ValidationError({'fund_code': '基金不存在'})

        return data

    def create(self, validated_data):
        """创建操作并自动重算持仓"""
        from .services import recalculate_position

        operation = super().create(validated_data)

        # 自动重算持仓
        recalculate_position(operation.account.id, operation.fund.id)

        return operation


class WatchlistItemSerializer(serializers.ModelSerializer):
    """自选列表项序列化器"""

    fund_code = serializers.CharField(source='fund.fund_code', read_only=True)
    fund_name = serializers.CharField(source='fund.fund_name', read_only=True)
    fund_type = serializers.CharField(source='fund.fund_type', read_only=True)

    class Meta:
        model = WatchlistItem
        fields = ['id', 'fund', 'fund_code', 'fund_name', 'fund_type', 'order', 'created_at']
        read_only_fields = ['id', 'created_at']


class WatchlistSerializer(serializers.ModelSerializer):
    """自选列表序列化器"""

    items = WatchlistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Watchlist
        fields = ['id', 'name', 'items', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate(self, data):
        """验证自选列表名唯一性"""
        user = self.context['request'].user
        name = data.get('name')

        if self.instance:
            if Watchlist.objects.filter(user=user, name=name).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError({'name': '自选列表名已存在'})
        else:
            if Watchlist.objects.filter(user=user, name=name).exists():
                raise serializers.ValidationError({'name': '自选列表名已存在'})

        return data


class UserRegisterSerializer(serializers.Serializer):
    """用户注册序列化器"""

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate_username(self, value):
        """验证用户名唯一性"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('用户名已存在')
        return value

    def validate(self, data):
        """验证密码一致性"""
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': '两次密码不一致'})
        return data

    def create(self, validated_data):
        """创建用户"""
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class FundNavHistorySerializer(serializers.ModelSerializer):
    """基金历史净值序列化器"""

    fund_code = serializers.CharField(source='fund.fund_code', read_only=True)
    fund_name = serializers.CharField(source='fund.fund_name', read_only=True)

    class Meta:
        model = FundNavHistory
        fields = [
            'id',
            'fund_code',
            'fund_name',
            'nav_date',
            'unit_nav',
            'accumulated_nav',
            'daily_growth',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class QueryNavSerializer(serializers.Serializer):
    """查询持仓操作净值序列化器"""

    fund_code = serializers.CharField(max_length=10)
    operation_date = serializers.DateField()
    before_15 = serializers.BooleanField()

    def validate_operation_date(self, value):
        """验证操作日期不能是未来"""
        if value > date.today():
            raise serializers.ValidationError('操作日期不能是未来')
        return value


class UserSourceCredentialSerializer(serializers.ModelSerializer):
    """用户数据源凭证序列化器"""

    class Meta:
        model = UserSourceCredential
        fields = [
            'id',
            'source_name',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class QRCodeLoginSerializer(serializers.Serializer):
    """二维码登录请求序列化器"""

    source_name = serializers.CharField(max_length=50)

    def validate_source_name(self, value):
        """验证数据源是否存在"""
        from .sources import SourceRegistry

        source = SourceRegistry.get_source(value)
        if not source:
            raise serializers.ValidationError(f'数据源 {value} 不存在')

        return value
