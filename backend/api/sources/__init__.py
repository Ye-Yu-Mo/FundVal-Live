"""
数据源模块初始化

自动注册所有数据源
"""
from .base import BaseEstimateSource
from .eastmoney import EastMoneySource
from .sina import SinaStockSource
from .registry import SourceRegistry

# 自动注册数据源
SourceRegistry.register(EastMoneySource())
SourceRegistry.register(SinaStockSource())

__all__ = [
    'BaseEstimateSource',
    'EastMoneySource',
    'SinaStockSource',
    'SourceRegistry',
]
