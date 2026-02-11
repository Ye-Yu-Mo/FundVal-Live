"""
数据源注册表
"""
from typing import Optional, List
from .base import BaseEstimateSource


class SourceRegistry:
    """数据源注册表（单例）"""

    _sources = {}

    @classmethod
    def register(cls, source: BaseEstimateSource):
        """
        注册数据源

        Args:
            source: 数据源实例
        """
        name = source.get_source_name()
        cls._sources[name] = source

    @classmethod
    def get_source(cls, name: str) -> Optional[BaseEstimateSource]:
        """
        获取数据源

        Args:
            name: 数据源名称

        Returns:
            数据源实例，如果不存在返回 None
        """
        return cls._sources.get(name)

    @classmethod
    def list_sources(cls) -> List[str]:
        """
        列出所有数据源

        Returns:
            数据源名称列表
        """
        return list(cls._sources.keys())

    @classmethod
    def get_default_source(cls) -> Optional[BaseEstimateSource]:
        """
        获取默认数据源（第一个注册的）

        Returns:
            数据源实例
        """
        if cls._sources:
            return list(cls._sources.values())[0]
        return None
