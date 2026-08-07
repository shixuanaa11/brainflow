"""ToolRegistry：工具注册表（可插拔唯一入口）"""
from typing import Callable


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._meta: dict[str, dict] = {}   # name → {desc, keywords, examples}

    def register(self, name: str, fn: Callable, desc: str = "",
                 keywords: list[str] | None = None,
                 examples: list[str] | None = None):
        """注册工具：fn 签名 (query="", **kwargs) -> str"""
        self._tools[name] = fn
        self._meta[name] = {"desc": desc, "keywords": keywords or [],
                            "examples": examples or []}

    def get(self, name: str) -> Callable | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def meta(self, name: str) -> dict:
        return self._meta.get(name, {})


_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
