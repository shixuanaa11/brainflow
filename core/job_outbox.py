"""Job Outbox：终态投递（chat + SSE）至少一次、可重试"""
import json
import sqlite3
import threading
import time
from pathlib import Path

from config.settings import DB_DIR

_lock = threading.Lock()
DB_PATH = str(DB_DIR / "tool_jobs.db")
MAX_ATTEMPTS = 5


class JobOutboxStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS job_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER DEFAULT 0,
                    error TEXT,
                    created_at REAL NOT NULL,
                    delivered_at REAL
                );
                CREATE INDEX IF NOT EXISTS idx_job_outbox_status
                    ON job_outbox(status, created_at);
            """)

    def enqueue(self, job_id: str, kind: str, payload: dict) -> int:
        now = time.time()
        with _lock:
            with self._conn:
                cur = self._conn.execute(
                    "INSERT INTO job_outbox (job_id, kind, payload, status, attempts, "
                    "error, created_at, delivered_at) VALUES (?,?,?,?,0,NULL,?,NULL)",
                    (job_id, kind, json.dumps(payload, ensure_ascii=False), "pending", now),
                )
                return int(cur.lastrowid)

    def reset_stale_processing(self, older_than_sec: float = 120) -> int:
        cutoff = time.time() - older_than_sec
        with _lock:
            with self._conn:
                cur = self._conn.execute(
                    "UPDATE job_outbox SET status='pending' "
                    "WHERE status='processing' AND created_at<?",
                    (cutoff,),
                )
                return cur.rowcount

    def claim_pending(self, limit: int = 20) -> list[dict]:
        now = time.time()
        with _lock:
            with self._conn:
                rows = self._conn.execute(
                    "SELECT id, job_id, kind, payload, attempts FROM job_outbox "
                    "WHERE status='pending' AND attempts<? ORDER BY created_at LIMIT ?",
                    (MAX_ATTEMPTS, limit),
                ).fetchall()
                claimed = []
                for row in rows:
                    oid = row[0]
                    self._conn.execute(
                        "UPDATE job_outbox SET status='processing', attempts=attempts+1 "
                        "WHERE id=? AND status='pending'",
                        (oid,),
                    )
                    if self._conn.total_changes:
                        claimed.append(self._row(row))
                return claimed

    def mark_done(self, outbox_id: int) -> None:
        with _lock:
            with self._conn:
                self._conn.execute(
                    "UPDATE job_outbox SET status='done', delivered_at=? WHERE id=?",
                    (time.time(), outbox_id),
                )

    def mark_failed(self, outbox_id: int, error: str) -> None:
        with _lock:
            with self._conn:
                self._conn.execute(
                    "UPDATE job_outbox SET status='pending', error=? WHERE id=?",
                    (error[:500], outbox_id),
                )

    def mark_dead(self, outbox_id: int, error: str) -> None:
        with _lock:
            with self._conn:
                self._conn.execute(
                    "UPDATE job_outbox SET status='failed', error=? WHERE id=?",
                    (error[:500], outbox_id),
                )

    def count_pending(self) -> int:
        with self._conn:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM job_outbox WHERE status IN ('pending','processing')",
            ).fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _row(r) -> dict:
        payload = {}
        try:
            payload = json.loads(r[3])
        except (json.JSONDecodeError, TypeError):
            pass
        return {
            "id": r[0],
            "job_id": r[1],
            "kind": r[2],
            "payload": payload,
            "attempts": r[4] or 0,
        }


_store: JobOutboxStore | None = None


def get_job_outbox() -> JobOutboxStore:
    global _store
    if _store is None:
        _store = JobOutboxStore()
    return _store
