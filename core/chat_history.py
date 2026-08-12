"""聊天会话历史：SQLite 持久化"""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from config.settings import DB_DIR

_lock = threading.Lock()
DB_CHAT = str(DB_DIR / "chat.db")


class ChatHistory:
    def __init__(self, db_path: str = DB_CHAT):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    meta TEXT,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
                );
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session
                    ON chat_messages(session_id, created_at);
            """)

    def create_session(self, user_id: str, title: str = "新对话") -> dict:
        session_id = uuid.uuid4().hex[:16]
        now = time.time()
        with _lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO chat_sessions VALUES (?,?,?,?,?)",
                    (session_id, user_id, title[:120], now, now),
                )
        return {
            "session_id": session_id,
            "user_id": user_id,
            "title": title[:120],
            "created_at": now,
            "updated_at": now,
        }

    def list_sessions(self, user_id: str, limit: int = 50) -> list[dict]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT session_id, user_id, title, created_at, updated_at "
                "FROM chat_sessions WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [
            {
                "session_id": r[0],
                "user_id": r[1],
                "title": r[2],
                "created_at": r[3],
                "updated_at": r[4],
            }
            for r in rows
        ]

    def get_session(self, session_id: str) -> dict | None:
        with self._conn:
            row = self._conn.execute(
                "SELECT session_id, user_id, title, created_at, updated_at "
                "FROM chat_sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "session_id": row[0],
            "user_id": row[1],
            "title": row[2],
            "created_at": row[3],
            "updated_at": row[4],
        }

    def get_messages(self, session_id: str) -> list[dict]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT role, content, meta, created_at FROM chat_messages "
                "WHERE session_id=? ORDER BY created_at, id",
                (session_id,),
            ).fetchall()
        out = []
        for role, content, meta, created_at in rows:
            item: dict = {
                "role": role,
                "content": content or "",
                "created_at": created_at,
            }
            if meta:
                try:
                    item["meta"] = json.loads(meta)
                except json.JSONDecodeError:
                    item["meta"] = {}
            out.append(item)
        return out

    def append_messages(self, session_id: str, messages: list[dict]) -> None:
        if not messages:
            return
        now = time.time()
        with _lock:
            with self._conn:
                for msg in messages:
                    meta = msg.get("meta")
                    meta_text = json.dumps(meta, ensure_ascii=False) if meta else None
                    self._conn.execute(
                        "INSERT INTO chat_messages (session_id, role, content, meta, created_at) "
                        "VALUES (?,?,?,?,?)",
                        (
                            session_id,
                            msg["role"],
                            msg.get("content") or "",
                            meta_text,
                            msg.get("created_at", now),
                        ),
                    )
                self._conn.execute(
                    "UPDATE chat_sessions SET updated_at=? WHERE session_id=?",
                    (now, session_id),
                )

    def update_title(self, session_id: str, title: str) -> None:
        with _lock:
            with self._conn:
                self._conn.execute(
                    "UPDATE chat_sessions SET title=?, updated_at=? WHERE session_id=?",
                    (title[:120], time.time(), session_id),
                )

    def delete_session(self, session_id: str) -> bool:
        with _lock:
            with self._conn:
                cur = self._conn.execute(
                    "DELETE FROM chat_sessions WHERE session_id=?", (session_id,)
                )
                self._conn.execute(
                    "DELETE FROM chat_messages WHERE session_id=?", (session_id,)
                )
        return cur.rowcount > 0

    def update_assistant_by_job_id(
        self,
        session_id: str,
        job_id: str,
        content: str,
        meta: dict | None = None,
    ) -> bool:
        """更新同一 job 的受理 assistant 消息（LangGraph 一轮一条 AIMessage）"""
        now = time.time()
        with _lock:
            with self._conn:
                rows = self._conn.execute(
                    "SELECT id, meta FROM chat_messages "
                    "WHERE session_id=? AND role='assistant' ORDER BY created_at, id",
                    (session_id,),
                ).fetchall()
                for mid, meta_text in rows:
                    meta_obj: dict = {}
                    if meta_text:
                        try:
                            meta_obj = json.loads(meta_text)
                        except json.JSONDecodeError:
                            pass
                    if meta_obj.get("job_id") != job_id:
                        continue
                    merged = {**meta_obj, **(meta or {})}
                    self._conn.execute(
                        "UPDATE chat_messages SET content=?, meta=? WHERE id=?",
                        (
                            content,
                            json.dumps(merged, ensure_ascii=False),
                            mid,
                        ),
                    )
                    self._conn.execute(
                        "UPDATE chat_sessions SET updated_at=? WHERE session_id=?",
                        (now, session_id),
                    )
                    return True
        return False


_history: ChatHistory | None = None


def get_chat_history() -> ChatHistory:
    global _history
    if _history is None:
        _history = ChatHistory()
    return _history
