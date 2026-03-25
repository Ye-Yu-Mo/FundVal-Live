"""
测试 XiaoBeiYangJiSource（M2）

测试点：
1. 登录类型
2. send_sms / verify_phone
3. fetch_estimate（交易时段 / 非交易时段 fallback）
4. fetch_realtime_nav / fetch_today_nav
5. fetch_nav_history（字段映射、日期过滤、range 计算）
6. fetch_holdings（字段映射、份额推算、money=0 跳过）
7. 未登录时抛出明确异常
"""
import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────
# Mock 数据
# ─────────────────────────────────────────────

MOCK_LOGIN_RESPONSE = {
    'code': 200,
    'data': {
        'accessToken': 'test-token-abc',
        'refreshToken': 'refresh-xyz',
        'expiresIn': 2592000,
        'user': {
            'unionId': '13800138000',
            'phone': '13800138000',
        }
    }
}

MOCK_SEND_SMS_RESPONSE = {
    'code': 200,
    'data': '验证码发送成功',
    'msg': '请求成功',
}

# 交易时段：valuation != 0
MOCK_OPTIONAL_NAV_TRADING = {
    'code': 200,
    'data': [
        {
            'code': '025209',
            'nav': 1.6552,
            'navY': -0.04013,
            'valuation': 1.6900,
            'valuationY': 0.02112,
        }
    ]
}

# 非交易时段：valuation == 0
MOCK_OPTIONAL_NAV_NON_TRADING = {
    'code': 200,
    'data': [
        {
            'code': '025209',
            'nav': 1.6552,
            'navY': -0.04013,
            'valuation': 0,
            'valuationY': 0,
        }
    ]
}

MOCK_FUND_DETAIL_RESPONSE = {
    'code': 200,
    'data': {
        'code': '025209',
        'name': '永赢先锋半导体智选C',
        'nav': 1.6552,
        'latestPriceDate': '2026-03-23',
        'dailyYield': 0.0262,
        'lastYield': -0.04013,
        'money': 12345,
        'earnings': 22,
        'holdLot': 7458.31,
    }
}

MOCK_TRAJECTORY_RESPONSE = {
    'code': 200,
    'data': {
        'nav': 1.6552,
        'data': [
            {'d': '2026-01-05', 'n': 1.4548, 'y': 0.09260, 'a': 1.4548, 's': 0},
            {'d': '2026-01-06', 'n': 1.4950, 'y': 0.02763, 'a': 1.4950, 's': 0},
            {'d': '2026-02-01', 'n': 1.5500, 'y': 0.01200, 'a': 1.5500, 's': 0},
            {'d': '2026-03-23', 'n': 1.6552, 'y': -0.04013, 'a': 1.6552, 's': 0},
        ]
    }
}

MOCK_HOLD_LIST_RESPONSE = {
    'code': 200,
    'data': {
        'list': [
            {
                'code': '025209',
                'money': 12345,
                'earnings': 22,
                'headDate': '2026-03-23',
                'data': {'name': '永赢先锋半导体智选C'},
            },
            {
                'code': '000001',
                'money': 5000,
                'earnings': -100,
                'headDate': '2026-03-20',
                'data': {'name': '华夏成长混合'},
            },
            # money=0 的记录应被跳过
            {
                'code': '999999',
                'money': 0,
                'earnings': 0,
                'headDate': '2026-03-23',
                'data': {'name': '测试基金'},
            },
        ]
    }
}

# get-optional-change-nav 用于持仓份额推算
MOCK_OPTIONAL_NAV_FOR_HOLDINGS = {
    'code': 200,
    'data': [
        {'code': '025209', 'nav': 1.6552, 'navY': -0.04013, 'valuation': 0, 'valuationY': 0},
        {'code': '000001', 'nav': 2.5000, 'navY': 0.01000, 'valuation': 0, 'valuationY': 0},
    ]
}


# ─────────────────────────────────────────────
# 辅助：构造已登录的 source
# ─────────────────────────────────────────────

