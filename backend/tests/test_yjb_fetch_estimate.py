"""
测试养基宝基金估值获取功能

测试点：
1. YangJiBaoSource.fetch_estimate() - 从所有账户持仓提取估值
2. YangJiBaoSource.fetch_today_nav() - 从所有账户持仓提取当日净值
3. YangJiBaoSource.fetch_realtime_nav() - 从所有账户持仓提取昨日净值
4. 边界条件：基金不在持仓中、数据缺失、日期校验
"""
import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import Mock, patch
from api.sources.yangjibao import YangJiBaoSource


# ─────────────────────────────────────────────
# Mock 数据
# ─────────────────────────────────────────────

MOCK_ACCOUNTS_RESPONSE = {
    'code': 200,
    'data': {
        'list': [
            {'id': 'account-1', 'title': '账户1'},
            {'id': 'account-2', 'title': '账户2'},
        ]
    }
}

MOCK_HOLDINGS_RESPONSE = {
    'code': 200,
    'data': [
        {
            'code': '000001',
            'short_name': '华夏成长',
            'nv_info': {
                'dwjz': '1.2345',
                'jzrq': '2024-02-23',
                'gsz': '1.2456',
                'gszzl': '0.90',
            }
        },
        {
            'code': '000002',
            'short_name': '华夏回报',
            'nv_info': {
                'dwjz': '2.5678',
                'jzrq': '2024-02-23',
                'vgsz': '2.5800',
                'vgszzl': '0.48',
            }
        },
        {
            'code': '000003',
            'short_name': '华夏稳定',
            'nv_info': {
                'dwjz': '1.0123',
                'jzrq': '2024-02-22',
            }
        }
    ]
}

MOCK_EMPTY_HOLDINGS = {
    'code': 200,
    'data': []
}

MOCK_TODAY_HOLDINGS = {
    'code': 200,
    'data': [
        {
            'code': '000001',
            'short_name': '华夏成长',
            'nv_info': {
                'dwjz': '1.2345',
                'jzrq': date.today().strftime('%Y-%m-%d'),
            }
        }
    ]
}


class TestYangJiBaoFetchEstimate:
    """测试 fetch_estimate 方法"""

    @patch('api.sources.yangjibao.requests.request')
    def test_fetch_estimate_with_gsz(self, mock_request):
        """测试获取估值（优先使用 gsz）"""
        def mock_side_effect(method, url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            if '/user_account' in url:
                mock_response.json.return_value = MOCK_ACCOUNTS_RESPONSE
            elif '/fund_hold' in url:
                mock_response.json.return_value = MOCK_HOLDINGS_RESPONSE
            return mock_response

        mock_request.side_effect = mock_side_effect

        source = YangJiBaoSource()
        source._token = 'test-token'

        result = source.fetch_estimate('000001')

        assert result is not None
        assert result['fund_code'] == '000001'
        assert result['fund_name'] == '华夏成长'
        assert result['estimate_nav'] == Decimal('1.2456')
        assert result['estimate_growth'] == Decimal('0.90')
        assert isinstance(result['estimate_time'], datetime)

    @patch('api.sources.yangjibao.requests.request')
    def test_fetch_estimate_fallback_to_vgsz(self, mock_request):
        """测试估值回退到 vgsz（无 gsz 时）"""
        def mock_side_effect(method, url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            if '/user_account' in url:
                mock_response.json.return_value = MOCK_ACCOUNTS_RESPONSE
            elif '/fund_hold' in url:
                mock_response.json.return_value = MOCK_HOLDINGS_RESPONSE
            return mock_response

        mock_request.side_effect = mock_side_effect

        source = YangJiBaoSource()
        source._token = 'test-token'

        result = source.fetch_estimate('000002')

        assert result is not None
        assert result['fund_code'] == '000002'
        assert result['estimate_nav'] == Decimal('2.5800')
        assert result['estimate_growth'] == Decimal('0.48')

    @patch('api.sources.yangjibao.requests.request')
    def test_fetch_estimate_no_estimate_data(self, mock_request):
        """测试无估值数据时返回 None"""
        def mock_side_effect(method, url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            if '/user_account' in url:
                mock_response.json.return_value = MOCK_ACCOUNTS_RESPONSE
            elif '/fund_hold' in url:
                mock_response.json.return_value = MOCK_HOLDINGS_RESPONSE
            return mock_response

        mock_request.side_effect = mock_side_effect

        source = YangJiBaoSource()
        source._token = 'test-token'

        result = source.fetch_estimate('000003')

        assert result is None

    @patch('api.sources.yangjibao.requests.request')
    def test_fetch_estimate_fund_not_in_holdings(self, mock_request):
        """测试基金不在持仓中"""
        def mock_side_effect(method, url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            if '/user_account' in url:
                mock_response.json.return_value = MOCK_ACCOUNTS_RESPONSE
            elif '/fund_hold' in url:
                mock_response.json.return_value = MOCK_HOLDINGS_RESPONSE
            return mock_response

        mock_request.side_effect = mock_side_effect

        source = YangJiBaoSource()
        source._token = 'test-token'

        result = source.fetch_estimate('999999')

        assert result is None

    def test_fetch_estimate_no_token(self):
        """测试未登录时返回 None"""
        source = YangJiBaoSource()
        result = source.fetch_estimate('000001')
        assert result is None


class TestYangJiBaoFetchTodayNav:
    """测试 fetch_today_nav 方法"""

    @patch('api.sources.yangjibao.requests.request')
    def test_fetch_today_nav_success(self, mock_request):
        """测试获取当日净值成功"""
        def mock_side_effect(method, url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            if '/user_account' in url:
                mock_response.json.return_value = MOCK_ACCOUNTS_RESPONSE
            elif '/fund_hold' in url:
                mock_response.json.return_value = MOCK_TODAY_HOLDINGS
            return mock_response

        mock_request.side_effect = mock_side_effect

        source = YangJiBaoSource()
        source._token = 'test-token'

        result = source.fetch_today_nav('000001')

        assert result is not None
        assert result['fund_code'] == '000001'
        assert result['nav'] == Decimal('1.2345')
        assert result['nav_date'] == date.today()

    @patch('api.sources.yangjibao.requests.request')
    def test_fetch_today_nav_not_today(self, mock_request):
        """测试净值日期不是今天时返回 None"""
        def mock_side_effect(method, url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            if '/user_account' in url:
                mock_response.json.return_value = MOCK_ACCOUNTS_RESPONSE
            elif '/fund_hold' in url:
                mock_response.json.return_value = MOCK_HOLDINGS_RESPONSE
            return mock_response

        mock_request.side_effect = mock_side_effect

        source = YangJiBaoSource()
        source._token = 'test-token'

        result = source.fetch_today_nav('000001')

        assert result is None


class TestYangJiBaoFetchRealtimeNav:
    """测试 fetch_realtime_nav 方法"""

    @patch('api.sources.yangjibao.requests.request')
    def test_fetch_realtime_nav_success(self, mock_request):
        """测试获取昨日净值成功"""
        def mock_side_effect(method, url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            if '/user_account' in url:
                mock_response.json.return_value = MOCK_ACCOUNTS_RESPONSE
            elif '/fund_hold' in url:
                mock_response.json.return_value = MOCK_HOLDINGS_RESPONSE
            return mock_response

        mock_request.side_effect = mock_side_effect

        source = YangJiBaoSource()
        source._token = 'test-token'

        result = source.fetch_realtime_nav('000001')

        assert result is not None
        assert result['fund_code'] == '000001'
        assert result['nav'] == Decimal('1.2345')
        assert result['nav_date'] == date(2024, 2, 23)
