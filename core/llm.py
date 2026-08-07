"""LLMClient：统一 LLM 入口（OpenAI SDK 直连，token 统计自主掌控 + 可选 Langfuse 观测）"""
import time

from openai import OpenAI

from config.settings import (LLM_MODEL, LLM_API_KEY, LLM_BASE_URL,
                             LANGFUSE_ENABLED, LANGFUSE_HOST,
                             LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)
from config.profiles import get_profile
from core.logs import get_logger
from core.stats import get_stats

log = get_logger("llm")


class LLMClient:
    def __init__(self):
        self._client = None
        self._model = LLM_MODEL
        self._langfuse = self._init_langfuse()

    @staticmethod
    def _init_langfuse():
        """Langfuse 可选：配置了 key 才启用；失败自动降级（不影响主流程）"""
        if not LANGFUSE_ENABLED:
            return None
        try:
            from langfuse import Langfuse
            lf = Langfuse(public_key=LANGFUSE_PUBLIC_KEY,
                          secret_key=LANGFUSE_SECRET_KEY,
                          host=LANGFUSE_HOST)
            log.info(f"Langfuse 已启用: {LANGFUSE_HOST}")
            return lf
        except Exception as e:
            log.warning(f"Langfuse 初始化失败（跳过，不影响主流程）: {e}")
            return None

    def _ensure_client(self):
        if self._client is None:
            profile = get_profile(self._model)
            base_url = (profile or {}).get("base_url") or LLM_BASE_URL
            api_key = (profile or {}).get("api_key") or LLM_API_KEY
            self._client = OpenAI(base_url=base_url or None, api_key=api_key)
        return self._client

    def _record_langfuse(self, name: str, model: str, messages: list[dict],
                         text: str, usage, latency: float):
        """Langfuse generation 记录（失败静默，不影响主流程）"""
        if self._langfuse is None:
            return
        try:
            usage_dict = None
            if usage is not None:
                usage_dict = {"input": getattr(usage, "prompt_tokens", 0) or 0,
                              "output": getattr(usage, "completion_tokens", 0) or 0,
                              "total": getattr(usage, "total_tokens", 0) or 0}
            gen = self._langfuse.generation(
                name=name or "llm", model=model,
                input=messages, output=text,
                usage=usage_dict,
                metadata={"latency_ms": int(latency * 1000)},
            )
            gen.end()
            self._langfuse.flush()   # 立即发送（本地低吞吐场景）
        except Exception as e:
            log.debug(f"Langfuse 上报失败（静默）: {e}")

    def chat(self, messages: list[dict], model: str = "", temperature: float = 0,
             max_tokens: int = 2048, tool_name: str = "") -> str:
        client = self._ensure_client()
        model = model or self._model
        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
            text = (resp.choices[0].message.content or "").strip()
            usage = getattr(resp, "usage", None)
            tokens = (usage.total_tokens if usage else 0) or 0
            get_stats().record(tool_name or "llm", tokens=tokens,
                               latency=time.time() - t0)
            # 可观测①：token 暂存到当前节点（内置面板 span 插入时合并）
            from core.tracing import get_tracer
            get_tracer().add_pending_tokens(tokens)
            # 可观测②：Langfuse generation（可选，LLM 级深度 trace/成本）
            self._record_langfuse(tool_name, model, messages, text,
                                  usage, time.time() - t0)
            return text
        except Exception as e:
            get_stats().record(tool_name or "llm", error=str(e),
                               latency=time.time() - t0)
            log.error(f"LLM 调用失败: {e}")
            raise


_client: LLMClient | None = None


def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
