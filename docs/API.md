# BrainFlow FastAPI 接口文档

本文档描述 `api/main.py` 提供的全部 HTTP 接口，与 `web/` 运营看板、对话页对接。实现源码：`api/main.py`。

---

## 基本信息

| 项 | 值 |
| --- | --- |
| 默认地址 | `http://127.0.0.1:5173` |
| OpenAPI / Swagger | `/docs` |
| OpenAPI JSON | `/api/openapi.json` |
| 默认 Content-Type | `application/json`（SSE 端点为 `text/event-stream`） |

### curl 约定

下文示例默认服务地址为 `http://127.0.0.1:5173`。可先设置环境变量再复制命令：

```bash
export BASE_URL="http://127.0.0.1:5173"
```

| 场景 | 常用请求头 |
| --- | --- |
| JSON 接口 | `Content-Type: application/json`、`Accept: application/json` |
| SSE 长连接 | `Accept: text/event-stream`；curl 加 `-N`（禁用缓冲） |
| 链路追踪（可选） | `X-Trace-Id: <自定义 id>` |

GET 请求无请求体；POST / PATCH 在 `-d` 中传 JSON 字符串。

### 请求头（可选）

| 头 | 说明 |
| --- | --- |
| `X-Trace-Id` | 自定义 trace id；未传时服务端自动生成 12 位 hex |

### 通用错误响应

FastAPI 标准格式：

```json
{ "detail": "错误说明" }
```

常见 HTTP 状态码：`400` 参数错误、`404` 资源不存在、`503` 服务未就绪（`/readyz`）。

---

## 健康检查

### GET `/healthz`

存活探针。

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/healthz" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{ "status": "ok" }
```

---

### GET `/readyz`

就绪探针：指标系统可用，且 LLM 凭证已配置。

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/readyz" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "status": "ready",
  "llm_configured": true
}
```

LLM 未配置时 `status` 为 `degraded`，仍返回 200。内部异常时返回 503：

```json
{ "status": "not_ready", "error": "..." }
```

---

### GET `/`

API 元信息（不托管前端静态页）。

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/" \
  -H "Accept: application/json"
```

 

**响应 200**

```json
{
  "service": "BrainFlow",
  "docs": "/docs",
  "health": "/healthz",
  "frontend": "运行 web/ 目录：npm run dev（默认 :5174）"
}
```

---

## 运维 API（生产看板）

数据来自内存指标（`core/stats`）与 SQLite trace（`core/tracing`），供 `web/` 仪表盘使用。

### GET `/api/board`

看板总览。

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/api/board" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "uptime_seconds": 3600,
  "total_calls": 128,
  "total_tokens": 45200,
  "total_errors": 2,
  "error_rate": 0.0156,
  "active_tools": 4,
  "top_tools": [["weather", 45], ["info_hunt", 30]],
  "status": "healthy",
  "tool_jobs": {
    "total": 12,
    "active": 1,
    "by_status": { "done": 10, "running": 1, "queued": 1 }
  }
}
```

`status`：`healthy` | `degraded`（错误率超过阈值时）。

---

### GET `/api/tasks`

最近任务 trace 列表（含节点级 span）。

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/api/tasks" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "tasks": [
    {
      "trace_id": "a1b2c3d4e5f6",
      "workflow": "agent",
      "user": "web",
      "input": "北京天气怎么样",
      "status": "ok",
      "timestamp": 1710000000.0,
      "spans": [
        {
          "node": "router",
          "kind": "router",
          "duration": 120,
          "status": "ok",
          "detail": "",
          "input": "",
          "output": "",
          "tokens": 50
        }
      ]
    }
  ],
  "count": 1
}
```

`span.kind`：`router` | `tool` | `summary`。

---

### GET `/api/profiles`

按工具聚合的调用次数与 token。

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/api/profiles" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "profiles": [
    { "tool": "weather", "calls": 45, "tokens": 12000 }
  ],
  "count": 1
}
```

---

### GET `/api/analytics/usage`

