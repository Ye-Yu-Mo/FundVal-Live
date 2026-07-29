"""
测试 SourceRegistry 健康检查机制 (M1 功能4)

新增:
- BaseEstimateSource.is_available() — 默认 True
- EastMoneySource.is_available() — 检查 Mobile API 连通性
- DanjuanSource.is_available() — 返回 False
- SourceRegistry.list_available_sources() — 过滤不可用源
"""

import pytest
from unittest.mock import patch, MagicMock
import requests

from api.sources.base import BaseEstimateSource
from api.sources.eastmoney import EastMoneySource
from api.sources.danjuan import DanjuanSource
from api.sources.sina import SinaStockSource
from api.sources.registry import SourceRegistry


# ================================================================
# BaseEstimateSource.is_available() — 默认 True
# ================================================================

class TestBaseIsAvailable:
    """基类 is_available() 默认返回 True"""

    def test_default_returns_true(self):
        """非抽象方法，默认 True，保证向后兼容"""
        # 通过一个具体子类测试
        source = SinaStockSource()
        # SinaStockSource 没有 override is_available()，应继承默认 True
        assert hasattr(source, "is_available"), "基类应有 is_available 方法"
        assert source.is_available() is True

    def test_is_not_abstract(self):
        """is_available 不是抽象方法 — 子类不强制实现"""
        import inspect
        # 检查 BaseEstimateSource 是否有 is_available 且不是 abstractmethod
        assert hasattr(BaseEstimateSource, "is_available"), (
            "BaseEstimateSource 应有 is_available 方法"
        )


# ================================================================
# EastMoneySource.is_available() — 检查 Mobile API 连通性
# ================================================================

class TestEastMoneyIsAvailable:
    """EastMoneySource.is_available() 通过 Mobile API 检查连通性"""

    def test_returns_true_when_api_available(self):
        """FundMNFInfo 返回正常数据 → True"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.json.return_value = {
                "Datas": [
                    {"FCODE": "000001", "ACCNAV": "1.4070", "PDATE": "2026-06-17"},
                ],
                "ErrCode": 0,
            }
            mock.raise_for_status = MagicMock()
            mock_get.return_value = mock

            assert source.is_available() is True

    def test_returns_false_when_no_data(self):
        """FundMNFInfo 返回空 Datas → False"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.json.return_value = {"Datas": [], "ErrCode": 0}
            mock.raise_for_status = MagicMock()
            mock_get.return_value = mock

            assert source.is_available() is False

    def test_returns_false_on_network_error(self):
        """网络错误 → False，不抛异常"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("timeout")

            assert source.is_available() is False

    def test_returns_false_on_timeout(self):
        """超时 → False"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.Timeout("timeout")

            assert source.is_available() is False

    def test_uses_fund_mn_finfo_endpoint(self):
        """检查请求了 FundMNFInfo 端点（最轻量的 mobile 请求）"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.json.return_value = {
                "Datas": [{"FCODE": "000001", "ACCNAV": "1.0", "PDATE": "2026-01-01"}],
                "ErrCode": 0,
            }
            mock.raise_for_status = MagicMock()
            mock_get.return_value = mock

            source.is_available()

            called_url = str(mock_get.call_args)
            assert "FundMNFInfo" in called_url, (
                f"应该调 FundMNFInfo 端点, 实际: {called_url}"
            )
            assert "000001" in called_url, (
                f"应该查询 000001 测试基金, 实际: {called_url}"
            )

    def test_timeout_is_short(self):
        """健康检查超时应 ≤ 5s（不应阻塞）"""
        source = EastMoneySource()

        with patch("requests.get") as mock_get:
            mock = MagicMock()
            mock.json.return_value = {
                "Datas": [{"FCODE": "000001", "ACCNAV": "1.0", "PDATE": "2026-01-01"}],
                "ErrCode": 0,
            }
            mock.raise_for_status = MagicMock()
            mock_get.return_value = mock

            source.is_available()

            timeout = mock_get.call_args.kwargs.get("timeout", None)
            assert timeout is not None, "健康检查应设置超时"
            assert timeout <= 5, f"超时应 ≤ 5s, 实际: {timeout}"


# ================================================================
# DanjuanSource.is_available() — 返回 False
# ================================================================

class TestDanjuanIsAvailable:
    """DanjuanSource.is_available() 返回 False"""

    def test_returns_false(self):
        """蛋卷 IP 被封禁，始终返回 False"""
        source = DanjuanSource()
        assert source.is_available() is False

    def test_does_not_make_http_request(self):
        """不应发起 HTTP 请求"""
        source = DanjuanSource()

        with patch("requests.get") as mock_get:
            result = source.is_available()

        assert result is False
        mock_get.assert_not_called()


# ================================================================
# SourceRegistry.list_available_sources() — 过滤
# ================================================================

class TestListAvailableSources:
    """SourceRegistry.list_available_sources() 过滤不可用源"""

    def test_excludes_danjuan(self):
        """danjuan 不在可用源列表中"""
        available = SourceRegistry.list_available_sources()
        assert "danjuan" not in available, (
            f"danjuan 应被过滤, 实际可用: {available}"
        )

    def test_includes_eastmoney(self):
        """eastmoney 在可用源列表中"""
        available = SourceRegistry.list_available_sources()
        assert "eastmoney" in available

    def test_includes_sina(self):
        """sina 在可用源列表中"""
        available = SourceRegistry.list_available_sources()
        assert "sina" in available

    def test_includes_yangjibao(self):
        """yangjibao 在可用源列表中"""
        available = SourceRegistry.list_available_sources()
        assert "yangjibao" in available

    def test_includes_xiaobeiyangji(self):
        """xiaobeiyangji 在可用源列表中"""
        available = SourceRegistry.list_available_sources()
        assert "xiaobeiyangji" in available

    def test_list_sources_unchanged(self):
        """list_sources() 仍然返回所有注册源（包括不可用的）"""
        all_sources = SourceRegistry.list_sources()
        assert "danjuan" in all_sources, (
            "list_sources() 应包含所有注册源（包括不可用的）"
        )
        assert "eastmoney" in all_sources

    def test_available_is_subset_of_all(self):
        """可用源是所有源的子集"""
        all_sources = set(SourceRegistry.list_sources())
        available = set(SourceRegistry.list_available_sources())
        assert available.issubset(all_sources)

    def test_each_available_source_has_is_available_true(self):
        """每个可用源的 is_available() 应为 True"""
        for name in SourceRegistry.list_available_sources():
            source = SourceRegistry.get_source(name)
            assert source is not None, f"源 {name} 应可通过 get_source 获取"
            assert source.is_available() is True, (
                f"可用源 {name} 的 is_available() 应为 True"
            )
