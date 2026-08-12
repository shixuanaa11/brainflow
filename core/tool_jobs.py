"""Tool Job 持久化：Repository 层（状态机约束 + 事件审计）"""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from config.settings import DB_DIR
from core.job_state import (
    ACTIVE_STATUSES,
    can_transition,
    is_terminal,
)

_lock = threading.Lock()
DB_JOBS = str(DB_DIR / "tool_jobs.db")

DEFAULT_LEASE_SEC = 300


class JobTransitionError(Exception):
    """非法状态迁移"""


class ToolJobStore:
    def __init__(self, db_path: str = DB_JOBS):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self):
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS tool_jobs (
                    job_id TEXT PRIMARY KEY,
                    trace_id TEXT,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    input TEXT,
                    result TEXT,
                    error TEXT,
                    user_query TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    finished_at REAL
                );
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT,
                    payload TEXT,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tool_jobs_session
                    ON tool_jobs(session_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_tool_jobs_status
                    ON tool_jobs(status, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_job_events_job
                    ON job_events(job_id, created_at);
            """)
            cols = {r[1] for r in self._conn.execute("PRAGMA table_info(tool_jobs)").fetchall()}
            for col, ddl in [
                ("attempt", "INTEGER DEFAULT 0"),
                ("max_attempts", "INTEGER DEFAULT 1"),
                ("worker_id", "TEXT"),
                ("lease_expires_at", "REAL"),
                ("result_ref", "TEXT"),
            ]:
                if col not in cols:
                    self._conn.execute(f"ALTER TABLE tool_jobs ADD COLUMN {col} {ddl}")

    def create(self, *, session_id: str, tool_name: str, user_query: str,
               trace_id: str = "", input_text: str = "",
               max_attempts: int = 1) -> dict:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = time.time()
        row = {
            "job_id": job_id,
            "trace_id": trace_id,
            "session_id": session_id,
            "tool_name": tool_name,
            "status": "submitted",
            "progress": 0,
            "input": input_text or user_query,
            "result": "",
            "error": "",
            "user_query": user_query,
            "created_at": now,
            "updated_at": now,
            "finished_at": None,
            "attempt": 0,
            "max_attempts": max(1, max_attempts),
            "worker_id": "",
            "lease_expires_at": None,
        }
        with _lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO tool_jobs "
                    "(job_id, trace_id, session_id, tool_name, status, progress, "
                    "input, result, error, user_query, created_at, updated_at, finished_at, "
                    "attempt, max_attempts, worker_id, lease_expires_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        row["job_id"], row["trace_id"], row["session_id"],
                        row["tool_name"], row["status"], row["progress"],
                        row["input"], row["result"], row["error"],
                        row["user_query"], row["created_at"], row["updated_at"],
                        row["finished_at"], row["attempt"], row["max_attempts"],
                        row["worker_id"], row["lease_expires_at"],
                    ),
                )
                self._append_event_locked(
                    job_id, "submitted", None, "submitted",
                    {"tool": tool_name}, now,
                )
        return row

    def transition(
        self,
        job_id: str,
        to_status: str,
        *,
        progress: int | None = None,
        result: str | None = None,
        error: str | None = None,
        worker_id: str | None = None,
        lease_expires_at: float | None = None,
        attempt: int | None = None,
        result_ref: str | None = None,
        event_type: str | None = None,
        payload: dict | None = None,
    ) -> dict:
        job = self.get(job_id)
        if not job:
            raise JobTransitionError(f"job {job_id} not found")
        from_status = job["status"]
        if not can_transition(from_status, to_status):
            raise JobTransitionError(
                f"invalid transition {from_status} -> {to_status} for {job_id}"
            )

        now = time.time()
        updates: dict = {"status": to_status, "updated_at": now}
        if progress is not None:
            updates["progress"] = progress
        if result is not None:
            updates["result"] = result
        if error is not None:
            updates["error"] = error
        if worker_id is not None:
            updates["worker_id"] = worker_id
        if lease_expires_at is not None:
            updates["lease_expires_at"] = lease_expires_at
        if attempt is not None:
            updates["attempt"] = attempt
        if result_ref is not None:
            updates["result_ref"] = result_ref
        if is_terminal(to_status):
            updates["finished_at"] = now
            updates["lease_expires_at"] = None
            updates["worker_id"] = ""

        cols = ", ".join(f"{k}=?" for k in updates)
        with _lock:
            with self._conn:
                self._conn.execute(
                    f"UPDATE tool_jobs SET {cols} WHERE job_id=?",
                    (*updates.values(), job_id),
                )
                self._append_event_locked(
                    job_id,
                    event_type or to_status,
                    from_status,
                    to_status,
                    payload,
                    now,
                )
        return self.get(job_id) or job

    def claim(self, job_id: str, worker_id: str, lease_sec: int = DEFAULT_LEASE_SEC) -> dict | None:
        job = self.get(job_id)
        if not job or job["status"] not in {"submitted", "running"}:
            return None
        now = time.time()
        lease = job.get("lease_expires_at")
        if job["status"] == "running" and lease and lease > now:
            if job.get("worker_id") and job["worker_id"] != worker_id:
                return None
        try:
            return self.transition(
                job_id,
                "running",
                progress=max(job.get("progress") or 0, 10),
                worker_id=worker_id,
                lease_expires_at=now + lease_sec,
                attempt=(job.get("attempt") or 0) + 1,
                event_type="claimed",
                payload={"worker_id": worker_id},
            )
        except JobTransitionError:
            return None

    def list_stale(self, limit: int = 50) -> list[dict]:
        now = time.time()
        placeholders = ",".join("?" * len(ACTIVE_STATUSES))
        sql = (
            "SELECT job_id, trace_id, session_id, tool_name, status, progress, "
            "input, result, error, user_query, created_at, updated_at, finished_at, "
            "attempt, max_attempts, worker_id, lease_expires_at, result_ref "
            f"FROM tool_jobs WHERE status IN ({placeholders}) "
            "AND (lease_expires_at IS NULL OR lease_expires_at < ?) "
            "ORDER BY updated_at ASC LIMIT ?"
        )
        with self._conn:
            rows = self._conn.execute(sql, (*ACTIVE_STATUSES, now, limit)).fetchall()
        return [self._row(r) for r in rows]

    def get(self, job_id: str) -> dict | None:
        with self._conn:
            row = self._conn.execute(
                "SELECT job_id, trace_id, session_id, tool_name, status, progress, "
                "input, result, error, user_query, created_at, updated_at, finished_at, "
                "attempt, max_attempts, worker_id, lease_expires_at, result_ref "
                "FROM tool_jobs WHERE job_id=?", (job_id,),
            ).fetchone()
        return self._row(row) if row else None

    def list_for_session(self, session_id: str, active_only: bool = False) -> list[dict]:
        sql = (
            "SELECT job_id, trace_id, session_id, tool_name, status, progress, "
            "input, result, error, user_query, created_at, updated_at, finished_at, "
            "attempt, max_attempts, worker_id, lease_expires_at, result_ref "
            "FROM tool_jobs WHERE session_id=? "
        )
        if active_only:
            placeholders = ",".join("?" * len(ACTIVE_STATUSES))
            sql += f"AND status IN ({placeholders}) "
            params: tuple = (session_id, *ACTIVE_STATUSES)
        else:
            params = (session_id,)
        sql += "ORDER BY created_at DESC LIMIT 50"
        with self._conn:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row(r) for r in rows]

    def list_recent(
        self,
        limit: int = 100,
        active_only: bool = False,
        status: str | None = None,
    ) -> list[dict]:
        sql = (
            "SELECT job_id, trace_id, session_id, tool_name, status, progress, "
            "input, result, error, user_query, created_at, updated_at, finished_at, "
            "attempt, max_attempts, worker_id, lease_expires_at, result_ref "
            "FROM tool_jobs WHERE 1=1 "
        )
        params: list = []
        if active_only:
            placeholders = ",".join("?" * len(ACTIVE_STATUSES))
            sql += f"AND status IN ({placeholders}) "
            params.extend(ACTIVE_STATUSES)
        if status:
            sql += "AND status=? "
            params.append(status)
        sql += "ORDER BY updated_at DESC LIMIT ?"
        params.append(min(limit, 200))
        with self._conn:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row(r) for r in rows]

    def list_events(self, job_id: str, since: float = 0) -> list[dict]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT id, job_id, event_type, from_status, to_status, payload, created_at "
                "FROM job_events WHERE job_id=? AND created_at>=? ORDER BY created_at, id",
                (job_id, since),
            ).fetchall()
        return [self._event_row(r) for r in rows]

    def list_events_for_session(self, session_id: str, since: float = 0) -> list[dict]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT e.id, e.job_id, e.event_type, e.from_status, e.to_status, "
                "e.payload, e.created_at "
                "FROM job_events e "
                "JOIN tool_jobs j ON j.job_id=e.job_id "
                "WHERE j.session_id=? AND e.created_at>=? "
                "ORDER BY e.created_at, e.id",
                (session_id, since),
            ).fetchall()
        return [self._event_row(r) for r in rows]

    def list_events_global(self, since: float = 0, limit: int = 200) -> list[dict]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT id, job_id, event_type, from_status, to_status, payload, created_at "
                "FROM job_events WHERE created_at>=? ORDER BY created_at DESC LIMIT ?",
                (since, limit),
            ).fetchall()
        return [self._event_row(r) for r in reversed(rows)]

    def summary(self) -> dict:
        with self._conn:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) FROM tool_jobs GROUP BY status",
            ).fetchall()
        by_status = {r[0]: r[1] for r in rows}
        active = sum(by_status.get(s, 0) for s in ACTIVE_STATUSES)
        return {
            "total": sum(by_status.values()),
            "active": active,
            "by_status": by_status,
        }

    def _append_event_locked(
        self,
        job_id: str,
        event_type: str,
        from_status: str | None,
        to_status: str | None,
        payload: dict | None,
        ts: float,
    ) -> None:
        self._conn.execute(
            "INSERT INTO job_events "
            "(job_id, event_type, from_status, to_status, payload, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                job_id,
                event_type,
                from_status,
                to_status,
                json.dumps(payload, ensure_ascii=False) if payload else None,
                ts,
            ),
        )

    @staticmethod
    def _row(r) -> dict:
        return {
            "job_id": r[0],
            "trace_id": r[1],
            "session_id": r[2],
            "tool_name": r[3],
            "status": r[4],
            "progress": r[5] or 0,
            "input": r[6] or "",
            "result": r[7] or "",
            "error": r[8] or "",
            "user_query": r[9] or "",
            "created_at": r[10],
            "updated_at": r[11],
            "finished_at": r[12],
            "attempt": r[13] or 0,
            "max_attempts": r[14] or 1,
            "worker_id": r[15] or "",
            "lease_expires_at": r[16],
            "result_ref": (r[17] or "") if len(r) > 17 else "",
        }

    @staticmethod
    def _event_row(r) -> dict:
        payload = None
        if r[5]:
            try:
                payload = json.loads(r[5])
            except json.JSONDecodeError:
                payload = {"raw": r[5]}
        return {
            "id": r[0],
            "job_id": r[1],
            "event_type": r[2],
            "from_status": r[3],
            "to_status": r[4],
            "payload": payload,
            "created_at": r[6],
        }


_store: ToolJobStore | None = None


def get_tool_jobs() -> ToolJobStore:
    global _store
    if _store is None:
        _store = ToolJobStore()
    return _store
