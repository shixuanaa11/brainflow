"""指标收集（线程安全）"""
import threading
import time
from collections import defaultdict

_lock = threading.Lock()


class StatsCollector:
    def __init__(self):
        self.calls = 0
        self.errors = 0
        self.tokens = 0
        self.by_tool: dict[str, int] = defaultdict(int)
        self.by_tool_tokens: dict[str, int] = defaultdict(int)
        self.recent: list[dict] = []

    def record(self, tool_name: str, tokens: int = 0, error: str = "",
               latency: float = 0.0, user_id: str = ""):
        with _lock:
            self.calls += 1
            self.tokens += tokens
            self.by_tool[tool_name] += 1
            self.by_tool_tokens[tool_name] += tokens
            if error:
                self.errors += 1
            self.recent.append({"tool": tool_name, "tokens": tokens, "error": error,
                                "latency": latency, "user": user_id, "time": time.time()})
            self.recent = self.recent[-200:]

    def summary(self) -> dict:
        with _lock:
            return {"total_calls": self.calls, "total_tokens": self.tokens,
                    "total_errors": self.errors,
                    "by_tool": dict(self.by_tool),
                    "by_tool_tokens": dict(self.by_tool_tokens)}

    def recent_logs(self, n: int = 50) -> list[dict]:
        with _lock:
            return list(self.recent[-n:])


_stats: StatsCollector | None = None


def get_stats() -> StatsCollector:
    global _stats
    if _stats is None:
        _stats = StatsCollector()
    return _stats
