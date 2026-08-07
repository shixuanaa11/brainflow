"""FastAPI：API 接口层 + 日志系统（对齐架构 §2.4/§2.5）

端点：
  7 API 对齐 Hermes：board / tasks / profiles / analytics/usage / logs / events / 首页
  对话：POST /api/chat；图可视化：GET /api/graphs；健康：/healthz /readyz
"""
import asyncio
import json
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core.logs import get_logger
from core.stats import get_stats
from core.tracing import get_tracer

ROOT = Path(__file__).parent.parent
app = FastAPI(title="BrainFlow 智脑流", docs_url="/docs",
              openapi_url="/api/openapi.json")
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
    s = get_stats().summary()
    return {
        "uptime_seconds": int(time.time() - START_TIME),
        "total_calls": s["total_calls"],
        "total_tokens": s["total_tokens"],
        "total_errors": s["total_errors"],
        "error_rate": round(s["total_errors"] / max(s["total_calls"], 1), 4),
        "active_tools": len(s["by_tool"]),
        "top_tools": sorted(s["by_tool"].items(), key=lambda x: -x[1])[:5],
        "status": "healthy" if s["total_errors"] < max(s["total_calls"] * 0.05, 5) else "degraded",
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
def chat(payload: dict):
    text = str(payload.get("text", "")).strip()
    if not text:
        return {"reply": "请输入内容"}
    from server.main import run_once
    return {"reply": run_once(text, str(payload.get("user_id", "web")))}


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
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse({"status": "not_ready", "error": str(e)}, status_code=503)


# ---- 前端静态页（对话 / 工作流图 / 看板）----
app.mount("/", StaticFiles(directory=str(Path(__file__).parent / "static"), html=True),
          name="static")
