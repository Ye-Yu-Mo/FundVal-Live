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
        assert source.get_source_name() == "eastmoney"

    def test_fetch_estimate_returns_none(self):
        """M1: fetch_estimate 返回 None（fundgz 已失效）"""
        from api.sources.eastmoney import EastMoneySource

        source = EastMoneySource()
        result = source.fetch_estimate("000001")

        # M1 后 fetch_estimate 直接返回 None，不抛异常
        assert result is None

    @patch("requests.get")
    def test_fetch_estimate_api_error(self, mock_get):
        """测试 API 错误处理 - 现在返回 None 而不是抛出异常"""
        from api.sources.eastmoney import EastMoneySource

        mock_get.side_effect = Exception("Network error")

        source = EastMoneySource()
        result = source.fetch_estimate("000001")

        # 异常处理后应该返回 None
        assert result is None

    @patch("requests.get")
    def test_fetch_realtime_nav_success(self, mock_get):
        """测试获取实际净值成功 (M1: Mobile API)"""
        from api.sources.eastmoney import EastMoneySource
        from unittest.mock import MagicMock

        mock = MagicMock()
        mock.json.return_value = {
            "Datas": [
                {"FCODE": "000001", "ACCNAV": "1.1490", "PDATE": "2026-02-10"},
            ]
        }
        mock.raise_for_status = MagicMock()
        mock_get.return_value = mock

        source = EastMoneySource()
        result = source.fetch_realtime_nav("000001")

        assert result["fund_code"] == "000001"
        assert result["nav"] == Decimal("1.1490")
        assert result["nav_date"] == date(2026, 2, 10)


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

        assert "eastmoney" in SourceRegistry.list_sources()

    def test_get_source(self):
        """测试获取数据源"""
        from api.sources.registry import SourceRegistry
        from api.sources.eastmoney import EastMoneySource

        source = EastMoneySource()
        SourceRegistry.register(source)

        retrieved = SourceRegistry.get_source("eastmoney")
        # 每次返回新实例，类型相同即可
        assert isinstance(retrieved, EastMoneySource)

    def test_get_nonexistent_source(self):
        """测试获取不存在的数据源"""
        from api.sources.registry import SourceRegistry

        result = SourceRegistry.get_source("nonexistent")
        assert result is None

    def test_list_sources(self):
        """测试列出所有数据源"""
        from api.sources.registry import SourceRegistry
        from api.sources.eastmoney import EastMoneySource

        source1 = EastMoneySource()
        SourceRegistry.register(source1)

        sources = SourceRegistry.list_sources()
        assert "eastmoney" in sources


class TestFundListSync:
    """基金列表同步测试 (M2: 通过 akshare 恢复)"""

    def test_fetch_fund_list_returns_data(self):
        """M2: fetch_fund_list 通过 ak.fund_name_em() 返回列表"""
        from api.sources.eastmoney import EastMoneySource
        from unittest.mock import patch
        import pandas as pd

        source = EastMoneySource()
        with patch("akshare.fund_name_em") as mock_ak:
            mock_ak.return_value = pd.DataFrame([
                {"基金代码": "000001", "基金简称": "华夏成长", "基金类型": "混合型"},
            ])

            funds = source.fetch_fund_list()

        assert len(funds) == 1
        assert funds[0]["fund_code"] == "000001"
        assert funds[0]["fund_name"] == "华夏成长"
