# -*- coding: utf-8 -*-
"""
自定义估值算法模块
用于在 API 无法获取估值时，基于历史数据计算估值
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def estimate_with_weighted_ma(history: List[Dict], weights: List[float] = None) -> Optional[Dict[str, float]]:
    """
    移动加权平均估值算法

    原理：
    - 基于近期涨跌幅的加权平均预测今日涨跌幅
    - 越近的数据权重越大
    - 适合短期趋势预测

    Args:
        history: 历史净值数据（按日期升序），格式：[{"date": "2024-01-01", "nav": 1.234}, ...]
        weights: 权重列表，默认 [0.4, 0.3, 0.2, 0.07, 0.03]（近5日）

    Returns:
        {
            "estimate": 估值,
            "est_rate": 估值涨跌幅(%),
            "confidence": 置信度(0-1),
            "method": "weighted_ma"
        }
        如果数据不足，返回 None
    """
    if not history or len(history) < 2:
        logger.warning("History data insufficient for estimation (need at least 2 days)")
        return None

    # 默认权重：近5日，越近权重越大
    weights = weights or [0.4, 0.3, 0.2, 0.07, 0.03]
    n = min(len(weights), len(history) - 1)

    if n < 2:
        logger.warning("Not enough history for weighted MA (need at least 2 days)")
        return None

    try:
        # 计算近n日涨跌幅
        changes = []
        for i in range(1, n + 1):
            current_nav = float(history[-i]["nav"])
            prev_nav = float(history[-i-1]["nav"])
            change = (current_nav - prev_nav) / prev_nav * 100
            changes.append(change)

        # 加权平均
        weighted_sum = sum(changes[i] * weights[i] for i in range(n))
        weight_total = sum(weights[:n])
        weighted_change = weighted_sum / weight_total

        # 预测今日估值
        yesterday_nav = float(history[-1]["nav"])
        estimated_nav = yesterday_nav * (1 + weighted_change / 100)

        # 计算置信度（基于数据量和波动率）
        confidence = min(n / len(weights), 1.0)  # 数据越多置信度越高
        volatility = sum(abs(c) for c in changes) / n  # 平均波动率
        if volatility > 3.0:  # 高波动降低置信度
            confidence *= 0.8

        return {
            "estimate": round(estimated_nav, 4),
            "est_rate": round(weighted_change, 2),
            "confidence": round(confidence, 2),
            "method": "weighted_ma"
        }

    except (KeyError, ValueError, ZeroDivisionError) as e:
        logger.error(f"Error calculating weighted MA estimate: {e}")
        return None


def estimate_with_simple_ma(history: List[Dict], days: int = 5) -> Optional[Dict[str, float]]:
    """
    简单移动平均估值算法（兜底方案）

    原理：
    - 计算近N日平均涨跌幅
    - 所有日期权重相同

    Args:
        history: 历史净值数据
        days: 移动平均天数

    Returns:
        估值结果字典，格式同 estimate_with_weighted_ma
    """
    if not history or len(history) < 2:
        return None

    n = min(days, len(history) - 1)

    try:
        # 计算近n日涨跌幅
        changes = []
        for i in range(1, n + 1):
            current_nav = float(history[-i]["nav"])
            prev_nav = float(history[-i-1]["nav"])
            change = (current_nav - prev_nav) / prev_nav * 100
            changes.append(change)

        # 简单平均
        avg_change = sum(changes) / len(changes)

        # 预测今日估值
        yesterday_nav = float(history[-1]["nav"])
        estimated_nav = yesterday_nav * (1 + avg_change / 100)

        return {
            "estimate": round(estimated_nav, 4),
            "est_rate": round(avg_change, 2),
            "confidence": 0.6,  # 简单平均置信度较低
            "method": "simple_ma"
        }

    except (KeyError, ValueError, ZeroDivisionError) as e:
        logger.error(f"Error calculating simple MA estimate: {e}")
        return None


def estimate_nav(code: str, history: List[Dict]) -> Optional[Dict[str, float]]:
    """
    智能估值入口函数

    根据历史数据量自动选择最佳算法：
    - 数据充足（>=5天）：使用加权移动平均
    - 数据较少（2-4天）：使用简单移动平均
    - 数据不足（<2天）：返回 None

    Args:
        code: 基金代码
        history: 历史净值数据

    Returns:
        估值结果字典
    """
    if not history or len(history) < 2:
        logger.info(f"Fund {code}: insufficient history for estimation")
        return None

    # 优先使用加权移动平均
    if len(history) >= 5:
        result = estimate_with_weighted_ma(history)
        if result:
            logger.info(f"Fund {code}: estimated using weighted MA, confidence={result['confidence']}")
            return result

    # 兜底：简单移动平均
    result = estimate_with_simple_ma(history)
    if result:
        logger.info(f"Fund {code}: estimated using simple MA (fallback)")
        return result

    return None