使用统计摘要。

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/api/analytics/usage" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "total_calls": 128,
  "total_tokens": 45200,
  "total_errors": 2,
  "by_tool": { "weather": 45, "info_hunt": 30 },
  "by_tool_tokens": { "weather": 12000, "info_hunt": 8000 }
}
```

---

### GET `/api/logs`

最近调用日志。

**Query**

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `n` | int | 50 | 条数，最大 200 |

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/api/logs?n=20" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "logs": [
    {
      "tool": "weather",
      "tokens": 120,
      "error": "",
      "latency": 850,
      "user": "web",
      "time": 1710000000.0
    }
  ]
}
```

---

### GET `/api/events`

运维 SSE：仅心跳，用于保持连接。

**curl**

```bash
curl -N -X GET "http://127.0.0.1:5173/api/events" \
  -H "Accept: text/event-stream" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**SSE 事件**

| type | 字段 | 说明 |
| --- | --- | --- |
| `heartbeat` | `ts` | Unix 时间戳，约每 15s 一条 |

---

## 对话 API

### POST `/api/chat`

同步对话（阻塞至 graph 跑完）。

**请求体**

```json
{
  "text": "你好",
  "user_id": "web"
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `text` | 是 | 用户输入；空则返回提示 |
| `user_id` | 否 | 默认 `web` |

**curl**

```bash
curl -X POST "http://127.0.0.1:5173/api/chat" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001" \
  -d '{
    "text": "你好",
    "user_id": "web"
  }'
```

**响应 200**

```json
{ "reply": "你好！有什么可以帮你的？" }
```

空 `text` 时仍 200：`{ "reply": "请输入内容" }`。

---

### POST `/api/chat/stream`

**Run Stream**：SSE 流式对话。按 LangGraph 节点推送 `step`；同步工具在 summary 前推送 `reply`；异步工具（`info_hunt`、`weather`）只推带 `job_id` 的 step，后续进度走 Join Stream。

**请求体**

```json
{
  "text": "查一下上海天气",
  "user_id": "web",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `text` | 是 | 用户输入 |
| `user_id` | 否 | 默认 `web` |
| `session_id` | 否 | 传入且会话存在时，会先持久化 user 消息 |

**curl**

```bash
curl -N -X POST "http://127.0.0.1:5173/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "X-Trace-Id: demo-trace-001" \
  -d '{
    "text": "查一下上海天气",
    "user_id": "web",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**错误 400**

```json
{ "detail": "请输入内容" }
```

**SSE 事件类型**

| type | 说明 |
| --- | --- |
| `start` | 流开始 |
| `step` | 节点完成一步（见下表） |
| `node` | 节点名通知 `{ "type": "node", "node": "router" }` |
| `reply` | 助手正文（仅同步路径） |
| `error` | 异常 `{ "type": "error", "message": "..." }` |

**`step` 字段**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `node` | string | 图节点名，如 `router`、`summary`、`tool_weather` |
| `kind` | string | `router` \| `tool` \| `summary` \| `qa` |
| `status` | string | 当前实现多为 `done`；开始时 router 会先推 `running` |
| `intent` | string? | router 识别的意图 |
| `tool` | string? | 工具名（去掉 `tool_` 前缀） |
| `output` | string? | 工具输出摘要 |
| `async` | bool? | true 表示异步 Job |
| `job_id` | string? | 异步任务 id，客户端应订阅 Join Stream |

**流结束标记**

```
data: [DONE]
```

**示例（同步）**

```
data: {"type":"start"}

data: {"type":"step","node":"router","kind":"router","status":"running"}

data: {"type":"step","node":"router","kind":"router","status":"done","intent":"weather"}

data: {"type":"node","node":"router"}

data: {"type":"step","node":"tool_weather","kind":"tool","status":"done","tool":"weather","output":"..."}

data: {"type":"node","node":"tool_weather"}

data: {"type":"step","node":"summary","kind":"summary","status":"done"}

data: {"type":"node","node":"summary"}

data: {"type":"reply","reply":"上海今天晴，25°C..."}

data: [DONE]
```

**示例（异步工具）**

`step` 含 `"async": true, "job_id": "..."`，无即时 `reply`；通过 `GET /api/chat/sessions/{session_id}/events` 接收 `job` / `job_done` 事件。

---

## 会话历史 API

持久化在 SQLite（`core/chat_history`）。

### GET `/api/chat/sessions`

**Query**

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `user_id` | `web` | 用户 id |
| `limit` | 50 | 最大 100 |

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/api/chat/sessions?user_id=web&limit=20" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "web",
      "title": "新对话",
      "created_at": 1710000000.0,
      "updated_at": 1710000100.0
    }
  ],
  "count": 1
}
```

---

### POST `/api/chat/sessions`

创建会话。

**请求体**

```json
{
  "user_id": "web",
  "title": "天气咨询"
}
```

**curl**

```bash
curl -X POST "http://127.0.0.1:5173/api/chat/sessions" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001" \
  -d '{
    "user_id": "web",
    "title": "天气咨询"
  }'
