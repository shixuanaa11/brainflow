# BrainFlow 运营看板（web）

BrainFlow 自研运营前端：总览指标、任务链路追踪、LangGraph 工作流可视化、AI 对话（SSE 流式 + 会话历史）。

> 后端 API 由仓库根目录 `python server/main.py` 提供（默认 `:5173`）。完整项目说明见 [根目录 README](../README.md)。

### 项目信息

| 项 | 内容 |
| --- | --- |
| **作者** | 黄宇然（huangyuran） |
| **版本** | v1.2（2026-08-11） |
| **协议** | 专有 · © 2026 黄宇然，保留所有权利 |

---

## 技术栈

| 类别 | 选型 |
| --- | --- |
| 框架 | React 19 · Vite 8 · TypeScript |
| 样式 | Tailwind CSS 4 · shadcn/ui（new-york） |
| 路由 | react-router-dom 7 |
| 数据 | TanStack Query · 原生 fetch / SSE |
| 对话 UI | Vercel AI SDK · AI Elements 组件 |
| 图表 | Recharts |
| 工作流图 | @xyflow/react · Mermaid → Flow 自动布局 |

---

## 快速开始

### 前置条件

- Node.js >= 18
- 仓库根目录已按 [README 快速开始](../README.md#3-启动三个终端) 启动：
  - **终端 ①** FastAPI 后端（`:5173`，本前端代理目标）
  - **终端 ③** 即下方 `npm run dev`（`:5174`）
  - （可选）**终端 ②** `langgraph dev`（`:2024`，LangSmith 调试，与本看板独立）

```powershell
# 终端 ① — 在仓库根目录
.venv\Scripts\python server\main.py
```

### 安装与启动

```bash
cd web
npm install
npm run dev
```

- 开发地址：http://localhost:5174
- Vite 已将 `/api`、`/healthz`、`/readyz` 代理到 `http://localhost:5173`

### 构建

```bash
npm run build    # 输出到 dist/
npm run preview  # 预览生产构建
```

---

## 页面与路由

| 路由 | 页面 | 说明 |
| --- | --- | --- |
| `/` | 总览看板 | 调用量、Token、错误率、工具分布图表 |
| `/traces` | 任务链路 | 节点级 trace 列表；展开查看执行链路与耗时；点击节点打开详情弹窗 |
| `/graph` | 工作流图 | 从 `/api/graphs` 拉取 Mermaid，渲染为可缩放交互式 Flow |
| `/chat` | AI 对话 | SSE 流式对话；左侧会话历史；链路可视化（router → tool → summary） |

界面截图见仓库根目录 [`assest/`](../assest/) 与 [根 README · 运营看板预览](../README.md#运营看板预览)。

### 演示视频

| 视频 | 内容 |
| --- | --- |
| [演示 1](../assest/brainflow前端看板演示1.mp4) | 简单问答 + 天气查询（general_qa / weather 全链路） |
| [演示 2](../assest/brainflow前端看板演示2.mp4) | 财税日报生成（info_hunt → caishui-report；视频已裁切，实际等待更久） |

---

## 目录结构

```
web/
├── src/
│   ├── pages/
│   │   ├── overview/OverviewPage.tsx   总览看板
│   │   ├── traces/TracesPage.tsx       任务链路
│   │   ├── graph/GraphPage.tsx         工作流图
│   │   └── chat/ChatPage.tsx           AI 对话（主页面，逻辑最重）
│   ├── components/
│   │   ├── layout/                     侧栏导航 + 页头
│   │   ├── chat/                       历史侧边栏、欢迎页
│   │   ├── traces/                     链路详情弹窗
│   │   ├── workflow/                   工作流节点 / 时间线
│   │   ├── ai-elements/                对话与工作流 UI  primitives
│   │   └── ui/                         shadcn 基础组件
│   └── lib/
│       ├── api.ts                      看板 / 图 / SSE 流式对话
│       ├── chat-history.ts             会话 CRUD API
│       ├── chat-messages.ts            消息结构与持久化格式
│       ├── chat-workflow.ts            SSE step → 链路 UI 状态
│       ├── mermaid-to-flow.ts          Mermaid → React Flow
│       └── types.ts                    与后端对齐的类型
├── vite.config.ts                      dev 代理与 @ 别名
└── components.json                     shadcn 配置
```

---

## 依赖的后端 API

### 看板 / 观测

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/board` | 总览指标 |
| GET | `/api/tasks` | 任务链路列表 |
| GET | `/api/profiles` | 工具使用分析 |
| GET | `/api/analytics/usage` | 使用统计 |
| GET | `/api/logs?n=` | 最近日志 |
| GET | `/api/graphs` | 工作流 Mermaid 定义 |

### 对话

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/chat/stream` | SSE 流式对话（`step` / `reply` 事件） |
| GET | `/api/chat/sessions` | 会话列表 |
| POST | `/api/chat/sessions` | 新建会话 |
| GET | `/api/chat/sessions/:id` | 会话详情 + 历史消息 |
| POST | `/api/chat/sessions/:id/messages` | 追加消息 |
| DELETE | `/api/chat/sessions/:id` | 删除会话 |

---

## 开发说明

### 代理与端口

`vite.config.ts` 中 dev server 固定 **5174**，避免与后端 **5173** 冲突。修改后端端口时需同步改 `proxy` 目标。

### 新增 shadcn 组件

项目已配置 `components.json`，在 `web/` 目录下按 shadcn CLI 惯例添加组件即可（组件落在 `src/components/ui/`）。

### 与 LangSmith 的关系

本前端对接**内置 FastAPI + SQLite** 生产运维链路，**不直接连接 LangSmith**。开发调试、全链路 trace 分析请使用 LangSmith + `langgraph dev`，见 [根 README · 开发与运维](../README.md#开发与运维)。

---

## 常见问题

**页面空白或接口 502？**  
确认根目录已执行 `python server/main.py`，且 5173 可访问。

**对话无流式输出？**  
检查 `/api/chat/stream` 是否正常；浏览器 Network 面板应看到 `text/event-stream`。

**工作流图为空？**  
确认 `/api/graphs` 返回有效 Mermaid；后端 `src/graph.py` 需能正常构建图。

**生产部署？**  
`npm run build` 后可将 `dist/` 由 Nginx 等静态托管，并将 `/api` 反向代理到 FastAPI 后端。
