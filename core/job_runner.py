"""Job Worker：后台执行、租约、并发控制、超时；终态投递走 outbox"""
import asyncio
import json
import time
import uuid
from typing import Callable

from core.job_state import is_terminal
from core.logs import get_logger
from core.stats import get_stats
from core.tool_jobs import JobTransitionError, get_tool_jobs
from core.tracing import get_tracer

log = get_logger("job_runner")

WORKER_ID = f"worker_{uuid.uuid4().hex[:8]}"
MAX_CONCURRENT_JOBS = 5
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
    return _semaphore


def _trace_context(job: dict):
    trace_id = job.get("trace_id") or ""
    if not trace_id:
        return
    tracer = get_tracer()
    tracer._current = {
        "id": trace_id,
        "workflow": "agent",
        "input": job.get("user_query", ""),
        "user": job.get("session_id", ""),
        "t0": job.get("created_at", time.time()),
    }


async def execute_job(job_id: str, fn: Callable, user_query: str, timeout_sec: int) -> None:
    from core.job_service import get_job_service

    store = get_tool_jobs()
    svc = get_job_service()

    async with _get_semaphore():
        job = store.claim(job_id, WORKER_ID)
        if not job:
            return

        tool_name = job["tool_name"]
        t0 = time.time()
        _trace_context(job)
        get_tracer().set_current_node(f"tool_{tool_name}")
        svc.notify_live(job)

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(fn, query=user_query),
                timeout=timeout_sec,
            )
            result = str(result)
            db_result, result_ref = svc.prepare_done_result(job_id, result)
            elapsed = time.time() - t0
            job = store.transition(
                job_id, "done", progress=100,
                result=db_result, result_ref=result_ref or None,
            )
            get_stats().record(tool_name, latency=elapsed)
            get_tracer().add_span(
                f"tool_{tool_name}", "tool", elapsed,
                status="ok", input_text=user_query, output_text=db_result[:500],
                detail=f"async job {job_id}",
            )
            svc.schedule_terminal_delivery(job, user_query)
            log.info(json.dumps({
                "event": "job_done", "job_id": job_id, "tool": tool_name,
            }, ensure_ascii=False))

        except asyncio.TimeoutError:
            err = f"任务超时（>{timeout_sec}s）"
            job = store.transition(
                job_id, "timeout", progress=100, error=err,
                event_type="timeout",
            )
            get_stats().record(tool_name, error=err)
            svc.schedule_terminal_delivery(job, user_query)
            log.warning(f"job {job_id} timeout")

        except JobTransitionError as e:
            log.warning(f"job {job_id} transition error: {e}")

        except Exception as e:
            err = str(e)
            job = store.get(job_id)
            try:
                if job and not is_terminal(job["status"]):
                    job = store.transition(
                        job_id, "error", progress=100, error=err,
                    )
            except JobTransitionError:
                job = store.get(job_id)
            get_stats().record(tool_name, error=err)
            get_tracer().add_span(
                f"tool_{tool_name}", "tool", time.time() - t0,
                status="error", detail=err, input_text=user_query,
            )
            if job:
                svc.schedule_terminal_delivery(job, user_query)
            log.warning(f"job {job_id} failed: {e}")


def schedule_job_execution(
    job_id: str,
    fn: Callable,
    user_query: str,
    timeout_sec: int = 300,
) -> None:
    coro = execute_job(job_id, fn, user_query, timeout_sec)

    async def _run():
        job = get_tool_jobs().get(job_id)
        if not job or is_terminal(job["status"]):
            return
        await coro

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())


schedule_job = schedule_job_execution
