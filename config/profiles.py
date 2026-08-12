"""LLM Profile 加载：扁平 llm_profiles.yaml，按 LLM_MODEL 名匹配"""
from pathlib import Path

import yaml

_PROFILE_FILE = Path(__file__).parent / "llm_profiles.yaml"
_PROFILES: dict[str, dict] | None = None


def _normalize_base_url(url: str) -> str:
    """OpenAI SDK 会自动追加 /chat/completions，去掉 yaml 里误写的完整路径"""
    url = (url or "").rstrip("/")
    suffix = "/chat/completions"
    if url.endswith(suffix):
        return url[: -len(suffix)]
    return url


def load_profiles() -> dict[str, dict]:
    global _PROFILES
    if _PROFILES is not None:
        return _PROFILES

    if not _PROFILE_FILE.exists():
        _PROFILES = {}
        return _PROFILES

    raw = yaml.safe_load(_PROFILE_FILE.read_text(encoding="utf-8")) or {}
    _PROFILES = {}
    for name, cfg in raw.items():
        if not isinstance(cfg, dict) or "model" not in cfg:
            continue
        _PROFILES[name] = {
            "model": str(cfg["model"]),
            "base_url": _normalize_base_url(str(cfg.get("base_url", ""))),
            "api_key": str(cfg.get("api_key", "")).strip(),
        }
    return _PROFILES


def get_llm_profile(name: str) -> dict:
    """按 profile 名（= .env LLM_MODEL）取配置；不存在则抛 KeyError"""
    profiles = load_profiles()
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "(empty)"
        raise KeyError(
            f"LLM profile '{name}' not found in llm_profiles.yaml. Available: {available}"
        )
    return profiles[name]


# 兼容旧调用
get_profile = get_llm_profile
