"""info_hunt 工具：政策/财税信息查询

财税日报（caishui-report skill）走本地 API；其余政策类查询暂返回引导说明。
Skill 定义：.agents/skills/caishui-report/SKILL.md
"""
import json
import re
import urllib.error
import urllib.request
from typing import Any

from config.settings import CAISHUI_REPORT_TIMEOUT, CAISHUI_REPORT_URL
from core.logs import get_logger

log = get_logger("info_hunt")

# caishui-report skill 触发词（与 SKILL.md 对齐）
CAISHUI_TRIGGERS = (
    "财税", "税收优惠", "税务", "优惠政策", "创业补贴", "政策补贴",
    "扶持资金", "机器人补贴", "ai补贴", "智能体补贴", "日报",
    "政策日报", "财税日报", "申报提醒", "资质入库", "科技型中小企业",
)

DEFAULT_REPORT_PARAMS: dict[str, Any] = {
    "user_id": "u_001",
    "name": "小匠世界",
    "industry": "儿童体验乐园,线下门店,机器人体验乐园",
    "platforms": ["线下门店", "小微企业"],
    "monthly_revenue": 18,
    "tax_identity": "有限公司_小规模",
    "province": "深圳",
    "current_anxiety": "税收优惠政策,创业补贴,AI智能体补贴,机器人开发补贴",
    "is_cross_border": False,
}

CITY_ALIASES = {
    "北京": "北京", "上海": "上海", "广州": "广州", "深圳": "深圳",
    "杭州": "杭州", "成都": "成都", "武汉": "武汉", "西安": "西安",
}


def _is_caishui_request(query: str) -> bool:
    q = query.lower()
    return any(kw.lower() in q for kw in CAISHUI_TRIGGERS)


def _decode_content_md(raw: str) -> str:
    if not raw:
        return ""
    text = raw
    if "\\n" in text or '\\"' in text:
        try:
            text = raw.encode("utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            text = raw.replace("\\n", "\n").replace('\\"', '"')
    return text.strip()


def _extract_params(query: str) -> dict[str, Any]:
    """从用户话术中覆盖默认参数（规则提取，轻量无 LLM 依赖）。"""
    params = dict(DEFAULT_REPORT_PARAMS)

    for city in CITY_ALIASES:
        if city in query:
            params["province"] = city
            break

    revenue_match = re.search(r"月营收\s*(\d+(?:\.\d+)?)\s*万", query)
    if revenue_match:
        params["monthly_revenue"] = float(revenue_match.group(1))

    name_match = re.search(r"(?:企业|公司|项目)(?:叫|是|名)?[「\"]?([^，。,\n「」\"]{2,20})[」\"]?", query)
    if name_match:
        params["name"] = name_match.group(1).strip()

    if "跨境" in query:
        params["is_cross_border"] = True

    params["current_anxiety"] = query[:200] or params["current_anxiety"]
    return params


def _post_report(payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        CAISHUI_REPORT_URL,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "BrainFlow/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=CAISHUI_REPORT_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _format_report_response(data: dict[str, Any]) -> str:
    content = _decode_content_md(str(data.get("content_md") or ""))
    if not content:
        return f"财税日报 API 返回成功，但未包含 content_md。原始响应：{json.dumps(data, ensure_ascii=False)[:500]}"

    score = data.get("quality_score", "—")
    verdict = data.get("quality_verdict", "—")
    duration = data.get("duration_sec", "—")
    report_id = data.get("report_id", "—")

    meta = (
        f"\n\n📊 报告质量评分：{score}/100  {verdict}  "
        f"|  ⏱️ 生成耗时：{duration}秒  |  报告ID：{report_id}"
    )
    return content + meta


def generate_caishui_report(query: str) -> str:
    params = _extract_params(query)
    log.info(f"财税日报请求: name={params['name']}, province={params['province']}")

    try:
        data = _post_report(params)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        return f"财税日报 API 错误 HTTP {e.code}：{detail}"
    except urllib.error.URLError as e:
        return (
            f"无法连接财税日报服务（{CAISHUI_REPORT_URL}）。"
            f"请确认 8101 端口服务已启动。详情：{e.reason}"
        )
    except TimeoutError:
        return "财税日报生成超时（>5 分钟），请稍后重试或检查服务负载。"
    except Exception as e:
        log.warning(f"财税日报失败: {e}")
        return f"财税日报生成失败：{e}"

    if data.get("status") != "success":
        return f"财税日报 API 返回异常：{json.dumps(data, ensure_ascii=False)[:500]}"

    return _format_report_response(data)


def _policy_search_placeholder(query: str) -> str:
    return (
        "[info_hunt] 政策检索能力开发中。\n"
        f"你的问题：{query[:120]}\n"
        "若需完整财税日报，请包含「财税日报」「创业补贴」「税收优惠」等关键词。"
    )


def query_info_hunt(query: str = "", **kwargs) -> str:
    """info_hunt 统一入口：财税日报优先，其余走政策检索占位。"""
    text = (query or kwargs.get("text") or "").strip()
    if not text:
        return "请描述你想查询的政策、补贴或财税信息，例如：生成深圳创业补贴财税日报"

    if _is_caishui_request(text):
        return generate_caishui_report(text)

    return _policy_search_placeholder(text)
