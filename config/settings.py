"""BrainFlow 全局配置：.env + 默认值"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# ---- LLM ----
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.7-flash")
LLM_ENABLE_THINKING = os.getenv("LLM_ENABLE_THINKING", "false").lower() in ("1", "true", "yes")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")

# ---- 数据 ----
DATA_DIR = ROOT / "data"
# DB 路径支持环境变量覆盖（测试/部署可指到可写目录）
DB_DIR = Path(os.getenv("DB_DIR", str(DATA_DIR)))
DB_OBSERVE = str(DB_DIR / "observe.db")

# ---- API ----
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "5173"))

# ---- Langfuse（可选，LLM 级可观测；配置 key 后自动启用，本地 Docker 自托管）----
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_ENABLED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)

# ---- 财税日报 API（caishui-report skill）----
CAISHUI_REPORT_URL = os.getenv(
    "CAISHUI_REPORT_URL", "http://127.0.0.1:8000/api/v1/generate-report"
)
CAISHUI_REPORT_TIMEOUT = int(os.getenv("CAISHUI_REPORT_TIMEOUT", "300"))

# ---- 微信（留空 = 未启用，后续实现）----
WECHAT_ACP_PATH = os.getenv("WECHAT_ACP_PATH", "")
