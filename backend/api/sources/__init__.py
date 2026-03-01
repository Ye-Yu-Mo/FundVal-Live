"""
数据源模块初始化

自动注册所有数据源
"""
from .base import BaseEstimateSource
from .eastmoney import EastMoneySource
from .sina import SinaStockSource
from .yangjibao import YangJiBaoSource
from .registry import SourceRegistry

# 自动注册数据源
SourceRegistry.register(EastMoneySource())
SourceRegistry.register(SinaStockSource())
SourceRegistry.register(YangJiBaoSource())

__all__ = [
    'BaseEstimateSource',
    'EastMoneySource',
    'SinaStockSource',
    'YangJiBaoSource',
    'SourceRegistry',
]
