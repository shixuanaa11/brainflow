"""LLM Profile 加载：多模型配置，${ENV} 注入，去硬编码"""
import os
import re
from pathlib import Path

import yaml

_PROFILE_FILE = Path(__file__).parent / "llm_profiles.yaml"
_PROFILES: dict = {}


def _resolve(value: str) -> str:
    return re.sub(r"\$\{(\w+)\}", lambda m: os.getenv(m.group(1), ""), str(value))


def load_profiles() -> dict:
    global _PROFILES
    if _PROFILES:
        return _PROFILES
    if _PROFILE_FILE.exists():
        raw = yaml.safe_load(_PROFILE_FILE.read_text(encoding="utf-8")) or {}
        for name, cfg in raw.get("profiles", {}).items():
            _PROFILES[name] = {
                "model": cfg["model"],
                "base_url": _resolve(cfg.get("base_url", "")),
                "api_key": _resolve(cfg.get("api_key", "")),
            }
    return _PROFILES


def get_profile(name: str = "") -> dict | None:
    profiles = load_profiles()
    if name and name in profiles:
        return profiles[name]
    default = profiles.get("default") or next(iter(profiles.values()), None)
    return profiles.get(default) if default else None
