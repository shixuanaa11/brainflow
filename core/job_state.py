"""Tool Job 状态机（数据层 + 操作层共用）"""
from typing import Final

ACTIVE_STATUSES: Final[frozenset[str]] = frozenset({"queued", "submitted", "running"})
TERMINAL_STATUSES: Final[frozenset[str]] = frozenset({"done", "error", "timeout", "cancelled"})

# 合法状态迁移：from -> {to, ...}
TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "queued": frozenset({"submitted", "cancelled"}),
    "submitted": frozenset({"running", "cancelled"}),
    "running": frozenset({"done", "error", "timeout", "cancelled", "submitted"}),
    "done": frozenset(),
    "error": frozenset(),
    "timeout": frozenset(),
    "cancelled": frozenset(),
}


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in TRANSITIONS.get(from_status, frozenset())


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def is_active(status: str) -> bool:
    return status in ACTIVE_STATUSES