def make_logged_in_source():
    from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
    source = XiaoBeiYangJiSource()
    source._token = 'test-token-abc'
    source._union_id = '13800138000'
    return source


def mock_response(payload):
    mock = MagicMock()
    mock.json.return_value = payload
    mock.raise_for_status.return_value = None
    return mock

# 向后兼容别名
mock_response = mock_response


# ─────────────────────────────────────────────
# 测试：基础属性
# ─────────────────────────────────────────────

class TestBasicProperties:
    def test_source_name(self):
        from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
        assert XiaoBeiYangJiSource().get_source_name() == 'xiaobeiyangji'

    def test_login_type(self):
        from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
        assert XiaoBeiYangJiSource().get_login_type() == 'phone'

    def test_get_qrcode_returns_none(self):
        from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
        assert XiaoBeiYangJiSource().get_qrcode() is None

    def test_check_qrcode_state_returns_none(self):
        from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
        assert XiaoBeiYangJiSource().check_qrcode_state('any') is None


# ─────────────────────────────────────────────
# 测试：登录流程
# ─────────────────────────────────────────────

class TestLogin:
    @patch('requests.request')
    def test_send_sms_uses_phone_number_field(self, mock_req):
        """send_sms 请求体字段名是 phoneNumber，不是 phone"""
        from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
        mock_req.return_value = mock_response(MOCK_SEND_SMS_RESPONSE)

        XiaoBeiYangJiSource().send_sms('13800138000')

        body = mock_req.call_args[1]['json']
        assert 'phoneNumber' in body
        assert body['phoneNumber'] == '13800138000'
        assert 'phone' not in body

    @patch('requests.request')
    def test_send_sms_does_not_require_token(self, mock_req):
        """send_sms 登录前调用，Authorization 为空 Bearer"""
        from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
        mock_req.return_value = mock_response(MOCK_SEND_SMS_RESPONSE)

        XiaoBeiYangJiSource().send_sms('13800138000')

        headers = mock_req.call_args[1]['headers']
        assert headers.get('Authorization') == 'Bearer '

    @patch('requests.request')
    def test_verify_phone_sets_token_and_union_id(self, mock_req):
        """verify_phone 成功后设置 _token 和 _union_id"""
        from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
        mock_req.return_value = mock_response(MOCK_LOGIN_RESPONSE)

        source = XiaoBeiYangJiSource()
        result = source.verify_phone('13800138000', '123456')

        assert source._token == 'test-token-abc'
        assert source._union_id == '13800138000'
        assert result['token'] == 'test-token-abc'
        assert result['union_id'] == '13800138000'

    @patch('requests.request')
    def test_verify_phone_uses_phone_client_type(self, mock_req):
        """verify_phone 请求体 clientType 是 PHONE"""
        from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
        mock_req.return_value = mock_response(MOCK_LOGIN_RESPONSE)

        XiaoBeiYangJiSource().verify_phone('13800138000', '123456')

        body = mock_req.call_args[1]['json']
        assert body['clientType'] == 'PHONE'

    def test_logout_clears_token_and_union_id(self):
        source = make_logged_in_source()
        source.logout()
        assert source._token is None
        assert source._union_id is None


# ─────────────────────────────────────────────
# 测试：未登录保护
# ─────────────────────────────────────────────

class TestNotLoggedIn:
    def test_fetch_estimate_raises_when_not_logged_in(self):
        from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
        with pytest.raises(Exception, match='未登录'):
            XiaoBeiYangJiSource().fetch_estimate('025209')

    def test_fetch_holdings_raises_when_not_logged_in(self):
        from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
        with pytest.raises(Exception, match='未登录'):
            XiaoBeiYangJiSource().fetch_holdings()

    def test_fetch_nav_history_raises_when_not_logged_in(self):
        from api.sources.xiaobeiyangji import XiaoBeiYangJiSource
        with pytest.raises(Exception, match='未登录'):
            XiaoBeiYangJiSource().fetch_nav_history('025209')


