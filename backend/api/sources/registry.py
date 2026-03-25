"""
数据源注册表
"""
from typing import Optional, List, Type
from .base import BaseEstimateSource


class SourceRegistry:
    """数据源注册表

    存储数据源的类（而非实例），每次 get_source 返回新实例，
    避免多请求共享同一实例导致 token/状态互相覆盖。
    """

    _classes: dict = {}

    @classmethod
    def register(cls, source: BaseEstimateSource):
        """注册数据源（传入实例，存储其类）"""
        name = source.get_source_name()
        cls._classes[name] = type(source)

    @classmethod
    def get_source(cls, name: str) -> Optional[BaseEstimateSource]:
        """返回新的数据源实例（每次调用都是新对象）"""
        klass = cls._classes.get(name)
        return klass() if klass else None

    @classmethod
    def list_sources(cls) -> List[str]:
        return list(cls._classes.keys())

    @classmethod
    def get_default_source(cls) -> Optional[BaseEstimateSource]:
        if cls._classes:
            return list(cls._classes.values())[0]()
        return None
