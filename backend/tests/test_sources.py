"""
测试数据源系统

测试点：
1. BaseEstimateSource 抽象基类
2. EastMoneySource 实现
3. SourceRegistry 注册表
4. 数据解析
"""
import pytest
from decimal import Decimal
from datetime import datetime, date
from unittest.mock import Mock, patch


class TestBaseEstimateSource:
    """BaseEstimateSource 抽象基类测试"""

    def test_cannot_instantiate_abstract_class(self):
        """测试不能直接实例化抽象类"""
        from api.sources.base import BaseEstimateSource

        with pytest.raises(TypeError):
            BaseEstimateSource()


class TestEastMoneySource:
    """EastMoneySource 测试"""

    def test_get_source_name(self):
        """测试获取数据源名称"""
        from api.sources.eastmoney import EastMoneySource

        source = EastMoneySource()
        assert source.get_source_name() == 'eastmoney'

    @patch('requests.get')
    def test_fetch_estimate_success(self, mock_get):
        """测试获取估值成功"""
        from api.sources.eastmoney import EastMoneySource

        # Mock API 响应
        mock_response = Mock()
        mock_response.text = 'jsonpgz({"fundcode":"000001","name":"华夏成长混合","jzrq":"2026-02-10","dwjz":"1.1490","gsz":"1.1370","gszzl":"-1.05","gztime":"2026-02-11 15:00"});'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        source = EastMoneySource()
        result = source.fetch_estimate('000001')

        assert result['fund_code'] == '000001'
        assert result['fund_name'] == '华夏成长混合'
        assert result['estimate_nav'] == Decimal('1.1370')
        assert result['estimate_growth'] == Decimal('-1.05')
        assert isinstance(result['estimate_time'], datetime)

    @patch('requests.get')
    def test_fetch_estimate_api_error(self, mock_get):
        """测试 API 错误处理"""
        from api.sources.eastmoney import EastMoneySource

        mock_get.side_effect = Exception('Network error')

        source = EastMoneySource()
        with pytest.raises(Exception):
            source.fetch_estimate('000001')

    @patch('requests.get')
    def test_fetch_realtime_nav_success(self, mock_get):
        """测试获取实际净值成功"""
        from api.sources.eastmoney import EastMoneySource

        mock_response = Mock()
        mock_response.text = 'jsonpgz({"fundcode":"000001","jzrq":"2026-02-10","dwjz":"1.1490"});'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        source = EastMoneySource()
        result = source.fetch_realtime_nav('000001')

        assert result['fund_code'] == '000001'
        assert result['nav'] == Decimal('1.1490')
        assert result['nav_date'] == date(2026, 2, 10)


class TestSourceRegistry:
    """SourceRegistry 测试"""

    def setup_method(self):
        """每个测试前清空注册表"""
        from api.sources.registry import SourceRegistry
        SourceRegistry._sources = {}

    def test_register_source(self):
        """测试注册数据源"""
        from api.sources.registry import SourceRegistry
        from api.sources.eastmoney import EastMoneySource

        source = EastMoneySource()
        SourceRegistry.register(source)

        assert 'eastmoney' in SourceRegistry.list_sources()

    def test_get_source(self):
        """测试获取数据源"""
        from api.sources.registry import SourceRegistry
        from api.sources.eastmoney import EastMoneySource

        source = EastMoneySource()
        SourceRegistry.register(source)

        retrieved = SourceRegistry.get_source('eastmoney')
        assert retrieved is source

    def test_get_nonexistent_source(self):
        """测试获取不存在的数据源"""
        from api.sources.registry import SourceRegistry

        result = SourceRegistry.get_source('nonexistent')
        assert result is None

    def test_list_sources(self):
        """测试列出所有数据源"""
        from api.sources.registry import SourceRegistry
        from api.sources.eastmoney import EastMoneySource

        source1 = EastMoneySource()
        SourceRegistry.register(source1)

        sources = SourceRegistry.list_sources()
        assert 'eastmoney' in sources
        assert len(sources) == 1


class TestFundListSync:
    """基金列表同步测试"""

    @patch('requests.get')
    def test_parse_fund_list(self, mock_get):
        """测试解析基金列表"""
        from api.sources.eastmoney import EastMoneySource

        mock_response = Mock()
        mock_response.text = 'var r = [["000001","HXCZHH","华夏成长混合","混合型-灵活","HUAXIACHENGZHANGHUNHE"],["000002","HXCZHH","华夏成长混合(后端)","混合型-灵活","HUAXIACHENGZHANGHUNHE"]];'
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        source = EastMoneySource()
        funds = source.fetch_fund_list()

        assert len(funds) == 2
        assert funds[0]['fund_code'] == '000001'
        assert funds[0]['fund_name'] == '华夏成长混合'
        assert funds[0]['fund_type'] == '混合型-灵活'
        assert funds[1]['fund_code'] == '000002'