```

**响应 200**：单个 `ChatSession` 对象（同上，无 `messages`）。

---

### GET `/api/chat/sessions/{session_id}`

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/api/chat/sessions/550e8400-e29b-41d4-a716-446655440000" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "session_id": "...",
  "user_id": "web",
  "title": "新对话",
  "created_at": 1710000000.0,
  "updated_at": 1710000100.0,
  "messages": [
    {
      "role": "user",
      "content": "你好",
      "created_at": 1710000000.0
    },
    {
      "role": "assistant",
      "content": "你好！",
      "created_at": 1710000001.0,
      "meta": {
        "job_id": "job-uuid",
        "job_status": "done",
        "tool": "weather",
        "steps": [
          {
            "node": "router",
            "kind": "router",
            "label": "意图识别",
            "status": "done",
            "intent": "weather"
          }
        ]
      }
    }
  ]
}
```

**404**：`{ "detail": "会话不存在" }`

---

### PATCH `/api/chat/sessions/{session_id}`

更新标题。

**请求体**

```json
{ "title": "新标题" }
```

**curl**

```bash
curl -X PATCH "http://127.0.0.1:5173/api/chat/sessions/550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001" \
  -d '{
    "title": "新标题"
  }'
```

**响应 200**：`{ "ok": true }`

---

### POST `/api/chat/sessions/{session_id}/messages`

批量追加消息（前端在流式结束后写 assistant 消息时使用）。

**请求体**

```json
{
  "messages": [
    {
      "role": "assistant",
      "content": "回复正文",
      "meta": { "steps": [], "job_id": "abc123" }
    }
  ]
}
```

**curl**

```bash
curl -X POST "http://127.0.0.1:5173/api/chat/sessions/550e8400-e29b-41d4-a716-446655440000/messages" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001" \
  -d '{
    "messages": [
      {
        "role": "assistant",
        "content": "回复正文",
        "meta": { "steps": [], "job_id": "abc123" }
      }
    ]
  }'
```

**响应 200**：`{ "ok": true, "count": 1 }`

---

### DELETE `/api/chat/sessions/{session_id}`

**curl**

```bash
curl -X DELETE "http://127.0.0.1:5173/api/chat/sessions/550e8400-e29b-41d4-a716-446655440000" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**：`{ "ok": true }`  
**404**：会话不存在

---

## 异步 Job API

异步工具：`info_hunt`、`weather`。状态机见 `core/job_state.py`。

| 状态 | 说明 |
| --- | --- |
| `queued` | 已创建，待提交 |
| `submitted` | 已提交 Worker |
| `running` | 执行中 |
| `done` | 成功 |
| `error` | 失败 |
| `timeout` | 超时 |
| `cancelled` | 已取消 |

### GET `/api/jobs`

Job 列表（Kanban / 看板）。

**Query**

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `limit` | 100 | 最大 200 |
| `active_only` | false | 仅活跃任务 |
| `status` | `""` | 按状态过滤 |

**curl**

```bash
# 全部任务
curl -X GET "http://127.0.0.1:5173/api/jobs?limit=50" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"

