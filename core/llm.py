"""LLMClient：统一 LLM 入口（OpenAI SDK 直连，token 统计自主掌控 + 可选 Langfuse 观测）"""
import json
import time

from openai import OpenAI

from config.settings import (LLM_MODEL, LLM_API_KEY, LLM_BASE_URL,
                             LLM_ENABLE_THINKING,
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
        self._resolved_base_url = ""
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

    def _resolve_endpoint(self) -> tuple[str, str]:
        profile = get_profile(self._model)
        base_url = (profile or {}).get("base_url") or LLM_BASE_URL
        api_key = (profile or {}).get("api_key") or LLM_API_KEY
        return base_url or "", api_key or ""

    def warmup(self):
        """预热 HTTP 连接（避免首请求额外握手耗时计入 router）"""
        self._ensure_client()

    def _ensure_client(self):
        if self._client is None:
            base_url, api_key = self._resolve_endpoint()
            self._resolved_base_url = base_url
            self._client = OpenAI(base_url=base_url or None, api_key=api_key)
            log.info(json.dumps({
                "event": "llm_client_init",
                "model": self._model,
                "base_url": base_url,
                "stream_default": False,
            }, ensure_ascii=False))
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
            # 异步上报，避免阻塞主链路
            try:
                self._langfuse.flush()
            except Exception:
                pass
        except Exception as e:
            log.debug(f"Langfuse 上报失败（静默）: {e}")

    def chat(self, messages: list[dict], model: str = "", temperature: float = 0,
             max_tokens: int = 2048, tool_name: str = "", stream: bool = False,
             enable_thinking: bool | None = None) -> str:
        """同步非流式调用（stream=False）。Router/Summary 均等待完整响应后返回。"""
        t0 = time.time()
        t_client = time.time()
        client = self._ensure_client()
        client_ms = int((time.time() - t_client) * 1000)

        model = model or self._model
        if enable_thinking is None:
            enable_thinking = LLM_ENABLE_THINKING
        extra: dict = {"extra_body": {"enable_thinking": enable_thinking}}

        t_api = time.time()
        try:
            if stream:
                chunks: list[str] = []
                ttft_ms = None
                stream_resp = client.chat.completions.create(
                    model=model, messages=messages,
                    temperature=temperature, max_tokens=max_tokens,
                    stream=True, **extra,
                )
                for chunk in stream_resp:
                    if ttft_ms is None and chunk.choices:
                        ttft_ms = int((time.time() - t_api) * 1000)
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        chunks.append(delta)
                text = "".join(chunks).strip()
                usage = None
            else:
                resp = client.chat.completions.create(
                    model=model, messages=messages,
                    temperature=temperature, max_tokens=max_tokens,
                    stream=False, **extra,
                )
                text = (resp.choices[0].message.content or "").strip()
                usage = getattr(resp, "usage", None)
                ttft_ms = None

            api_ms = int((time.time() - t_api) * 1000)
            tokens = (usage.total_tokens if usage else 0) or 0
            prompt_tokens = (usage.prompt_tokens if usage else 0) or 0
            completion_tokens = (usage.completion_tokens if usage else 0) or 0
            reasoning_tokens = 0
            if usage and getattr(usage, "completion_tokens_details", None):
                reasoning_tokens = getattr(usage.completion_tokens_details,
                                           "reasoning_tokens", 0) or 0
            total_ms = int((time.time() - t0) * 1000)

            get_stats().record(tool_name or "llm", tokens=tokens, latency=total_ms / 1000)
            from core.tracing import get_tracer
            get_tracer().add_pending_tokens(tokens)

            log.info(json.dumps({
                "event": "llm_call",
                "tool": tool_name or "llm",
                "model": model,
                "base_url": self._resolved_base_url,
                "stream": stream,
                "enable_thinking": enable_thinking,
                "client_ms": client_ms,
                "api_ms": api_ms,
                "total_ms": total_ms,
                "ttft_ms": ttft_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "reasoning_tokens": reasoning_tokens,
                "total_tokens": tokens,
            }, ensure_ascii=False))

            self._record_langfuse(tool_name, model, messages, text, usage, total_ms / 1000)
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