# ─────────────────────────────────────────────
# 测试：估值
# ─────────────────────────────────────────────

class TestFetchEstimate:
    @patch('requests.request')
    def test_trading_time_uses_valuation(self, mock_req):
        """交易时段：使用 valuation + valuationY"""
        mock_req.side_effect = [
            mock_response(MOCK_OPTIONAL_NAV_TRADING),
            mock_response(MOCK_FUND_DETAIL_RESPONSE),
        ]
        source = make_logged_in_source()
        result = source.fetch_estimate('025209')

        assert result is not None
        assert result['fund_code'] == '025209'
        assert result['estimate_nav'] == Decimal('1.6900')
        # valuationY=0.02112 → 2.112%
        assert abs(result['estimate_growth'] - Decimal('2.112')) < Decimal('0.001')

    @patch('requests.request')
    def test_non_trading_time_fallback_to_nav(self, mock_req):
        """非交易时段（valuation=0）：fallback 到 nav + navY"""
        mock_req.side_effect = [
            mock_response(MOCK_OPTIONAL_NAV_NON_TRADING),
            mock_response(MOCK_FUND_DETAIL_RESPONSE),
        ]
        source = make_logged_in_source()
        result = source.fetch_estimate('025209')

        assert result is not None
        assert result['estimate_nav'] == Decimal('1.6552')
        # navY=-0.04013 → -4.013%
        assert abs(result['estimate_growth'] - Decimal('-4.013')) < Decimal('0.001')

    @patch('requests.request')
    def test_estimate_nav_never_zero(self, mock_req):
        """estimate_nav 不能为 0"""
        mock_req.side_effect = [
            mock_response(MOCK_OPTIONAL_NAV_NON_TRADING),
            mock_response(MOCK_FUND_DETAIL_RESPONSE),
        ]
        source = make_logged_in_source()
        result = source.fetch_estimate('025209')

        assert result['estimate_nav'] != Decimal('0')


# ─────────────────────────────────────────────
# 测试：实时净值 / 当日净值
# ─────────────────────────────────────────────

class TestFetchNav:
    @patch('requests.request')
    def test_fetch_realtime_nav(self, mock_req):
        mock_req.return_value = mock_response(MOCK_FUND_DETAIL_RESPONSE)
        source = make_logged_in_source()
        result = source.fetch_realtime_nav('025209')

        assert result['fund_code'] == '025209'
        assert result['nav'] == Decimal('1.6552')
        assert result['nav_date'] == date(2026, 3, 23)

    @patch('requests.request')
    def test_fetch_today_nav_returns_none_if_not_today(self, mock_req):
        """净值日期不是今天，返回 None"""
        mock_req.return_value = mock_response(MOCK_FUND_DETAIL_RESPONSE)
        source = make_logged_in_source()
        # latestPriceDate=2026-03-23，今天是 2026-03-25，应返回 None
        result = source.fetch_today_nav('025209')
        assert result is None

    @patch('requests.request')
    def test_fetch_today_nav_returns_data_if_today(self, mock_req):
        """净值日期是今天，返回数据"""
        import copy
        detail = copy.deepcopy(MOCK_FUND_DETAIL_RESPONSE)
        detail['data']['latestPriceDate'] = date.today().isoformat()
        mock_req.return_value = mock_response(detail)

        source = make_logged_in_source()
        result = source.fetch_today_nav('025209')
        assert result is not None
        assert result['nav_date'] == date.today()


# ─────────────────────────────────────────────
# 测试：历史净值
# ─────────────────────────────────────────────

