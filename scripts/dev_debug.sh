#!/usr/bin/env bash
# BrainFlow 调试环境一键启动：LangGraph Server + Studio + Agent Chat UI
#
# 用法:
#   bash scripts/dev_debug.sh            # 启动 langgraph dev（:2024）→ Studio
#   bash scripts/dev_debug.sh --chat-ui  # 额外创建并启动 Agent Chat UI（:3000）
#
# 前置: pip install -U "langgraph-cli[inmem]"   （或 uvx --from langgraph-cli@latest）
set -e
cd "$(dirname "$0")/.."

echo "=========================================="
echo " BrainFlow 调试环境"
echo "=========================================="

# 1. 启动 LangGraph Server（默认端口 2024）
echo "[1/2] 启动 LangGraph Server (langgraph dev)..."
echo "      终端输出会给出 Studio 链接（Graph ID: agent）"
langgraph dev &
LG_PID=$!
trap "kill $LG_PID 2>/dev/null" EXIT

# 等待服务就绪
for i in $(seq 1 30); do
  if curl -s http://127.0.0.1:2024/ok >/dev/null 2>&1; then
    echo "  ✅ LangGraph Server 就绪: http://127.0.0.1:2024"
    break
  fi
  sleep 1
done

echo ""
echo "  🎨 LangGraph Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024"
echo "  📚 API Docs:         http://127.0.0.1:2024/docs"

# 2. 可选：Agent Chat UI
if [ "$1" == "--chat-ui" ]; then
  echo ""
  echo "[2/2] 启动 Agent Chat UI..."
  if [ ! -d ".chat-ui" ]; then
    echo "      首次运行：npx create-agent-chat-app --project-name .chat-ui"
    npx create-agent-chat-app --project-name .chat-ui
    cd .chat-ui && pnpm install && cd ..
  fi
  echo "      启动中（:3000）..."
  cd .chat-ui && pnpm dev &
  CHAT_PID=$!
  trap "kill $LG_PID $CHAT_PID 2>/dev/null" EXIT
  echo ""
  echo "  💬 Agent Chat UI:  http://localhost:3000"
  echo "     → Deployment URL: http://127.0.0.1:2024"
  echo "     → Assistant ID:   agent"
fi

echo ""
echo "按 Ctrl+C 停止全部服务"
wait
