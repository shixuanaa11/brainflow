"""打印当前 LLM_MODEL 对应的 api_key / base_url（对齐 GJS 模型配置规范）"""
import os
from pathlib import Path

from dotenv import load_dotenv

from config.profiles import get_llm_profile

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3.7-flash")
_active = get_llm_profile(LLM_MODEL)
print(_active["api_key"])
print(_active["base_url"])
