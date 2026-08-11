"""RouterAgent：LLM 意图识别（标准图中 router 节点的实现）"""
import json
import re

from config.prompts import (
    ROUTER_DISAMBIGUATION,
    ROUTER_FEW_SHOT_STATIC,
    ROUTER_GENERAL_QA,
    ROUTER_MUST_MATCH,
    ROUTER_OUTPUT_RULES,
    ROUTER_ROLE_SKILLS_LIMITS,
    ROUTER_SYSTEM_PROMPT_TEMPLATE,
)
from core.llm import get_client
from core.logs import get_logger
from core.registry import get_registry

log = get_logger("router")

_JSON_BLOCK = re.compile(r"\{[^{}]*\"intent\"[^{}]*\}", re.DOTALL)

# LLM 偶发中文 intent → 英文 id 映射
INTENT_ALIASES = {
    "天气": "weather", "天气工具": "weather",
    "新闻": "news", "新闻工具": "news",
    "信息查询": "info_hunt", "经营数据": "jingying_data",
    "b站上传": "bilibili_upload", "b站评论": "bilibili_comment",
    "抖音发布": "douyin_publish", "抖音评论": "douyin_comment",
    "互动屏": "interactive_screen", "演示模式": "demo_mode",
    "全屏": "fullscreen", "任务看板": "task_kanban",
    "小匠机器人": "xiaojiang_robot", "小匠": "xiaojiang_robot",
    "通用问答": "general_qa",
}


class RouterAgent:
    def __init__(self):
        self.llm = get_client()
        self._system_prompt: str | None = None

    def _tool_catalog(self) -> str:
        """紧凑工具目录"""
        reg = get_registry()
        lines = ["【工具 id 列表】"]
        for name in reg.list_tools():
            if name == "general_qa":
                continue
            meta = reg.meta(name)
            kw = "、".join(meta.get("keywords", [])[:5])
            hint = meta.get("router_hint") or meta.get("desc", "")
            lines.append(f"- `{name}`: {hint}" + (f"（{kw}）" if kw else ""))
        lines.append("- `general_qa`: 闲聊兜底")
        return "\n".join(lines)

    def _build_system_prompt(self) -> str:
        return ROUTER_SYSTEM_PROMPT_TEMPLATE.format(
            role_skills_limits=ROUTER_ROLE_SKILLS_LIMITS,
            tool_catalog=self._tool_catalog(),
            must_match=ROUTER_MUST_MATCH,
            disambiguation=ROUTER_DISAMBIGUATION,
            general_qa=ROUTER_GENERAL_QA,
            output_rules=ROUTER_OUTPUT_RULES,
            few_shot=ROUTER_FEW_SHOT_STATIC,
        )

    def _system_prompt_text(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = self._build_system_prompt()
        return self._system_prompt

    def _normalize_intent(self, intent: str) -> str:
        intent = (intent or "").strip()
        if intent in get_registry().list_tools():
            return intent
        alias = INTENT_ALIASES.get(intent) or INTENT_ALIASES.get(intent.lower())
        if alias:
            return alias
        # 模糊：intent 含工具 id 子串
        for name in get_registry().list_tools():
            if name in intent or intent in name:
                return name
        return intent

    @staticmethod
    def _parse_intent(raw: str) -> str:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = text.strip("`").replace("json", "", 1).strip()
        # 取最后一个 JSON 块（避免 thinking 文本干扰）
        blocks = _JSON_BLOCK.findall(text)
        if blocks:
            text = blocks[-1]
        data = json.loads(text)
        return str(data.get("intent", "general_qa"))

    def classify(self, text: str) -> str:
        """LLM 意图识别 + 白名单校验（始终走 LLM，关闭 thinking 加速）"""
        raw = self.llm.chat(
            messages=[{"role": "system", "content": self._system_prompt_text()},
                      {"role": "user", "content": text}],
            max_tokens=32, tool_name="router",
        )
        try:
            intent = self._normalize_intent(self._parse_intent(raw))
        except (json.JSONDecodeError, ValueError, KeyError):
            log.warning(f"意图 JSON 解析失败，回退 general_qa | raw={raw[:120]!r}")
            intent = "general_qa"

        if intent not in get_registry().list_tools():
            log.warning(f"意图不在白名单，回退 general_qa | intent={intent!r} raw={raw[:120]!r}")
            return "general_qa"
        log.info(f"LLM 意图识别: {intent}")
        return intent
