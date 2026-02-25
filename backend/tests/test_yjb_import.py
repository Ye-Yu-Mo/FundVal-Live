"""
测试养基宝账户数据一键导入功能

测试点：
1. YangJiBaoSource.fetch_accounts() - 获取账户列表
2. YangJiBaoSource.fetch_holdings(account_id) - 获取持仓
3. import_yjb.import_from_yangjibao() - 导入服务
4. SourceCredentialViewSet.import_from_yangjibao API
"""
import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import Mock, patch, MagicMock
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

# ─────────────────────────────────────────────
# Mock 数据
# ─────────────────────────────────────────────

MOCK_USER_ACCOUNT_RESPONSE = {
    'code': 200,
    'data': {
        'list': [
            {'id': 'acc-001', 'title': '招商银行'},
            {'id': 'acc-002', 'title': '支付宝'},
        ]
    }
}

MOCK_ACCOUNT_COLLECT_RESPONSE = {
    'code': 200,
    'data': {
        'account_data': [
            {'account_id': 'acc-001', 'title': '招商银行', 'today_income': '12.34'},
            {'account_id': 'acc-002', 'title': '支付宝', 'today_income': '5.67'},
        ]
    }
}

MOCK_HOLDINGS_ACC001 = {
    'code': 200,
    'data': [
        {
            'code': '000001',
            'short_name': '华夏成长',
            'hold_share': '1000.0000',
            'hold_cost': '1.2000',
            'money': '1200.00',
            'hold_day': '2024-01-15',
            'last_net': '1.2345',
        },
        {
            'code': '000002',
            'short_name': '华夏回报',
            'hold_share': '500.0000',
            'hold_cost': '2.5000',
            'money': '1250.00',
            'hold_day': '2024-02-01',
            'last_net': '2.5678',
        },
    ]
}

MOCK_HOLDINGS_ACC002 = {
    'code': 200,
    'data': [
        {
            'code': '000003',
            'short_name': '华夏稳定',
            'hold_share': '200.0000',
            'hold_cost': '1.0000',
            'money': '200.00',
            'hold_day': '2024-01-20',
            'last_net': '1.0123',
        },
    ]
}

MOCK_EMPTY_HOLDINGS = {'code': 200, 'data': []}


# ─────────────────────────────────────────────
# 1. YangJiBaoSource.fetch_accounts()
# ─────────────────────────────────────────────

class TestYangJiBaoFetchAccounts:
    """测试 fetch_accounts 方法"""

    @patch('api.sources.yangjibao.requests.request')
    def test_fetch_accounts_success(self, mock_request):
        """测试获取账户列表成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_USER_ACCOUNT_RESPONSE
        mock_request.return_value = mock_response

        from api.sources.yangjibao import YangJiBaoSource
        source = YangJiBaoSource()
        source._token = 'test-token'

        result = source.fetch_accounts()

        assert len(result) == 2
        assert result[0]['account_id'] == 'acc-001'
        assert result[0]['name'] == '招商银行'
        assert result[1]['account_id'] == 'acc-002'
        assert result[1]['name'] == '支付宝'

    @patch('api.sources.yangjibao.requests.request')
    def test_fetch_accounts_empty(self, mock_request):
        """测试空账户列表"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'code': 200, 'data': {'list': []}}
        mock_request.return_value = mock_response

        from api.sources.yangjibao import YangJiBaoSource
        source = YangJiBaoSource()
        source._token = 'test-token'

        result = source.fetch_accounts()

        assert result == []

    def test_fetch_accounts_no_token(self):
        """测试未登录时抛出异常"""
        from api.sources.yangjibao import YangJiBaoSource
        source = YangJiBaoSource()

        with pytest.raises(Exception, match='未登录'):
            source.fetch_accounts()


# ─────────────────────────────────────────────
# 2. YangJiBaoSource.fetch_holdings(account_id)
# ─────────────────────────────────────────────

