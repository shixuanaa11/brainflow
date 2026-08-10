"""标准 LangGraph 工作流图（BrainFlow 核心）

结构：START → router 节点（LLM 意图识别）→ 条件边按 intent 分发 → 工具节点 → summary 节点（LLM 总结）→ END
状态：MessagesState（对话历史，Studio Chat / Agent Chat UI 原生兼容）
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langchain_core.messages import AIMessage, HumanMessage

from core.registry import get_registry
from core.router import RouterAgent
from core.stats import get_stats
from core.tracing import get_tracer
from core.llm import get_client
from prompts import SUMMARY_SYSTEM_PROMPT
from tools.wechat_tools import register_tools


class WorkflowState(MessagesState):
    intent: str        # router 节点写入：意图识别结果
    tool_output: str   # 工具节点写入：工具返回


def _last_user_text(state: dict) -> str:
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            return m.content or ""
    return ""


def make_router_node(router: RouterAgent):
    """router 节点：LLM 意图识别，span 记录 输入(用户消息)/输出(intent)/token(自动挂)"""
    def node(state: dict) -> dict:
        text = _last_user_text(state)
        t0 = __import__("time").time()
        get_tracer().set_current_node("router")
        try:
            intent = router.classify(text)
            get_tracer().add_span("router", "router", __import__("time").time() - t0,
                                  status="ok", input_text=text, output_text=intent)
            get_stats().record("router", latency=__import__("time").time() - t0)
            return {"intent": intent}
        except Exception as e:
            get_tracer().add_span("router", "router", __import__("time").time() - t0,
                                  status="error", detail=str(e), input_text=text)
            raise
    return node


def make_tool_node(fn: callable, name: str):
    """工具节点：span 记录 输入(query)/输出(result)/耗时/状态；结果写入 tool_output，交 summary 节点总结"""
    def node(state: dict) -> dict:
        text = _last_user_text(state)
        t0 = __import__("time").time()
        get_tracer().set_current_node(name)
        try:
            result = str(fn(query=text))
            get_tracer().add_span(name, "tool", __import__("time").time() - t0,
                                  status="ok", input_text=text, output_text=result)
            get_stats().record(name, latency=__import__("time").time() - t0)
            return {"tool_output": result}
        except Exception as e:
            get_tracer().add_span(name, "tool", __import__("time").time() - t0,
                                  status="error", detail=str(e), input_text=text)
            get_stats().record(name, error=str(e))
            raise
    return node


def make_summary_node():
    """summary 节点：LLM 把工具原始结果总结为面向用户的回复（原话 + 工具结果 → 最终答复）"""
    llm = get_client()

    def node(state: dict) -> dict:
        text = _last_user_text(state)
        tool_output = state.get("tool_output", "")
        t0 = __import__("time").time()
        get_tracer().set_current_node("summary")
        try:
            reply = llm.chat(
                messages=[{"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                          {"role": "user", "content": f"用户原话：{text}\n\n工具原始返回结果：\n{tool_output}"}],
                tool_name="summary",
            )
            get_tracer().add_span("summary", "summary", __import__("time").time() - t0,
                                  status="ok", input_text=tool_output, output_text=reply)
            get_stats().record("summary", latency=__import__("time").time() - t0)
            return {"messages": [AIMessage(content=reply)]}
        except Exception as e:
            # LLM 总结失败时降级：直接透传工具结果，保证用户有回复
            fallback = tool_output or text
            get_tracer().add_span("summary", "summary", __import__("time").time() - t0,
                                  status="error", detail=str(e), input_text=tool_output)
            get_stats().record("summary", error=str(e))
            return {"messages": [AIMessage(content=fallback)]}
    return node


def build_graph():
    """构建标准工作流图（唯一图，生产/调试共用）"""
    register_tools()
    router = RouterAgent()
    reg = get_registry()

    g = StateGraph(WorkflowState)
    g.add_node("router", make_router_node(router))
    g.add_node("summary", make_summary_node())

    path_map: dict[str, str] = {}
    for name in reg.list_tools():
        node_id = f"tool_{name}"
        g.add_node(node_id, make_tool_node(reg.get(name), name))
        path_map[name] = node_id
        g.add_edge(node_id, "summary")

    def route_by_intent(state: dict) -> str:
        """条件边路由：返回 path_map 的键（intent），LangGraph 用它查节点名"""
        intent = state.get("intent", "general_qa")
        return intent if intent in path_map else "general_qa"

    g.add_edge(START, "router")
    g.add_conditional_edges("router", route_by_intent, path_map)
    g.add_edge("summary", END)
    return g.compile(checkpointer=MemorySaver())   # 生产切 SqliteSaver


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def get_graph_mermaid() -> str:
    """工作流图可视化：官方 draw_mermaid()（零依赖）"""
    return get_graph().get_graph().draw_mermaid()
