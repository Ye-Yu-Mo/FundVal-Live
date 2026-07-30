"""
测试 AkshareEstimateEngine (M2 功能1)

验证点:
- _load_all_estimates 缓存 DataFrame
- get_estimate 命中/未命中
- get_batch_estimate 部分命中
- 缓存 TTL 过期重新拉取
- 网络/akshare 异常 → 返回 None 不传播
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pandas as pd
from api.sources.akshare_estimate import AkshareEstimateEngine

# ── 辅助: 构造 akshare 估值 DataFrame ──


def _make_estimate_df(rows):
    """构造 fund_value_estimation_em 返回的 DataFrame"""
    return pd.DataFrame(rows)


def _sample_df():
    """标准 3 只基金的估值 DataFrame（模拟 akshare 1.18 列名）"""
    return _make_estimate_df(
        [
            {
                "基金代码": "000001",
                "基金名称": "华夏成长混合",
                "交易日-估算数据-估算值": 1.1370,
                "交易日-估算数据-估算增长率": "-1.05",
                "交易日-公布数据-单位净值": 1.1490,
                "交易日-单位净值": "2026-07-28",
            },
            {
                "基金代码": "000002",
                "基金名称": "华夏成长后端",
                "交易日-估算数据-估算值": 2.3456,
                "交易日-估算数据-估算增长率": "0.50",
                "交易日-公布数据-单位净值": 2.3300,
                "交易日-单位净值": "2026-07-28",
            },
            {
                "基金代码": "161725",
                "基金名称": "招商中证白酒",
                "交易日-估算数据-估算值": 1.8900,
                "交易日-估算数据-估算增长率": "2.10",
                "交易日-公布数据-单位净值": 1.8500,
                "交易日-单位净值": "2026-07-28",
            },
        ]
    )


# ================================================================
# _load_all_estimates — 缓存 + 异常处理
# ================================================================


class TestLoadAllEstimates:
    """_load_all_estimates 批量拉取 + 缓存"""

    def test_returns_dataframe_from_akshare(self):
        """正常调 akshare 返回 DataFrame"""
        engine = AkshareEstimateEngine()

        with (
            patch.object(
                engine, "_load_all_estimates", wraps=engine._load_all_estimates
            ) as wrapped,
            patch("akshare.fund_value_estimation_em") as mock_ak,
        ):
            mock_ak.return_value = _sample_df()

            df = engine._load_all_estimates()

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert len(df) == 3
        mock_ak.assert_called_once()

    def test_cached_within_ttl(self):
        """5 分钟内不重复调 akshare"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = _sample_df()

            df1 = engine._load_all_estimates()
            df2 = engine._load_all_estimates()  # 应走缓存

        assert df1 is df2, "缓存命中应返回同一对象"
        mock_ak.assert_called_once()  # 只调一次

    def test_cache_expired_after_ttl(self):
        """TTL 过后重新拉取"""
        engine = AkshareEstimateEngine()
        ttl = engine._cache_ttl

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.side_effect = [_sample_df(), _sample_df()]  # 每次返回新 DataFrame

            df1 = engine._load_all_estimates()
            # 模拟时间流逝
            engine._last_fetch_time -= timedelta(seconds=ttl + 10)
            df2 = engine._load_all_estimates()  # 缓存过期

        assert df1 is not df2, "缓存过期应重新拉取"
        assert mock_ak.call_count == 2

    def test_returns_empty_df_on_network_error(self):
        """网络异常 → 返回空 DataFrame，不抛异常"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.side_effect = ConnectionError("network down")

            df = engine._load_all_estimates()

        assert isinstance(df, pd.DataFrame)
        assert df.empty, "异常应返回空 DataFrame"

    def test_returns_empty_df_when_akshare_returns_none(self):
        """akshare 返回 None → 返回空 DataFrame"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = None

            df = engine._load_all_estimates()

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_refresh_cache_clears_cache(self):
        """_refresh_cache 强制清除缓存"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = _sample_df()

            engine._load_all_estimates()
            assert mock_ak.call_count == 1

            engine._refresh_cache()
            engine._load_all_estimates()
            assert mock_ak.call_count == 2, "刷新后应重新拉取"


# ================================================================
# get_estimate — 单只基金估值
# ================================================================


class TestGetEstimate:
    """get_estimate 单只估值"""

    def test_found_returns_correct_format(self):
        """基金存在 → 返回标准 dict"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = _sample_df()

            result = engine.get_estimate("000001")

        assert result is not None
        assert result["fund_code"] == "000001"
        assert result["fund_name"] == "华夏成长混合"
        assert result["estimate_nav"] == Decimal("1.1370")
        assert result["estimate_growth"] == Decimal("-1.05")
        assert isinstance(result["estimate_time"], datetime)

    def test_not_found_returns_none(self):
        """基金代码不在 DataFrame 中 → 返回 None"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = _sample_df()

            result = engine.get_estimate("999999")

        assert result is None

    def test_empty_dataframe_returns_none(self):
        """空 DataFrame → 返回 None"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = pd.DataFrame()

            result = engine.get_estimate("000001")

        assert result is None

    def test_missing_column_handled(self):
        """DataFrame 缺少必需列（基金代码 或估算值）→ 返回 None + 日志"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = pd.DataFrame([{"wrong_column": "x"}])

            result = engine.get_estimate("000001")

        assert result is None, "缺少必需列应返回 None"

    def test_does_not_cache_after_error(self):
        """上次拉取失败后可以重试（不保留空缓存）"""
        engine = AkshareEstimateEngine()
        engine._refresh_cache()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            # 第一次失败
            mock_ak.side_effect = ConnectionError("fail")
            result1 = engine.get_estimate("000001")
            assert result1 is None

            # 第二次成功
            mock_ak.side_effect = None
            mock_ak.return_value = _sample_df()
            engine._refresh_cache()  # 强制刷新
            result2 = engine.get_estimate("000001")
            assert result2 is not None

    def test_compatible_with_old_column_names(self):
        """兼容旧版 akshare 列名（估算值, 估算增长率）"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = _make_estimate_df(
                [
                    {
                        "基金代码": "000001",
                        "基金名称": "旧格式",
                        "估算值": 1.2345,
                        "估算增长率": "0.50",
                    },
                ]
            )

            result = engine.get_estimate("000001")

        assert result is not None
        assert result["estimate_nav"] == Decimal("1.2345")
        assert result["estimate_growth"] == Decimal("0.50")


# ================================================================
# get_batch_estimate — 批量估值
# ================================================================


class TestGetBatchEstimate:
    """get_batch_estimate 批量估值"""

    def test_all_found(self):
        """全部命中"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = _sample_df()

            results = engine.get_batch_estimate(["000001", "161725"])

        assert len(results) == 2
        assert results["000001"] is not None
        assert results["161725"] is not None
        assert results["000001"]["estimate_nav"] == Decimal("1.1370")

    def test_partial_found(self):
        """部分命中，部分不存在"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = _sample_df()

            results = engine.get_batch_estimate(["000001", "999999"])

        assert results["000001"] is not None
        assert results["999999"] is None

    def test_all_miss(self):
        """全部不存在"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = _sample_df()

            results = engine.get_batch_estimate(["888888", "999999"])

        assert results["888888"] is None
        assert results["999999"] is None

    def test_uses_single_akshare_call(self):
        """批量获取只调一次 akshare"""
        engine = AkshareEstimateEngine()

        with patch("akshare.fund_value_estimation_em") as mock_ak:
            mock_ak.return_value = _sample_df()

            engine.get_batch_estimate(["000001", "000002", "161725"])

        mock_ak.assert_called_once()
