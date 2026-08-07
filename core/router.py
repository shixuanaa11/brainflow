"""RouterAgent：LLM 意图识别（标准图中 router 节点的实现）"""
import json

from config.prompts import ROUTER_SYSTEM_PROMPT_TEMPLATE
from core.llm import get_client
from core.logs import get_logger
from core.registry import get_registry

log = get_logger("router")


class RouterAgent:
    def __init__(self):
        self.llm = get_client()

    def _tool_list(self) -> str:
        """① 动态工具清单：id + 描述 + 触发词（注册表自动生成）"""
        reg = get_registry()
        lines = []
        for name in reg.list_tools():
            meta = reg.meta(name)
            kw = "，".join(meta.get("keywords", []))
            desc = meta.get("desc", "")
            lines.append(f"- {name}: {desc}（触发词：{kw}）" if kw else f"- {name}: {desc}")
        return "\n".join(lines)

    def _few_shot(self) -> str:
        """② few-shot：每工具 1 条真实例句"""
        reg = get_registry()
        out = []
        for name in reg.list_tools():
            for ex in reg.meta(name).get("examples", [])[:1]:
                out.append(f"用户：{ex}\n输出：{{\"intent\": \"{name}\", \"reason\": \"...\"}}")
        return "\n".join(out[:20])

    def classify(self, text: str) -> str:
        """LLM 意图识别 + 白名单校验（防幻觉，回退 general_qa 不抛错）"""
        system = ROUTER_SYSTEM_PROMPT_TEMPLATE.format(
            tool_list=self._tool_list(), few_shot=self._few_shot())
        raw = self.llm.chat(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": text}],
            max_tokens=100, tool_name="router",
        )
        try:
            intent = str(json.loads(raw).get("intent", "general_qa"))
        except json.JSONDecodeError:
            log.warning(f"意图输出非 JSON，回退 general_qa: {raw[:50]}")
            intent = "general_qa"

        if intent not in get_registry().list_tools():
            log.warning(f"意图不在白名单，回退 general_qa: {intent}")
            return "general_qa"
        log.info(f"意图识别: {intent}")
        return intent
