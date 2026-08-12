"""Job 终态投递：构建 outbox 载荷、大结果外置"""
from pathlib import Path

from config.settings import DB_DIR

RESULT_INLINE_MAX = 8000
RESULT_DIR = DB_DIR / "job_results"


def async_receipt_text(tool_name: str, job_id: str) -> str:
    return (
        f"已受理，任务 `{job_id}` 已在后台执行（{tool_name}）。"
        "你可以离开本页，完成后结果会自动出现在对话中。"
    )


def build_async_submit_message(
    tool_name: str,
    job_id: str,
    user_query: str,
    receipt: str | None = None,
) -> dict:
    """LangGraph 异步 turn：submit 阶段写入唯一 assistant 消息"""
    node_name = f"tool_{tool_name}"
    text = receipt or async_receipt_text(tool_name, job_id)
    return {
        "role": "assistant",
        "content": text,
        "meta": {
            "job_id": job_id,
            "job_status": "submitted",
            "tool": tool_name,
            "steps": [
                {
                    "node": "router",
                    "kind": "router",
                    "label": "意图识别 (router)",
                    "status": "done",
                },
                {
                    "node": node_name,
                    "kind": "tool",
                    "label": f"工具调用 ({tool_name})",
                    "status": "running",
                },
            ],
            "tools": [{
                "name": tool_name,
                "state": "input-available",
                "input": {"query": user_query},
            }],
        },
    }


def persist_large_result(job_id: str, result: str) -> tuple[str, str]:
    """返回 (db_result, result_ref)；小结果 result_ref 为空"""
    if len(result) <= RESULT_INLINE_MAX:
        return result, ""
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    ref = RESULT_DIR / f"{job_id}.txt"
    ref.write_text(result, encoding="utf-8")
    preview = (
        result[:500]
        + f"\n\n…（完整结果已外置，共 {len(result)} 字，见 result_ref）"
    )
    return preview, str(ref)


def build_chat_result_update_payload(
    session_id: str,
    job_id: str,
    tool_name: str,
    user_query: str,
    result: str,
    result_ref: str = "",
) -> dict:
    """终态更新原受理消息，不追加第二条 assistant"""
    meta = {
        "job_id": job_id,
        "job_status": "done",
        "tool": tool_name,
        "steps": [
            {
                "node": "router",
                "kind": "router",
                "label": "意图识别 (router)",
                "status": "done",
            },
            {
                "node": f"tool_{tool_name}",
                "kind": "tool",
                "label": f"工具调用 ({tool_name})",
                "status": "done",
                "output": result[:500],
            },
        ],
        "tools": [{
            "name": tool_name,
            "state": "output-available",
            "input": {"query": user_query},
            "output": result[:2000],
        }],
    }
    if result_ref:
        meta["result_ref"] = result_ref
    return {
        "session_id": session_id,
        "job_id": job_id,
        "content": result,
        "meta": meta,
    }


def build_chat_result_payload(
    session_id: str,
    job_id: str,
    tool_name: str,
    user_query: str,
    result: str,
    result_ref: str = "",
) -> dict:
    """兼容旧 outbox 条目；新投递请用 build_chat_result_update_payload"""
    return build_chat_result_update_payload(
        session_id, job_id, tool_name, user_query, result, result_ref,
    )


def build_chat_error_update_payload(
    session_id: str,
    job_id: str,
    tool_name: str,
    err: str,
    status: str = "error",
) -> dict:
    content = f"任务 {job_id} 执行失败：{err}"
    return {
        "session_id": session_id,
        "job_id": job_id,
        "content": content,
        "meta": {
            "job_id": job_id,
            "job_status": status,
            "tool": tool_name,
            "tools": [{
                "name": tool_name,
                "state": "output-error",
                "input": {},
                "errorText": err,
            }],
        },
    }


def build_chat_error_payload(
    session_id: str,
    job_id: str,
    tool_name: str,
    err: str,
    status: str = "error",
) -> dict:
    return build_chat_error_update_payload(
        session_id, job_id, tool_name, err, status=status,
    )
