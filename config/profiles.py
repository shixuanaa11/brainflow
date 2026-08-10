"""LLM Profile 加载：多模型配置，${ENV} 注入，去硬编码"""
import os
import re
from pathlib import Path

import yaml

_PROFILE_FILE = Path(__file__).parent / "llm_profiles.yaml"
_PROFILES: dict = {}
_DEFAULT_NAME: str = ""


def _resolve(value: str) -> str:
    return re.sub(r"\$\{(\w+)\}", lambda m: os.getenv(m.group(1), ""), str(value))


def load_profiles() -> dict:
    global _PROFILES, _DEFAULT_NAME
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
        # YAML 顶层 default 是 profile 名（字符串），不是 profiles 里的条目
        default = raw.get("default", "")
        if isinstance(default, str) and default in _PROFILES:
            _DEFAULT_NAME = default
        elif _PROFILES:
            _DEFAULT_NAME = next(iter(_PROFILES))
    return _PROFILES


def get_profile(name: str = "") -> dict | None:
    profiles = load_profiles()
    if name and name in profiles:
        return profiles[name]
    if _DEFAULT_NAME and _DEFAULT_NAME in profiles:
        return profiles[_DEFAULT_NAME]
    return next(iter(profiles.values()), None) if profiles else None
