"""
测试最近修改的 serializers.py

测试点：
1. PositionOperationSerializer.validate() - 验证并设置 fund
2. PositionOperationSerializer.create() - 创建操作并自动重算持仓
3. PositionSerializer.get_fund() - 返回基金详细信息（包含估值）
"""
import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from rest_framework import serializers as drf_serializers

from api.models import Fund, Account, Position, PositionOperation
from api.serializers import PositionOperationSerializer, PositionSerializer

User = get_user_model()


@pytest.mark.django_db
class TestPositionOperationSerializerValidate:
    """测试 PositionOperationSerializer.validate()"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user):
        parent = Account.objects.create(user=user, name='父账户')
        return Account.objects.create(user=user, name='子账户', parent=parent)

    @pytest.fixture
    def fund(self):
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.5000')
        )

    @pytest.fixture
    def request_context(self, user):
        """创建请求上下文"""
        factory = APIRequestFactory()
        request = factory.post('/api/operations/')
        request.user = user
        return {'request': request}

    def test_validate_with_valid_fund_code(self, account, fund, request_context):
        """测试：fund_code 有效时，自动设置 fund"""
        serializer = PositionOperationSerializer(context=request_context)

        data = {
            'account': account,
            'fund_code': '000001',
            'operation_type': 'BUY',
            'operation_date': date.today(),
            'before_15': True,
            'amount': Decimal('1000'),
            'share': Decimal('100'),
            'nav': Decimal('10'),
        }

        validated_data = serializer.validate(data)

        # 验证：fund_code 被移除，fund 被设置
        assert 'fund_code' not in validated_data
        assert 'fund' in validated_data
        assert validated_data['fund'] == fund

    def test_validate_with_missing_fund_code(self, account, request_context):
        """测试：fund_code 缺失时，抛出验证错误"""
        serializer = PositionOperationSerializer(context=request_context)

        data = {
            'account': account,
            'operation_type': 'BUY',
            'operation_date': date.today(),
            'before_15': True,
            'amount': Decimal('1000'),
            'share': Decimal('100'),
            'nav': Decimal('10'),
        }

        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            serializer.validate(data)

        assert 'fund_code' in exc_info.value.detail
        assert '基金代码不能为空' in str(exc_info.value.detail['fund_code'])

    def test_validate_with_nonexistent_fund_code(self, account, request_context):
        """测试：fund_code 不存在时，抛出验证错误"""
        serializer = PositionOperationSerializer(context=request_context)

        data = {
            'account': account,
            'fund_code': '999999',  # 不存在的基金代码
            'operation_type': 'BUY',
            'operation_date': date.today(),
            'before_15': True,
            'amount': Decimal('1000'),
            'share': Decimal('100'),
            'nav': Decimal('10'),
        }

        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            serializer.validate(data)

        assert 'fund_code' in exc_info.value.detail
        assert '基金不存在' in str(exc_info.value.detail['fund_code'])


@pytest.mark.django_db
class TestPositionOperationSerializerCreate:
    """测试 PositionOperationSerializer.create() - 自动重算持仓"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user):
        parent = Account.objects.create(user=user, name='父账户')
        return Account.objects.create(user=user, name='子账户', parent=parent)

    @pytest.fixture
    def fund(self):
        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            latest_nav=Decimal('1.5000')
        )

    @pytest.fixture
    def request_context(self, user):
        """创建请求上下文"""
        factory = APIRequestFactory()
        request = factory.post('/api/operations/')
        request.user = user
        return {'request': request}

    def test_create_operation_recalculates_position(self, account, fund, request_context):
        """测试：创建操作后自动重算持仓"""
        # 初始状态：无持仓
        assert Position.objects.filter(account=account, fund=fund).count() == 0

        # 创建操作
        serializer = PositionOperationSerializer(context=request_context)
        validated_data = {
            'account': account,
            'fund': fund,
            'operation_type': 'BUY',
            'operation_date': date.today(),
            'before_15': True,
            'amount': Decimal('1000'),
            'share': Decimal('100'),
            'nav': Decimal('10'),
        }

        operation = serializer.create(validated_data)

        # 验证：操作创建成功
        assert operation.id is not None
        assert operation.account == account
        assert operation.fund == fund

        # 验证：持仓自动创建并计算正确
        position = Position.objects.get(account=account, fund=fund)
        assert position.holding_share == Decimal('100')
        assert position.holding_cost == Decimal('1000')
        assert position.holding_nav == Decimal('10')

    def test_create_multiple_operations_recalculates_correctly(self, account, fund, request_context):
        """测试：多次操作后持仓计算正确"""
        serializer = PositionOperationSerializer(context=request_context)

        # 第一次建仓
        operation1 = serializer.create({
            'account': account,
            'fund': fund,
            'operation_type': 'BUY',
            'operation_date': date.today(),
            'before_15': True,
            'amount': Decimal('1000'),
            'share': Decimal('100'),
            'nav': Decimal('10'),
        })

        # 验证第一次持仓
        position = Position.objects.get(account=account, fund=fund)
        assert position.holding_share == Decimal('100')
        assert position.holding_cost == Decimal('1000')

        # 第二次加仓
        operation2 = serializer.create({
            'account': account,
            'fund': fund,
            'operation_type': 'BUY',
            'operation_date': date.today(),
            'before_15': True,
            'amount': Decimal('500'),
            'share': Decimal('50'),
            'nav': Decimal('10'),
        })

        # 验证第二次持仓（累加）
        position.refresh_from_db()
        assert position.holding_share == Decimal('150')
        assert position.holding_cost == Decimal('1500')

        # 第三次减仓
        operation3 = serializer.create({
            'account': account,
            'fund': fund,
            'operation_type': 'SELL',
            'operation_date': date.today(),
            'before_15': True,
            'amount': Decimal('300'),
            'share': Decimal('30'),
            'nav': Decimal('10'),
        })

        # 验证第三次持仓（减少）
        position.refresh_from_db()
        assert position.holding_share == Decimal('120')
        assert position.holding_cost == Decimal('1200')


