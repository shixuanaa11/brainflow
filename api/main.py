"""FastAPI：API 接口层 + 日志系统（对齐架构 §2.4/§2.5）

端点：
  运维 API：board / tasks / profiles / analytics/usage / logs / events
  对话：POST /api/chat/stream；Job：/api/jobs/*；图：GET /api/graphs；健康：/healthz /readyz
  UI 由 web/ 前端提供（本模块不托管静态页）
"""
import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from core.logs import get_logger
from core.llm import get_client
from core.stats import get_stats
from core.tracing import get_tracer
from src.graph import init_graph

ROOT = Path(__file__).parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_graph()
    from core.job_service import get_job_service
    svc = get_job_service()
    await svc.start(run_outbox_loop=True)
    get_client().warmup()
    yield
    await svc.stop()


app = FastAPI(title="BrainFlow 智脑流", docs_url="/docs",
              openapi_url="/api/openapi.json", lifespan=lifespan)
log = get_logger("api")
START_TIME = time.time()


# ---- 日志中间件：每次请求记录 method/path/status/duration/trace_id ----
@app.middleware("http")
async def request_log(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id", uuid.uuid4().hex[:12])
    t0 = time.time()
    response = await call_next(request)
    log.info(json.dumps({
        "event": "request", "trace_id": trace_id,
        "method": request.method, "path": request.url.path,
        "status": response.status_code,
        "duration_ms": int((time.time() - t0) * 1000),
    }, ensure_ascii=False))
    return response


# ---- 7 API（对齐 Hermes）----
@app.get("/api/board")
def board():
    from core.tool_jobs import get_tool_jobs
    s = get_stats().summary()
    jobs = get_tool_jobs().summary()
    return {
        "uptime_seconds": int(time.time() - START_TIME),
        "total_calls": s["total_calls"],
        "total_tokens": s["total_tokens"],
        "total_errors": s["total_errors"],
        "error_rate": round(s["total_errors"] / max(s["total_calls"], 1), 4),
        "active_tools": len(s["by_tool"]),
        "top_tools": sorted(s["by_tool"].items(), key=lambda x: -x[1])[:5],
        "status": "healthy" if s["total_errors"] < max(s["total_calls"] * 0.05, 5) else "degraded",
        "tool_jobs": jobs,
    }


@app.get("/api/tasks")
def tasks():
    traces = get_tracer().recent_traces(n=50)
    return {"tasks": [
        {"trace_id": t["trace_id"], "workflow": t["workflow"], "user": t["user_id"],
         "input": t["input"], "status": t["status"], "timestamp": t["started_at"],
         "spans": get_tracer().spans_of(t["trace_id"])} for t in traces],
        "count": len(traces)}


@app.get("/api/profiles")
def profiles():
    s = get_stats().summary()
    return {"profiles": [
        {"tool": n, "calls": c, "tokens": s["by_tool_tokens"].get(n, 0)}
        for n, c in sorted(s["by_tool"].items(), key=lambda x: -x[1])],
        "count": len(s["by_tool"])}


@app.get("/api/analytics/usage")
def usage():
    return get_stats().summary()


@app.get("/api/logs")
def logs(n: int = 50):
    return {"logs": get_stats().recent_logs(n=min(n, 200))}


@app.get("/api/events")
async def events():
    """SSE 实时事件（心跳）"""
    async def gen():
        while True:
            yield f"data: {json.dumps({'type': 'heartbeat', 'ts': time.time()})}\n\n"
            await asyncio.sleep(15)
    return StreamingResponse(gen(), media_type="text/event-stream")


# ---- 对话 + 图 ----
@app.post("/api/chat")
async def chat(payload: dict):
    text = str(payload.get("text", "")).strip()
    if not text:
        return {"reply": "请输入内容"}
    from server.main import run_once_async
    return {"reply": await run_once_async(text, str(payload.get("user_id", "web")))}


@app.post("/api/chat/stream")
async def chat_stream(payload: dict):
    """SSE 流式对话：按节点流式推送（router → tool → summary），reply 在 summary 节点产出时实时推送"""
    text = str(payload.get("text", "")).strip()
    user_id = str(payload.get("user_id", "web"))
    session_id = str(payload.get("session_id", "")).strip()
    if not text:
        return JSONResponse({"detail": "请输入内容"}, status_code=400)

    from src.graph import get_graph_async
    from langchain_core.messages import HumanMessage
    from core.tracing import get_tracer

    async def gen():
        from core.chat_history import get_chat_history

        if session_id:
            hist = get_chat_history()
            if hist.get_session(session_id):
                hist.append_messages(session_id, [{"role": "user", "content": text}])

        yield f"data: {json.dumps({'type': 'start'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'step', 'node': 'router', 'kind': 'router', 'status': 'running'}, ensure_ascii=False)}\n\n"
        get_tracer().start_trace("agent", text, user_id)
        graph = await get_graph_async()
        try:
            async for event in graph.astream(
                {"messages": [HumanMessage(content=text)], "session_id": session_id},
                stream_mode="updates",
            ):
                for node, update in event.items():
                    kind = (
                        "router" if node == "router"
                        else "qa" if node == "general_qa"
                        else "summary" if node == "summary"
                        else "tool"
                    )
                    job_id = update.get("job_id", "")
                    is_async = bool(job_id)
                    step: dict = {
                        "type": "step",
                        "node": node,
                        "kind": kind,
                        "status": "done",
                    }
                    if kind == "router":
                        step["intent"] = update.get("intent")
                    elif kind == "tool":
                        step["tool"] = node.removeprefix("tool_")
                        step["output"] = update.get("tool_output")
                        if is_async:
                            step["async"] = True
                            step["job_id"] = job_id
                    yield f"data: {json.dumps(step, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'node', 'node': node}, ensure_ascii=False)}\n\n"
                    # 异步 job 状态走 session/job SSE（join stream），图流只推 step
                    for m in (update.get("messages") or []):
                        if getattr(m, "type", "") == "ai" and m.content and not is_async:
                            yield f"data: {json.dumps({'type': 'reply', 'reply': m.content}, ensure_ascii=False)}\n\n"
            get_tracer().end_trace("ok")
        except Exception as e:
            get_tracer().end_trace("error", str(e))
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---- 聊天历史 ----
@app.get("/api/chat/sessions")
def chat_sessions(user_id: str = "web", limit: int = 50):
    from core.chat_history import get_chat_history
    sessions = get_chat_history().list_sessions(user_id, limit=min(limit, 100))
    return {"sessions": sessions, "count": len(sessions)}


@app.post("/api/chat/sessions")
def chat_create_session(payload: dict):
    from core.chat_history import get_chat_history
    user_id = str(payload.get("user_id", "web"))
    title = str(payload.get("title", "新对话")).strip() or "新对话"
    session = get_chat_history().create_session(user_id, title)
    return session


@app.get("/api/chat/sessions/{session_id}")
def chat_get_session(session_id: str):
    from core.chat_history import get_chat_history
    hist = get_chat_history()
    session = hist.get_session(session_id)
    if not session:
        return JSONResponse({"detail": "会话不存在"}, status_code=404)
    messages = hist.get_messages(session_id)
    return {**session, "messages": messages}


@app.patch("/api/chat/sessions/{session_id}")
def chat_update_session(session_id: str, payload: dict):
    from core.chat_history import get_chat_history
    hist = get_chat_history()
    if not hist.get_session(session_id):
        return JSONResponse({"detail": "会话不存在"}, status_code=404)
    title = str(payload.get("title", "")).strip()
    if title:
        hist.update_title(session_id, title)
    return {"ok": True}


@app.post("/api/chat/sessions/{session_id}/messages")
def chat_append_messages(session_id: str, payload: dict):
    from core.chat_history import get_chat_history
    hist = get_chat_history()
    if not hist.get_session(session_id):
        return JSONResponse({"detail": "会话不存在"}, status_code=404)
    messages = payload.get("messages") or []
    hist.append_messages(session_id, messages)
    return {"ok": True, "count": len(messages)}


@app.delete("/api/chat/sessions/{session_id}")
def chat_delete_session(session_id: str):
    from core.chat_history import get_chat_history
    deleted = get_chat_history().delete_session(session_id)
    if not deleted:
        return JSONResponse({"detail": "会话不存在"}, status_code=404)
    return {"ok": True}


@app.get("/api/jobs")
def list_jobs(limit: int = 100, active_only: bool = False, status: str = ""):
    from core.tool_jobs import get_tool_jobs
    jobs = get_tool_jobs().list_recent(
        limit=min(limit, 200),
        active_only=active_only,
        status=status or None,
    )
    summary = get_tool_jobs().summary()
    return {"jobs": jobs, "count": len(jobs), "summary": summary}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    from core.job_service import get_job_service
    job = get_job_service().get(job_id)
    if not job:
        return JSONResponse({"detail": "任务不存在"}, status_code=404)
    return job


@app.get("/api/jobs/{job_id}/events")
def get_job_events(job_id: str, since: float = 0):
    from core.job_service import get_job_service
    job = get_job_service().get(job_id)
    if not job:
        return JSONResponse({"detail": "任务不存在"}, status_code=404)
    events = get_job_service().list_events(job_id, since=since)
    return {"job_id": job_id, "events": events, "count": len(events)}


@app.get("/api/jobs/{job_id}/result")
def get_job_result_file(job_id: str):
    from core.job_service import get_job_service
    from fastapi.responses import FileResponse
    job = get_job_service().get(job_id)
    if not job:
        return JSONResponse({"detail": "任务不存在"}, status_code=404)
    ref = job.get("result_ref") or ""
    if not ref or not Path(ref).is_file():
        return JSONResponse({"detail": "无外置结果文件", "result": job.get("result")})
    return FileResponse(ref, media_type="text/plain; charset=utf-8",
                        filename=f"{job_id}.txt")


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    from core.job_service import get_job_service
    job = get_job_service().get(job_id)
    if not job:
        return JSONResponse({"detail": "任务不存在"}, status_code=404)
    updated = get_job_service().cancel(job_id)
    return {"ok": True, "job": updated}


@app.get("/api/jobs/events")
async def jobs_events(since: float = 0):
    """全局工具任务 SSE：snapshot + replay(since) + 实时"""
    from core.job_bus import subscribe_global, unsubscribe_global
    from core.job_service import get_job_service
    from core.tool_jobs import get_tool_jobs

    async def gen():
        recent = get_tool_jobs().list_recent(limit=100)
        if since <= 0:
            yield f"data: {json.dumps({'type': 'snapshot', 'jobs': recent}, ensure_ascii=False)}\n\n"
        if since > 0:
            for ev in get_job_service().replay_global_sse(since):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        q = await subscribe_global()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'ts': time.time()})}\n\n"
        finally:
            await unsubscribe_global(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/chat/sessions/{session_id}/jobs")
def chat_session_jobs(session_id: str, active_only: bool = True):
    from core.chat_history import get_chat_history
    from core.tool_jobs import get_tool_jobs
    if not get_chat_history().get_session(session_id):
        return JSONResponse({"detail": "会话不存在"}, status_code=404)
    jobs = get_tool_jobs().list_for_session(session_id, active_only=active_only)
    return {"jobs": jobs, "count": len(jobs)}


@app.get("/api/chat/sessions/{session_id}/events")
async def chat_session_events(session_id: str, since: float = 0):
    """会话级 SSE：snapshot + replay(since) + 实时"""
    from core.chat_history import get_chat_history
    from core.job_bus import subscribe, unsubscribe
    from core.job_service import get_job_service
    from core.tool_jobs import get_tool_jobs

    if not get_chat_history().get_session(session_id):
        return JSONResponse({"detail": "会话不存在"}, status_code=404)

    async def gen():
        active = get_tool_jobs().list_for_session(session_id, active_only=True)
        if since <= 0:
            yield f"data: {json.dumps({'type': 'snapshot', 'jobs': active}, ensure_ascii=False)}\n\n"
        if since > 0:
            for ev in get_job_service().replay_session_sse(session_id, since):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        q = await subscribe(session_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'ts': time.time()})}\n\n"
        finally:
            await unsubscribe(session_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/graphs")
def graphs():
    from src.graph import get_graph_mermaid
    return {"id": "agent", "mermaid": get_graph_mermaid()}


# ---- 健康检查 ----
@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    try:
        get_stats().summary()
        llm_ready = get_client().has_credentials()
        return {
            "status": "ready" if llm_ready else "degraded",
            "llm_configured": llm_ready,
        }
    except Exception as e:
        return JSONResponse({"status": "not_ready", "error": str(e)}, status_code=503)


@app.get("/")
def root():
    """API 根路径；UI 请使用 web/ 前端（Vite :5174）"""
    return {
        "service": "BrainFlow",
        "docs": "/docs",
        "health": "/healthz",
        "frontend": "运行 web/ 目录：npm run dev（默认 :5174）",
    }
