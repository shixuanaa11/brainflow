"""Job 操作层：submit / cancel / recovery / outbox 投递 / SSE replay"""
import asyncio
import json
import time

from core.chat_history import get_chat_history
from core.job_bus import publish
from core.job_delivery import (
    build_chat_error_update_payload,
    build_chat_result_update_payload,
    persist_large_result,
)
from core.job_outbox import get_job_outbox
from core.job_state import is_terminal
from core.logs import get_logger
from core.registry import get_registry
from core.tool_jobs import JobTransitionError, get_tool_jobs

log = get_logger("job_service")

OUTBOX_POLL_SEC = 1.0


def job_event_from_row(job: dict, event_type: str = "job") -> dict:
    evt = {
        "type": event_type,
        "job_id": job["job_id"],
        "session_id": job["session_id"],
        "tool": job["tool_name"],
        "status": job["status"],
        "progress": job.get("progress", 0),
        "result": job.get("result") or "",
        "error": job.get("error") or "",
        "attempt": job.get("attempt", 0),
    }
    if job.get("result_ref"):
        evt["result_ref"] = job["result_ref"]
    evt["ts"] = job.get("updated_at") or time.time()
    return evt


def sse_type_for_status(status: str) -> str:
    if status == "done":
        return "job_done"
    if status in ("error", "timeout", "cancelled"):
        return "job_error"
    return "job"


