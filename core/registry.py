"""ToolRegistry：工具注册表（可插拔唯一入口）"""
from typing import Callable


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._meta: dict[str, dict] = {}   # name → {desc, keywords, examples, direct_reply}

    def register(self, name: str, fn: Callable, desc: str = "",
                 keywords: list[str] | None = None,
                 examples: list[str] | None = None,
                 direct_reply: bool = False,
                 async_execution: bool = False,
                 job_timeout_sec: int = 300,
                 job_max_attempts: int = 1,
                 router_hint: str = "",
                 router_exclude: str = ""):
        """注册工具：fn 签名 (query="", **kwargs) -> str"""
        self._tools[name] = fn
        self._meta[name] = {
            "desc": desc,
            "keywords": keywords or [],
            "examples": examples or [],
            "direct_reply": direct_reply,
            "async_execution": async_execution,
            "job_timeout_sec": job_timeout_sec,
            "job_max_attempts": job_max_attempts,
            "router_hint": router_hint,
            "router_exclude": router_exclude,
        }

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