class TestYangJiBaoFetchHoldings:
    """测试 fetch_holdings 方法"""

    @patch('api.sources.yangjibao.requests.request')
    def test_fetch_holdings_success(self, mock_request):
        """测试获取持仓成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_HOLDINGS_ACC001
        mock_request.return_value = mock_response

        from api.sources.yangjibao import YangJiBaoSource
        source = YangJiBaoSource()
        source._token = 'test-token'

        result = source.fetch_holdings('acc-001')

        assert len(result) == 2
        assert result[0]['fund_code'] == '000001'
        assert result[0]['fund_name'] == '华夏成长'
        assert result[0]['share'] == Decimal('1000.0000')
        assert result[0]['nav'] == Decimal('1.2000')
        assert result[0]['amount'] == Decimal('1200.00')
        assert result[0]['operation_date'] == date(2024, 1, 15)

    @patch('api.sources.yangjibao.requests.request')
    def test_fetch_holdings_empty(self, mock_request):
        """测试空持仓"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_EMPTY_HOLDINGS
        mock_request.return_value = mock_response

        from api.sources.yangjibao import YangJiBaoSource
        source = YangJiBaoSource()
        source._token = 'test-token'

        result = source.fetch_holdings('acc-001')

        assert result == []

    def test_fetch_holdings_no_token(self):
        """测试未登录时抛出异常"""
        from api.sources.yangjibao import YangJiBaoSource
        source = YangJiBaoSource()

        with pytest.raises(Exception, match='未登录'):
            source.fetch_holdings('acc-001')


