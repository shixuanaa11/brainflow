"""Trace/Span 可观测：每次请求一条 trace，每节点一个 span（状态/耗时/输入输出/token）→ SQLite"""
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from config.settings import DB_OBSERVE

_lock = threading.Lock()


class TraceSpan:
    def __init__(self, db_path: str = DB_OBSERVE):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
        self._current: dict = {}
        self._current_node: str = ""   # 当前执行节点（LLM token 挂到它上面）
        self._pending: dict = {}       # node -> 待挂 token（span 未插入前先暂存）

    def _init_db(self):
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY, workflow TEXT, user_id TEXT,
                    input TEXT, status TEXT, started_at REAL, ended_at REAL, detail TEXT);
                CREATE TABLE IF NOT EXISTS spans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT,
                    node TEXT, kind TEXT, duration REAL, status TEXT,
                    detail TEXT, input TEXT, output TEXT, tokens INTEGER, ts REAL);
            """)
            # 兼容旧表：缺列则补
            cols = {r[1] for r in self._conn.execute("PRAGMA table_info(spans)").fetchall()}
            for col, ddl in [("input", "TEXT"), ("output", "TEXT"), ("tokens", "INTEGER DEFAULT 0")]:
                if col not in cols:
                    self._conn.execute(f"ALTER TABLE spans ADD COLUMN {col} {ddl}")

    # ---- trace 生命周期 ----
    def start_trace(self, workflow: str, user_input: str, user_id: str):
        self._current = {"id": uuid.uuid4().hex[:16], "workflow": workflow,
                         "input": user_input, "user": user_id, "t0": time.time()}
        self._current_node = ""
        self._pending = {}

    def end_trace(self, status: str, detail: str = ""):
        c = self._current
        if not c:
            return
        with _lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO traces VALUES (?,?,?,?,?,?,?,?)",
                    (c["id"], c["workflow"], c["user"], c["input"],
                     status, c["t0"], time.time(), detail))

    # ---- span 记录（节点级：状态/耗时/输入输出/token）----
    def add_span(self, node: str, kind: str, duration: float,
                 status: str = "ok", detail: str = "",
                 input_text: str = "", output_text: str = "", tokens: int = 0):
        c = self._current
        if not c:
            return
        # 合并 LLM 调用暂存的 token（span 插入前由 add_pending_tokens 积累）
        pending = self._pending.pop(node, 0)
        tokens = int(tokens) + int(pending)
        with _lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO spans (trace_id,node,kind,duration,status,detail,input,output,tokens,ts) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (c["id"], node, kind, duration, status,
                     str(detail),
                     str(input_text),
                     str(output_text), int(tokens), time.time()))

    def set_current_node(self, node: str):
        """节点执行开始前调用：LLM 的 token 将挂到该节点"""
        self._current_node = node

    def current_trace_id(self) -> str:
        return self._current.get("id", "") if self._current else ""

    def add_pending_tokens(self, tokens: int):
        """LLM 调用后暂存 token 到当前节点（span 插入时合并）"""
        c = self._current
        if not c or tokens <= 0:
            return
        node = self._current_node or "router"
        self._pending[node] = self._pending.get(node, 0) + int(tokens)

    # ---- 查询（供 Dashboard）----
    def recent_traces(self, n: int = 50) -> list[dict]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT * FROM traces ORDER BY started_at DESC LIMIT ?", (n,)).fetchall()
        cols = ["trace_id", "workflow", "user_id", "input", "status",
                "started_at", "ended_at", "detail"]
        return [dict(zip(cols, r)) for r in rows]

    def spans_of(self, trace_id: str) -> list[dict]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT node,kind,duration,status,detail,input,output,tokens FROM spans "
                "WHERE trace_id=? ORDER BY ts", (trace_id,)).fetchall()
        return [{"node": r[0], "kind": r[1], "duration": r[2],
                 "status": r[3], "detail": r[4], "input": r[5],
                 "output": r[6], "tokens": r[7]} for r in rows]


_tracer: TraceSpan | None = None


def get_tracer() -> TraceSpan:
    global _tracer
    if _tracer is None:
        _tracer = TraceSpan()
    return _tracer
