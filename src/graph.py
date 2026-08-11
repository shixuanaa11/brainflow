"""标准 LangGraph 工作流图（BrainFlow 核心）

结构：START → router 节点（LLM 意图识别）→ 条件边按 intent 分发
      → general_qa 节点（直出）或 工具节点 → summary 节点（LLM 总结）→ END
状态：MessagesState（单轮 invoke 内传递；不持久化会话记忆）
观测：core/tracing.py → data/observe.db（trace/span 记录输入输出）
"""
import sys
import time
from pathlib import Path

from langgraph.graph import END, START, MessagesState, StateGraph
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from config.prompts import GENERAL_QA_SYSTEM_PROMPT
from core.registry import get_registry
from core.router import RouterAgent
from core.stats import get_stats
from core.tracing import get_tracer
from core.llm import get_client
from prompts import SUMMARY_SYSTEM_PROMPT
from tools.wechat_tools import register_tools

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


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
        t0 = time.time()
        get_tracer().set_current_node("router")
        try:
            intent = router.classify(text)
            get_tracer().add_span("router", "router", time.time() - t0,
                                  status="ok", input_text=text, output_text=intent)
            get_stats().record("router", latency=time.time() - t0)
            return {"intent": intent}
        except Exception as e:
            get_tracer().add_span("router", "router", time.time() - t0,
                                  status="error", detail=str(e), input_text=text)
            raise
    return node


def make_tool_node(fn: callable, name: str):
    """工具节点：span 记录 输入(query)/输出(result)/耗时/状态；结果写入 tool_output，交 summary 节点总结"""
    def node(state: dict) -> dict:
        text = _last_user_text(state)
        t0 = time.time()
        get_tracer().set_current_node(name)
        try:
            result = str(fn(query=text))
            get_tracer().add_span(name, "tool", time.time() - t0,
                                  status="ok", input_text=text, output_text=result)
            get_stats().record(name, latency=time.time() - t0)
            return {
                "tool_output": result,
                "messages": [ToolMessage(content=result, name=name, tool_call_id=f"tool_{name}")],
            }
        except Exception as e:
            err = f"[错误] {name} 执行失败: {e}"
            get_tracer().add_span(name, "tool", time.time() - t0,
                                  status="error", detail=str(e), input_text=text)
            get_stats().record(name, error=str(e))
            return {
                "tool_output": err,
                "messages": [ToolMessage(content=err, name=name, tool_call_id=f"tool_{name}")],
            }
    return node


def make_general_qa_node():
    """general_qa 节点：通用问答直出，不经 stub 工具与 summary"""
    llm = get_client()

    def node(state: dict) -> dict:
        text = _last_user_text(state)
        t0 = time.time()
        get_tracer().set_current_node("general_qa")
        try:
            reply = llm.chat(
                messages=[{"role": "system", "content": GENERAL_QA_SYSTEM_PROMPT},
                          {"role": "user", "content": text}],
                tool_name="general_qa",
            )
            get_tracer().add_span("general_qa", "general_qa", time.time() - t0,
                                  status="ok", input_text=text, output_text=reply)
            get_stats().record("general_qa", latency=time.time() - t0)
            return {"messages": [AIMessage(content=reply)]}
        except Exception as e:
            fallback = f"抱歉，暂时无法回答：{e}"
            get_tracer().add_span("general_qa", "general_qa", time.time() - t0,
                                  status="error", detail=str(e), input_text=text)
            get_stats().record("general_qa", error=str(e))
            return {"messages": [AIMessage(content=fallback)]}
    return node


def make_summary_node():
    """summary 节点：LLM 总结工具结果；direct_reply 工具直接透传（跳过 LLM）"""
    llm = get_client()
    reg = get_registry()

    def node(state: dict) -> dict:
        text = _last_user_text(state)
        tool_output = state.get("tool_output", "")
        intent = state.get("intent", "")
        t0 = time.time()
        get_tracer().set_current_node("summary")

        if (reg.meta(intent).get("direct_reply")
                and tool_output
                and not tool_output.startswith("[错误]")):
            get_tracer().add_span("summary", "summary", time.time() - t0,
                                  status="ok", input_text=tool_output, output_text=tool_output,
                                  detail="direct_reply passthrough")
            get_stats().record("summary", latency=time.time() - t0)
            return {"messages": [AIMessage(content=tool_output)]}

        try:
            reply = llm.chat(
                messages=[{"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                          {"role": "user", "content": f"用户原话：{text}\n\n工具原始返回结果：\n{tool_output}"}],
                max_tokens=256, tool_name="summary",
            )
            get_tracer().add_span("summary", "summary", time.time() - t0,
                                  status="ok", input_text=tool_output, output_text=reply)
            get_stats().record("summary", latency=time.time() - t0)
            return {"messages": [AIMessage(content=reply)]}
        except Exception as e:
            fallback = tool_output or text
            get_tracer().add_span("summary", "summary", time.time() - t0,
                                  status="error", detail=str(e), input_text=tool_output)
            get_stats().record("summary", error=str(e))
            return {"messages": [AIMessage(content=fallback)]}
    return node


def _build_state_graph() -> StateGraph:
    register_tools()
    router = RouterAgent()
    reg = get_registry()

    g = StateGraph(WorkflowState)
    g.add_node("router", make_router_node(router))
    g.add_node("general_qa", make_general_qa_node())
    g.add_node("summary", make_summary_node())

    path_map: dict[str, str] = {"general_qa": "general_qa"}
    for name in reg.list_tools():
        if name == "general_qa":
            continue
        node_id = f"tool_{name}"
        g.add_node(node_id, make_tool_node(reg.get(name), name))
        path_map[name] = node_id
        g.add_edge(node_id, "summary")

    def route_by_intent(state: dict) -> str:
        intent = state.get("intent", "general_qa")
        return intent if intent in path_map else "general_qa"

    g.add_edge(START, "router")
    g.add_conditional_edges("router", route_by_intent, path_map)
    g.add_edge("general_qa", END)
    g.add_edge("summary", END)
    return g


_graph = None


def _compile_graph():
    return _build_state_graph().compile()


async def init_graph():
    """初始化工作流图（无 checkpointer，单轮无状态执行）"""
    global _graph
    if _graph is None:
        _graph = _compile_graph()
    return _graph


async def get_graph_async():
    if _graph is None:
        await init_graph()
    return _graph


def get_graph():
    """同步入口（langgraph.json / Studio / 测试）"""
    global _graph
    if _graph is None:
        _graph = _compile_graph()
    return _graph


def get_graph_mermaid() -> str:
    return _build_state_graph().compile().get_graph().draw_mermaid()