# ─────────────────────────────────────────────
# 3. import_yjb.import_from_yangjibao()
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestImportFromYangJiBao:
    """测试导入服务"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='testuser', password='pass')

    @pytest.fixture
    def mock_source(self):
        source = Mock()
        source.fetch_accounts.return_value = [
            {'account_id': 'acc-001', 'name': '招商银行'},
        ]
        source.fetch_holdings.return_value = [
            {
                'fund_code': '000001',
                'fund_name': '华夏成长',
                'share': Decimal('1000.0000'),
                'nav': Decimal('1.2000'),
                'amount': Decimal('1200.00'),
                'operation_date': date(2024, 1, 15),
            }
        ]
        return source

    def test_import_creates_parent_account(self, user, mock_source):
        """测试导入创建父账户（养基宝）"""
        from api.services.import_yjb import import_from_yangjibao
        from api.models import Account

        import_from_yangjibao(user, mock_source)

        parent = Account.objects.filter(user=user, name='养基宝').first()
        assert parent is not None
        assert parent.parent is None

    def test_import_creates_sub_account(self, user, mock_source):
        """测试导入创建子账户"""
        from api.services.import_yjb import import_from_yangjibao
        from api.models import Account

        import_from_yangjibao(user, mock_source)

        sub = Account.objects.filter(user=user, name='招商银行').first()
        assert sub is not None
        assert sub.parent is not None
        assert sub.parent.name == '养基宝'

    def test_import_creates_fund(self, user, mock_source):
        """测试导入创建基金"""
        from api.services.import_yjb import import_from_yangjibao
        from api.models import Fund

        import_from_yangjibao(user, mock_source)

        fund = Fund.objects.filter(fund_code='000001').first()
        assert fund is not None
        assert fund.fund_name == '华夏成长'

    def test_import_creates_position_operation(self, user, mock_source):
        """测试导入创建持仓操作"""
        from api.services.import_yjb import import_from_yangjibao
        from api.models import PositionOperation

        import_from_yangjibao(user, mock_source)

        op = PositionOperation.objects.filter(
            account__name='招商银行',
            fund__fund_code='000001',
        ).first()

        assert op is not None
        assert op.operation_type == 'BUY'
        assert op.share == Decimal('1000.0000')
        assert op.nav == Decimal('1.2000')
        assert op.amount == Decimal('1200.00')
        assert op.operation_date == date(2024, 1, 15)

    def test_import_returns_result_summary(self, user, mock_source):
        """测试导入返回结果摘要"""
        from api.services.import_yjb import import_from_yangjibao

        result = import_from_yangjibao(user, mock_source)

        assert 'accounts_created' in result
        assert 'accounts_skipped' in result
        assert 'holdings_created' in result
        assert 'holdings_skipped' in result
        assert result['accounts_created'] == 1
        assert result['holdings_created'] == 1

    def test_import_idempotent_accounts(self, user, mock_source):
        """测试重复导入账户不重复创建"""
        from api.services.import_yjb import import_from_yangjibao
        from api.models import Account

        import_from_yangjibao(user, mock_source)
        import_from_yangjibao(user, mock_source)

        assert Account.objects.filter(user=user, name='招商银行').count() == 1

    def test_import_idempotent_holdings(self, user, mock_source):
        """测试重复导入持仓不重复创建"""
        from api.services.import_yjb import import_from_yangjibao
        from api.models import PositionOperation

        import_from_yangjibao(user, mock_source)
        import_from_yangjibao(user, mock_source)

        assert PositionOperation.objects.filter(
            account__name='招商银行',
            fund__fund_code='000001',
        ).count() == 1

    def test_import_multiple_accounts(self, user):
        """测试导入多个账户"""
        from api.services.import_yjb import import_from_yangjibao
        from api.models import Account, PositionOperation

        mock_source = Mock()
        mock_source.fetch_accounts.return_value = [
            {'account_id': 'acc-001', 'name': '招商银行'},
            {'account_id': 'acc-002', 'name': '支付宝'},
        ]

        def mock_fetch_holdings(account_id):
            if account_id == 'acc-001':
                return [{'fund_code': '000001', 'fund_name': '华夏成长',
                         'share': Decimal('1000'), 'nav': Decimal('1.2'),
                         'amount': Decimal('1200'), 'operation_date': date(2024, 1, 15)}]
            elif account_id == 'acc-002':
                return [{'fund_code': '000003', 'fund_name': '华夏稳定',
                         'share': Decimal('200'), 'nav': Decimal('1.0'),
                         'amount': Decimal('200'), 'operation_date': date(2024, 1, 20)}]
            return []

        mock_source.fetch_holdings.side_effect = mock_fetch_holdings

        result = import_from_yangjibao(user, mock_source)

        assert Account.objects.filter(user=user, parent__name='养基宝').count() == 2
        assert result['accounts_created'] == 2
        assert result['holdings_created'] == 2

    def test_import_skips_holding_with_missing_data(self, user):
        """测试跳过缺失关键数据的持仓"""
        from api.services.import_yjb import import_from_yangjibao

        mock_source = Mock()
        mock_source.fetch_accounts.return_value = [
            {'account_id': 'acc-001', 'name': '招商银行'},
        ]
        mock_source.fetch_holdings.return_value = [
            {
                'fund_code': '',  # 缺失基金代码
                'fund_name': '未知基金',
                'share': Decimal('100'),
                'nav': Decimal('1.0'),
                'amount': Decimal('100'),
                'operation_date': date(2024, 1, 15),
            }
        ]

        result = import_from_yangjibao(user, mock_source)

        assert result['holdings_skipped'] == 1
        assert result['holdings_created'] == 0


# ─────────────────────────────────────────────
# 4. API 端点测试
# ─────────────────────────────────────────────

@pytest.mark.django_db
class TestImportFromYangJiBaoAPI:
    """测试导入 API 端点"""

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client.force_authenticate(user=self.user)

    def test_import_requires_login(self):
        """测试未登录养基宝时返回 400"""
        response = self.client.post('/api/source-credentials/import/')
        assert response.status_code == 400
        assert '未登录' in response.json().get('error', '')

    @patch('api.services.import_yjb.import_from_yangjibao')
    def test_import_success(self, mock_import):
        """测试导入成功"""
        from api.models import UserSourceCredential

        UserSourceCredential.objects.create(
            user=self.user,
            source_name='yangjibao',
            token='test-token',
            is_active=True,
        )

        mock_import.return_value = {
            'accounts_created': 2,
            'accounts_skipped': 0,
            'holdings_created': 3,
            'holdings_skipped': 0,
        }

        response = self.client.post('/api/source-credentials/import/')

        assert response.status_code == 200
        data = response.json()
        assert data['accounts_created'] == 2
        assert data['holdings_created'] == 3

    def test_import_unauthenticated(self):
        """测试未登录系统时返回 401"""
        client = APIClient()
        response = client.post('/api/source-credentials/import/')
        assert response.status_code == 401