@pytest.mark.django_db
class TestPositionSerializerGetFund:
    """测试 PositionSerializer.get_fund() - 返回基金详细信息"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def account(self, user):
        parent = Account.objects.create(user=user, name='父账户')
        return Account.objects.create(user=user, name='子账户', parent=parent)

    @pytest.fixture
    def fund_with_estimate(self):
        """创建包含估值的基金"""
        from datetime import datetime
        from django.utils import timezone

        return Fund.objects.create(
            fund_code='000001',
            fund_name='测试基金',
            fund_type='股票型',
            latest_nav=Decimal('1.5000'),
            latest_nav_date=date(2026, 2, 11),
            estimate_nav=Decimal('1.6000'),
            estimate_growth=Decimal('6.67'),
            estimate_time=timezone.make_aware(datetime(2026, 2, 12, 14, 30))
        )

    @pytest.fixture
    def fund_without_estimate(self):
        """创建不包含估值的基金"""
        return Fund.objects.create(
            fund_code='000002',
            fund_name='测试基金2',
            fund_type='债券型',
            latest_nav=Decimal('1.2000'),
            latest_nav_date=date(2026, 2, 11),
        )

    def test_get_fund_with_estimate(self, account, fund_with_estimate):
        """测试：返回包含估值的基金信息"""
        position = Position.objects.create(
            account=account,
            fund=fund_with_estimate,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        serializer = PositionSerializer(position)
        fund_data = serializer.data['fund']

        # 验证基本信息
        assert fund_data['fund_code'] == '000001'
        assert fund_data['fund_name'] == '测试基金'
        assert fund_data['fund_type'] == '股票型'

        # 验证净值信息
        assert fund_data['latest_nav'] == '1.5000'
        assert fund_data['latest_nav_date'] == '2026-02-11'

        # 验证估值信息
        assert fund_data['estimate_nav'] == '1.6000'
        assert fund_data['estimate_growth'] == '6.67'
        assert fund_data['estimate_time'] is not None

    def test_get_fund_without_estimate(self, account, fund_without_estimate):
        """测试：返回不包含估值的基金信息（估值字段为 None）"""
        position = Position.objects.create(
            account=account,
            fund=fund_without_estimate,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        serializer = PositionSerializer(position)
        fund_data = serializer.data['fund']

        # 验证基本信息
        assert fund_data['fund_code'] == '000002'
        assert fund_data['fund_name'] == '测试基金2'

        # 验证净值信息
        assert fund_data['latest_nav'] == '1.2000'

        # 验证估值信息为 None
        assert fund_data['estimate_nav'] is None
        assert fund_data['estimate_growth'] is None
        assert fund_data['estimate_time'] is None

    def test_position_serializer_includes_fund_field(self, account, fund_with_estimate):
        """测试：持仓序列化器包含 fund 字段"""
        position = Position.objects.create(
            account=account,
            fund=fund_with_estimate,
            holding_share=Decimal('100'),
            holding_cost=Decimal('1000'),
            holding_nav=Decimal('10'),
        )

        serializer = PositionSerializer(position)
        data = serializer.data

        # 验证 fund 字段存在
        assert 'fund' in data
        assert isinstance(data['fund'], dict)

        # 验证旧的字段仍然存在（向后兼容）
        assert 'fund_code' in data
        assert 'fund_name' in data
        assert 'fund_type' in data