def replay_events_as_sse(events: list[dict], jobs_by_id: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    for ev in events:
        job = jobs_by_id.get(ev["job_id"])
        if not job:
            continue
        to_status = ev.get("to_status") or job["status"]
        if to_status not in ("submitted", "running", "done", "error", "timeout", "cancelled"):
            continue
        evt_type = sse_type_for_status(to_status) if is_terminal(to_status) else "job"
        if ev.get("event_type") in ("claimed", "requeue"):
            evt_type = "job"
        payload = {
            **job_event_from_row({**job, "status": to_status}, evt_type),
            "type": evt_type,
            "replay": True,
            "event_id": ev.get("id"),
            "ts": ev.get("created_at"),
        }
        out.append(payload)
    return out


class JobService:
    def __init__(self):
        self._store = get_tool_jobs()
        self._outbox = get_job_outbox()
        self._started = False
        self._outbox_task: asyncio.Task | None = None

    async def start(self, *, run_outbox_loop: bool = True) -> None:
        if self._started:
            return
        self._started = True
        self._outbox.reset_stale_processing()
        n = await self.recover_stale_jobs()
        if n:
            log.info(json.dumps({"event": "job_recovery", "count": n}, ensure_ascii=False))
        processed = await self.process_outbox_batch()
        if processed:
            log.info(json.dumps({"event": "outbox_flush", "count": processed}, ensure_ascii=False))
        if run_outbox_loop:
            self._outbox_task = asyncio.create_task(self._outbox_loop())

    async def stop(self) -> None:
        if self._outbox_task:
            self._outbox_task.cancel()
            try:
                await self._outbox_task
            except asyncio.CancelledError:
                pass
            self._outbox_task = None

    async def _outbox_loop(self) -> None:
        while True:
            try:
                await self.process_outbox_batch()
            except Exception as e:
                log.warning(f"outbox loop error: {e}")
            await asyncio.sleep(OUTBOX_POLL_SEC)

    async def process_outbox_batch(self) -> int:
        done = 0
        for item in self._outbox.claim_pending():
            try:
                self._deliver_outbox_item(item)
                self._outbox.mark_done(item["id"])
                done += 1
            except Exception as e:
                if item["attempts"] >= 5:
                    self._outbox.mark_dead(item["id"], str(e))
                    log.error(f"outbox {item['id']} dead: {e}")
                else:
                    self._outbox.mark_failed(item["id"], str(e))
        return done

    def _deliver_outbox_item(self, item: dict) -> None:
        kind = item["kind"]
        payload = item["payload"]
        if kind == "chat":
            get_chat_history().append_messages(
                payload["session_id"], payload["messages"],
            )
        elif kind == "chat_update":
            hist = get_chat_history()
            updated = hist.update_assistant_by_job_id(
                payload["session_id"],
                payload["job_id"],
                payload["content"],
                payload.get("meta"),
            )
            if not updated:
                hist.append_messages(payload["session_id"], [{
                    "role": "assistant",
                    "content": payload["content"],
                    "meta": payload.get("meta"),
                }])
        elif kind == "sse":
            publish(payload["session_id"], payload["event"])
        else:
            raise ValueError(f"unknown outbox kind: {kind}")

    def schedule_terminal_delivery(self, job: dict, user_query: str) -> None:
        session_id = job["session_id"]
        status = job["status"]
        tool = job["tool_name"]
        job_id = job["job_id"]

        if status == "done":
            chat_payload = build_chat_result_update_payload(
                session_id, job_id, tool, user_query,
                job.get("result") or "",
                job.get("result_ref") or "",
            )
        else:
            err = job.get("error") or status
            chat_payload = build_chat_error_update_payload(
                session_id, job_id, tool, err, status=status,
            )

        evt_type = sse_type_for_status(status)
        sse_payload = {
            "session_id": session_id,
            "event": job_event_from_row(job, evt_type),
        }
        sse_payload["event"]["type"] = evt_type

        self._outbox.enqueue(job_id, "chat_update", chat_payload)
        self._outbox.enqueue(job_id, "sse", sse_payload)

    def submit(
        self,
        *,
        tool_name: str,
        session_id: str,
        user_query: str,
        trace_id: str = "",
    ) -> dict:
        reg = get_registry()
        fn = reg.get(tool_name)
        if not fn:
            raise ValueError(f"tool not found: {tool_name}")

        meta = reg.meta(tool_name)
        job = self._store.create(
            session_id=session_id,
            tool_name=tool_name,
            user_query=user_query,
            trace_id=trace_id,
            max_attempts=int(meta.get("job_max_attempts", 1)),
        )
        if session_id:
            from core.chat_history import get_chat_history
            from core.job_delivery import build_async_submit_message
            get_chat_history().append_messages(
                session_id,
                [build_async_submit_message(
                    tool_name, job["job_id"], user_query,
                )],
            )
        self.notify_live(job)
        from core.job_runner import schedule_job_execution
        schedule_job_execution(
            job_id=job["job_id"],
            fn=fn,
            user_query=user_query,
            timeout_sec=int(meta.get("job_timeout_sec", 300)),
        )
        return job

    def cancel(self, job_id: str) -> dict | None:
        job = self._store.get(job_id)
        if not job or is_terminal(job["status"]):
            return job
        try:
            job = self._store.transition(
                job_id, "cancelled",
                progress=100,
                error="用户取消",
                event_type="cancelled",
            )
            self.schedule_terminal_delivery(job, job.get("user_query") or "")
            return job
        except JobTransitionError as e:
            log.warning(f"cancel {job_id} failed: {e}")
            return self._store.get(job_id)

    async def recover_stale_jobs(self) -> int:
        reg = get_registry()
        count = 0
        for job in self._store.list_stale():
            fn = reg.get(job["tool_name"])
            if not fn:
                try:
                    j = self._store.transition(
                        job["job_id"], "error",
                        error=f"tool {job['tool_name']} not registered",
                        event_type="recovery_error",
                    )
                    self.schedule_terminal_delivery(j, job.get("user_query") or "")
                except JobTransitionError:
                    pass
                continue
            if (job.get("attempt") or 0) >= (job.get("max_attempts") or 1):
                try:
                    j = self._store.transition(
                        job["job_id"], "error",
                        error="超过最大重试次数",
                        event_type="recovery_exhausted",
                    )
                    self.schedule_terminal_delivery(j, job.get("user_query") or "")
                except JobTransitionError:
                    pass
                continue
            try:
                if job["status"] == "running":
                    self._store.transition(
                        job["job_id"], "submitted",
                        event_type="requeue",
                        payload={"reason": "lease_expired"},
                    )
                from core.job_runner import schedule_job_execution
                schedule_job_execution(
                    job_id=job["job_id"],
                    fn=fn,
                    user_query=job["user_query"],
                    timeout_sec=int(reg.meta(job["tool_name"]).get("job_timeout_sec", 300)),
                )
                count += 1
            except JobTransitionError as e:
                log.warning(f"recover {job['job_id']}: {e}")
        return count

    def notify_live(self, job: dict, event_type: str = "job") -> None:
        evt = job_event_from_row(job, event_type)
        if event_type == "job_done":
            evt["type"] = "job_done"
        elif event_type == "job_error":
            evt["type"] = "job_error"
        else:
            evt["type"] = "job"
        publish(job["session_id"], evt)

    def get(self, job_id: str) -> dict | None:
        return self._store.get(job_id)

    def list_events(self, job_id: str, since: float = 0) -> list[dict]:
        return self._store.list_events(job_id, since)

    def replay_session_sse(self, session_id: str, since: float) -> list[dict]:
        events = self._store.list_events_for_session(session_id, since)
        job_ids = {e["job_id"] for e in events}
        jobs_by_id = {
            jid: self._store.get(jid)
            for jid in job_ids
            if self._store.get(jid)
        }
        return replay_events_as_sse(events, jobs_by_id)

    def replay_global_sse(self, since: float) -> list[dict]:
        events = self._store.list_events_global(since)
        job_ids = {e["job_id"] for e in events}
        jobs_by_id = {
            jid: self._store.get(jid)
            for jid in job_ids
            if self._store.get(jid)
        }
        return replay_events_as_sse(events, jobs_by_id)

    def prepare_done_result(self, job_id: str, raw_result: str) -> tuple[str, str]:
        return persist_large_result(job_id, raw_result)


_service: JobService | None = None


def get_job_service() -> JobService:
    global _service
    if _service is None:
        _service = JobService()
    return _service