# 仅活跃 + 按状态过滤
curl -X GET "http://127.0.0.1:5173/api/jobs?active_only=true&status=running" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "jobs": [
    {
      "job_id": "abc123",
      "session_id": "...",
      "tool_name": "weather",
      "status": "running",
      "progress": 50,
      "result": null,
      "error": null,
      "result_ref": "/path/to/result.txt",
      "user_query": "上海天气",
      "created_at": 1710000000.0,
      "updated_at": 1710000030.0
    }
  ],
  "count": 1,
  "summary": {
    "total": 12,
    "active": 1,
    "by_status": { "running": 1, "done": 11 }
  }
}
```

---

### GET `/api/jobs/{job_id}`

单个 Job 详情。

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/api/jobs/abc123" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**404**：任务不存在

---

### GET `/api/jobs/{job_id}/events`

Job 审计事件（状态迁移、payload）。

**Query**

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `since` | 0 | 只返回 `created_at > since` 的事件 |

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/api/jobs/abc123/events?since=1710000000" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "job_id": "abc123",
  "events": [
    {
      "event_type": "status_change",
      "from_status": "queued",
      "to_status": "submitted",
      "payload": {},
      "created_at": 1710000001.0
    }
  ],
  "count": 1
}
```

---

### GET `/api/jobs/{job_id}/result`

下载外置结果文件（`result_ref` 指向的本地文件）。

**curl**

```bash
# 输出到终端
curl -X GET "http://127.0.0.1:5173/api/jobs/abc123/result" \
  -H "Accept: text/plain, application/json" \
  -H "X-Trace-Id: demo-trace-001"

# 保存为文件
curl -X GET "http://127.0.0.1:5173/api/jobs/abc123/result" \
  -H "X-Trace-Id: demo-trace-001" \
  -o "abc123-result.txt"
```

 

- 有文件：返回 `text/plain` 文件流  
- 无外置文件：200 JSON `{ "detail": "无外置结果文件", "result": "内联结果文本" }`  
- **404**：任务不存在

---

### POST `/api/jobs/{job_id}/cancel`

取消任务（仅非终态可取消）。

**curl**

```bash
curl -X POST "http://127.0.0.1:5173/api/jobs/abc123/cancel" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "ok": true,
  "job": { "job_id": "abc123", "status": "cancelled" }
}
```

---

### GET `/api/jobs/events`

**全局 Job SSE**：Job 看板用。连接后先 `snapshot`，可选 `since` 重放，再实时推送。

**Query**

| 参数 | 说明 |
| --- | --- |
| `since` | Unix 时间戳；`>0` 时跳过 snapshot，重放该时间点之后的事件 |

**curl**

```bash
# 首次连接（含 snapshot）
curl -N -X GET "http://127.0.0.1:5173/api/jobs/events" \
  -H "Accept: text/event-stream" \
  -H "X-Trace-Id: demo-trace-001"

# 断线重连（从上次事件时间戳重放）
curl -N -X GET "http://127.0.0.1:5173/api/jobs/events?since=1710000030" \
  -H "Accept: text/event-stream" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**SSE 事件**

| type | 说明 |
| --- | --- |
| `snapshot` | `{ "type": "snapshot", "jobs": [ ToolJob, ... ] }` |
| `job` | 进度更新 |
| `job_done` | 成功结束 |
| `job_error` | 失败 / 超时 / 取消 |
| `heartbeat` | 15s 无事件时发送 |

**Job 事件公共字段**

```json
{
  "type": "job",
  "job_id": "abc123",
  "session_id": "...",
  "tool": "weather",
  "status": "running",
  "progress": 50,
  "result": null,
  "error": null,
  "result_ref": null,
  "ts": 1710000030.0,
  "replay": false
}
```

`replay: true` 表示来自 `since` 重放，非实时。

---

### GET `/api/chat/sessions/{session_id}/jobs`

会话下 Job 列表。

**Query**

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `active_only` | true | 仅活跃任务 |

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/api/chat/sessions/550e8400-e29b-41d4-a716-446655440000/jobs?active_only=false" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**404**：会话不存在

---

### GET `/api/chat/sessions/{session_id}/events`

**Join Stream**：对话页切屏恢复、异步工具进度。行为同全局 SSE，但仅该 `session_id` 的 Job。

**Query**：`since`（同上）

**curl**

```bash
# 首次连接（含活跃 Job snapshot）
curl -N -X GET "http://127.0.0.1:5173/api/chat/sessions/550e8400-e29b-41d4-a716-446655440000/events" \
  -H "Accept: text/event-stream" \
  -H "X-Trace-Id: demo-trace-001"

