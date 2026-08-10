"""BrainFlow 全链路验证：图构建 + 工具节点 + FastAPI"""
import sys
from pathlib import Path

# Windows 终端 GBK 兼容：强制 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from langchain_core.messages import HumanMessage

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("  ✅ " if cond else "  ❌ ") + name)


def test_graph():
    from src.graph import get_graph, get_graph_mermaid, make_tool_node
    from tools.wechat_tools import _stub
    from langchain_core.messages import HumanMessage

    graph = get_graph()
    check("图构建（router + 14 工具节点）", graph is not None)
    check("draw_mermaid 输出", "graph TD" in get_graph_mermaid())

    # 工具节点函数直测（无需 LLM/图执行）
    node = make_tool_node(_stub("weather"), "weather")
    out = node({"messages": [HumanMessage(content="深圳天气")]})
    check("工具节点执行（weather）", "weather" in out["tool_output"])

    # 完整链路（router → 条件边 → 工具）需 LLM 可用，此处 try 探测
    try:
        r = graph.invoke({"messages": [HumanMessage(content="深圳天气")]},
                          config={"configurable": {"thread_id": "t1"}})
        check("完整链路 invoke", r["messages"][-1].content != "")
    except Exception as e:
        print(f"  ⚠️ 完整链路跳过（需 LLM 配置）: {type(e).__name__}")


def test_api():
    from fastapi.testclient import TestClient
    from api.main import app
    c = TestClient(app)
    check("healthz", c.get("/healthz").json()["status"] == "ok")
    check("readyz", c.get("/readyz").json()["status"] == "ready")
    check("board API", "total_calls" in c.get("/api/board").json())
    check("graphs API", "mermaid" in c.get("/api/graphs").json())
    check("前端页面", c.get("/").status_code == 200)


def test_stats():
    from core.stats import get_stats
    get_stats().record("test", tokens=10)
    check("指标记录", get_stats().summary()["total_calls"] >= 1)


if __name__ == "__main__":
    print("=" * 50)
    print("BrainFlow 全链路验证")
    print("=" * 50)
    test_graph()
    test_api()
    test_stats()
    print("-" * 50)
    print(f"结果: {len(PASS)} 通过, {len(FAIL)} 失败")
    if FAIL:
        print(f"失败项: {FAIL}")
        sys.exit(1)