class TestFetchNavHistory:
    @patch('requests.request')
    def test_field_mapping(self, mock_req):
        """d→nav_date, n→nav, y→growth（*100）"""
        mock_req.return_value = mock_response(MOCK_TRAJECTORY_RESPONSE)
        source = make_logged_in_source()
        result = source.fetch_nav_history('025209')

        assert len(result) > 0
        first = result[0]
        assert 'nav_date' in first
        assert 'nav' in first
        assert 'growth' in first
        assert first['fund_code'] == '025209'
        # y=0.09260 → growth≈9.260
        assert abs(first['growth'] - Decimal('9.260')) < Decimal('0.01')

    @patch('requests.request')
    def test_date_filter(self, mock_req):
        """start_date/end_date 过滤"""
        mock_req.return_value = mock_response(MOCK_TRAJECTORY_RESPONSE)
        source = make_logged_in_source()
        result = source.fetch_nav_history(
            '025209',
            start_date=date(2026, 2, 1),
            end_date=date(2026, 3, 31),
        )
        dates = [r['nav_date'] for r in result]
        assert all(date(2026, 2, 1) <= d <= date(2026, 3, 31) for d in dates)
        # 2026-01-05 和 2026-01-06 应被过滤掉
        assert date(2026, 1, 5) not in dates

    @patch('requests.request')
    def test_range_calculation_no_dates(self, mock_req):
        """无日期参数，默认 range=3"""
        mock_req.return_value = mock_response(MOCK_TRAJECTORY_RESPONSE)
        source = make_logged_in_source()
        source.fetch_nav_history('025209')

        body = mock_req.call_args[1]['json']
        assert body['range'] == 3

    @patch('requests.request')
    def test_range_calculation_with_dates(self, mock_req):
        """有日期参数，range 按月数计算"""
        mock_req.return_value = mock_response(MOCK_TRAJECTORY_RESPONSE)
        source = make_logged_in_source()
        source.fetch_nav_history(
            '025209',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
        )
        body = mock_req.call_args[1]['json']
        assert body['range'] == 6

    @patch('requests.request')
    def test_range_capped_at_12(self, mock_req):
        """range 最大 12"""
        mock_req.return_value = mock_response(MOCK_TRAJECTORY_RESPONSE)
        source = make_logged_in_source()
        source.fetch_nav_history(
            '025209',
            start_date=date(2024, 1, 1),
            end_date=date(2026, 3, 25),
        )
        body = mock_req.call_args[1]['json']
        assert body['range'] <= 12


# ─────────────────────────────────────────────
# 测试：持仓导入
# ─────────────────────────────────────────────

class TestFetchHoldings:
    @patch('requests.request')
    def test_basic_field_mapping(self, mock_req):
        """fund_code, fund_name, amount, earnings 字段正确"""
        mock_req.side_effect = [
            mock_response(MOCK_HOLD_LIST_RESPONSE),
            mock_response(MOCK_OPTIONAL_NAV_FOR_HOLDINGS),
        ]
        source = make_logged_in_source()
        result = source.fetch_holdings()

        codes = [r['fund_code'] for r in result]
        assert '025209' in codes
        assert '000001' in codes

        h = next(r for r in result if r['fund_code'] == '025209')
        assert h['amount'] == Decimal('12345')
        assert h['earnings'] == Decimal('22')
        assert h['fund_name'] == '永赢先锋半导体智选C'

    @patch('requests.request')
    def test_money_zero_skipped(self, mock_req):
        """money=0 的记录被跳过"""
        mock_req.side_effect = [
            mock_response(MOCK_HOLD_LIST_RESPONSE),
            mock_response(MOCK_OPTIONAL_NAV_FOR_HOLDINGS),
        ]
        source = make_logged_in_source()
        result = source.fetch_holdings()

        codes = [r['fund_code'] for r in result]
        assert '999999' not in codes

    @patch('requests.request')
    def test_share_calculated_from_nav(self, mock_req):
        """share = money / nav"""
        mock_req.side_effect = [
            mock_response(MOCK_HOLD_LIST_RESPONSE),
            mock_response(MOCK_OPTIONAL_NAV_FOR_HOLDINGS),
        ]
        source = make_logged_in_source()
        result = source.fetch_holdings()

        h = next(r for r in result if r['fund_code'] == '025209')
        # money=12345, nav=1.6552 → share ≈ 7458.16
        expected_share = Decimal('12345') / Decimal('1.6552')
        assert abs(h['share'] - expected_share) < Decimal('0.01')
