"""会话级 Job 事件总线：SSE 订阅 / 推送"""
import asyncio
from collections import defaultdict
from typing import Any

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_global_subscribers: set[asyncio.Queue] = set()
_lock = asyncio.Lock()


async def subscribe_global() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=128)
    async with _lock:
        _global_subscribers.add(q)
    return q


async def unsubscribe_global(q: asyncio.Queue) -> None:
    async with _lock:
        _global_subscribers.discard(q)


def publish_global(event: dict[str, Any]) -> None:
    for q in list(_global_subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def subscribe(session_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=64)
    async with _lock:
        _subscribers[session_id].add(q)
    return q


async def unsubscribe(session_id: str, q: asyncio.Queue) -> None:
    async with _lock:
        subs = _subscribers.get(session_id)
        if subs:
            subs.discard(q)
            if not subs:
                del _subscribers[session_id]


def publish(session_id: str, event: dict[str, Any]) -> None:
    """线程安全：可从 job 线程调用；同时广播到全局看板"""
    publish_global(event)
    subs = _subscribers.get(session_id)
    if not subs:
        return
    for q in list(subs):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def publish_async(session_id: str, event: dict[str, Any]) -> None:
    subs = _subscribers.get(session_id)
    if not subs:
        return
    for q in list(subs):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass
