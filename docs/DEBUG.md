# BrainFlow 调试前端接入指南（Studio + Agent Chat UI）

> 这两个前端是 **LangGraph 官方外部工具**，不是本项目内置代码。它们通过 `langgraph.json` 注册的图入口与 BrainFlow 对接，调试所见即生产所跑（同一份图定义）。

---

## 1. LangGraph Studio（图可视化 + 节点调试）

**是什么**：官方 Agent IDE。图模式可看到完整工作流图（router → 条件边 → 14 工具节点），逐节点调试（查看中间状态、输入输出）。

**启动**：

```bash
pip install -U "langgraph-cli[inmem]"
langgraph dev          # 默认端口 2024
```

启动后终端输出：

```
🚀 API: http://127.0.0.1:2024
🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
📚 API Docs: http://127.0.0.1:2024/docs
```

**使用**：
1. 浏览器打开 Studio 链接（或 smith.langchain.com/studio）
2. Graph 选择 `agent`（对应 `langgraph.json` 里的图入口）
3. 图模式：可视化完整图；运行后查看每个节点的状态/输入/输出
4. 聊天模式：直接输入消息测试（走 router 节点 → LLM 意图识别 → 工具节点）

**本项目对接点**：`langgraph.json`

```json
{
  "graphs": { "agent": "./src/graph.py:get_graph" }
}
```

---

## 2. Agent Chat UI（官方聊天调试界面）

**是什么**：官方开源聊天应用（Next.js），连接任何带 `messages` 键的 LangGraph 服务器。我们的图是 MessagesState，原生兼容。

**创建并启动**：

```bash
npx create-agent-chat-app --project-name my-chat-ui
cd my-chat-ui
pnpm install
pnpm dev              # http://localhost:3000
```

**连接配置**（打开页面后填写）：

| 配置项 | 值 |
| --- | --- |
| Deployment URL | `http://127.0.0.1:2024`（langgraph dev 地址） |
| Assistant ID | `agent`（langgraph.json 里的图 id） |
| LangSmith API Key | 可选（本地调试不需要） |

**使用**：在聊天框输入消息（如"深圳今天天气怎么样"）→ 走完整链路：router 节点（LLM 意图识别）→ 条件边分发 → 工具节点 → 回复。

---

## 3. 一键脚本

```bash
bash scripts/dev_debug.sh            # 启动 langgraph dev + Studio 链接
bash scripts/dev_debug.sh --chat-ui  # 额外创建并启动 Agent Chat UI
```

---

## 4. LangSmith（可选，链路追踪）

`.env` 配置后自动上报：

```env
LANGSMITH_API_KEY=lsv2_xxx
LANGSMITH_PROJECT=brainflow
LANGSMITH_TRACING=true
```

---

## 5. 前端分工

| 前端 | 类型 | 场景 | 启动 |
| --- | --- | --- | --- |
| 运营看板（`web/`） | 自研 | **生产**（对话/图/看板/Job） | `cd web && npm run dev` |
| LangGraph Studio | 官方 IDE | **调试**（图可视化） | `langgraph dev` |
| Agent Chat UI | 官方应用 | **调试**（聊天） | `npx create-agent-chat-app` + `pnpm dev` |