# 断线重连
curl -N -X GET "http://127.0.0.1:5173/api/chat/sessions/550e8400-e29b-41d4-a716-446655440000/events?since=1710000030" \
  -H "Accept: text/event-stream" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**首包**：`since <= 0` 时推 `{ "type": "snapshot", "jobs": [...] }`（活跃 Job）  
**重连**：`since > 0` 重放会话内事件，再订阅实时队列

**典型联调流程（curl）**

```bash
# 1. 创建会话
curl -X POST "http://127.0.0.1:5173/api/chat/sessions" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"user_id":"web","title":"联调测试"}'

# 2. 终端 A：订阅 Join Stream（替换 SESSION_ID）
curl -N "http://127.0.0.1:5173/api/chat/sessions/SESSION_ID/events" \
  -H "Accept: text/event-stream"

# 3. 终端 B：发起流式对话（替换 SESSION_ID）
curl -N -X POST "http://127.0.0.1:5173/api/chat/stream" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"text":"查一下上海天气","user_id":"web","session_id":"SESSION_ID"}'
```

---

## 工作流图

### GET `/api/graphs`

返回 LangGraph Mermaid 源码。

**curl**

```bash
curl -X GET "http://127.0.0.1:5173/api/graphs" \
  -H "Accept: application/json" \
  -H "X-Trace-Id: demo-trace-001"
```

 

**响应 200**

```json
{
  "id": "agent",
  "mermaid": "graph TD\n  __start__ --> router\n  ..."
}
```

前端用 [mermaid.js](https://mermaid.js.org/) 渲染。

---

## SSE 客户端约定

1. 每条消息格式：`data: {JSON}\n\n`
2. Run Stream 以 `data: [DONE]\n\n` 结束（非 JSON）
3. Job / Join Stream 长连接，超时发 `heartbeat`，客户端应忽略或用于保活
4. 建议解析失败时打日志并跳过该行，避免单条脏数据断流
5. 浏览器 `EventSource` 仅支持 GET；Run Stream 需 `fetch` + `ReadableStream` 或 polyfill
6. curl 测试 SSE 时务必加 `-N`，否则输出可能被缓冲

---

## 端点速查

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/board` | 看板总览 |
| GET | `/api/tasks` | Trace 任务列表 |
| GET | `/api/profiles` | 工具画像 |
| GET | `/api/analytics/usage` | 使用统计 |
| GET | `/api/logs` | 调用日志 |
| GET | `/api/events` | 运维 SSE 心跳 |
| POST | `/api/chat` | 同步对话 |
| POST | `/api/chat/stream` | Run Stream SSE |
| GET | `/api/chat/sessions` | 会话列表 |
| POST | `/api/chat/sessions` | 创建会话 |
| GET | `/api/chat/sessions/{id}` | 会话详情 + 消息 |
| PATCH | `/api/chat/sessions/{id}` | 改标题 |
| POST | `/api/chat/sessions/{id}/messages` | 追加消息 |
| DELETE | `/api/chat/sessions/{id}` | 删除会话 |
| GET | `/api/jobs` | Job 列表 |
| GET | `/api/jobs/{id}` | Job 详情 |
| GET | `/api/jobs/{id}/events` | Job 审计 |
| GET | `/api/jobs/{id}/result` | 结果文件 |
| POST | `/api/jobs/{id}/cancel` | 取消 Job |
| GET | `/api/jobs/events` | 全局 Job SSE |
| GET | `/api/chat/sessions/{id}/jobs` | 会话 Job 列表 |
| GET | `/api/chat/sessions/{id}/events` | Join Stream SSE |
| GET | `/api/graphs` | Mermaid 工作流 |
| GET | `/healthz` | 存活 |
| GET | `/readyz` | 就绪 |
| GET | `/` | 服务信息 |

---

## 相关文档

- 异步 Job 架构：[async-job-architecture.md](./async-job-architecture.md)
- 前端类型定义：`web/src/lib/types.ts`
- 本地调试：[DEBUG.md](./DEBUG.md)
