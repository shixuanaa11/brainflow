"""BrainFlow 主入口：uvicorn 起 FastAPI（+ 微信能力留空，后续实现）

用法：
  python server/main.py                  # 启动 API 服务
  python server/main.py --cli "消息"      # CLI 模式直接测试
"""
import argparse
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import API_HOST, API_PORT
from core.logs import get_logger
from src.graph import get_graph

log = get_logger("main")


def run_once(text: str, user_id: str = "") -> str:
    """单次执行：graph.invoke（标准 API）"""
    from langchain_core.messages import HumanMessage
    from core.tracing import get_tracer

    get_tracer().start_trace("agent", text, user_id)
    try:
        result = get_graph().invoke(
            {"messages": [HumanMessage(content=text)]},
            config={"configurable": {"thread_id": user_id or "default"}},
        )
        get_tracer().end_trace("ok")
        for m in reversed(result["messages"]):
            if getattr(m, "type", "") == "ai":
                return m.content or ""
        return ""
    except Exception as e:
        get_tracer().end_trace("error", str(e))
        log.error(f"执行失败: {e}")
        return f"执行出错: {e}"


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="BrainFlow 智脑流")
    parser.add_argument("--cli", help="CLI 模式：处理一条消息")
    parser.add_argument("--no-api", action="store_true", help="不启动 API 服务")
    args = parser.parse_args()

    get_graph()   # 预热：注册工具 + 编译图
    log.info("工作流图就绪（router → 条件边 → 14 工具节点）")

    if args.cli:
        print(run_once(args.cli, user_id="cli"))
        return

    if not args.no_api:
        threading.Thread(target=lambda: uvicorn.run(
            "api.main:app", host=API_HOST, port=API_PORT,
            log_level="info"), daemon=True).start()
        log.info(f"API: http://localhost:{API_PORT}（Swagger: /docs）")
        log.info("⚠️ 微信接入能力留空（WECHAT_ACP_PATH 未配置），后续实现")

    # 微信能力留空：此处后续接入 WeChatBridge（weixin-acp）
    try:
        while True:
            import time
            time.sleep(3600)
    except KeyboardInterrupt:
        log.info("退出 BrainFlow")


if __name__ == "__main__":
    main()
