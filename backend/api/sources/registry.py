"""
数据源注册表
"""

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
    def get_source(cls, name: str) -> BaseEstimateSource | None:
        """返回新的数据源实例（每次调用都是新对象）"""
        klass = cls._classes.get(name)
        return klass() if klass else None

    @classmethod
    def list_sources(cls) -> list[str]:
        return list(cls._classes.keys())

    @classmethod
    def list_available_sources(cls) -> list[str]:
        """返回当前可用的数据源名称列表

        M1 (2026-07-29): 遍历所有注册的源，调用 is_available() 过滤不可用源。
        每个源的 is_available() 只在此时被调用一次。
        """
        available = []
        for name, klass in cls._classes.items():
            try:
                instance = klass()
                if instance.is_available():
                    available.append(name)
            except Exception:
                # 如果实例化或检查失败，跳过该源
                continue
        return available

    @classmethod
    def get_default_source(cls) -> BaseEstimateSource | None:
        if cls._classes:
            return list(cls._classes.values())[0]()
        return None
