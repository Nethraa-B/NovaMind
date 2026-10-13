import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


DATABASE_URL = _get_env(
    "DATABASE_URL",
    f"sqlite:///{(BASE_DIR / 'data' / 'novamind.db').as_posix()}",
)
CHROMA_PERSIST_DIR = _get_env("CHROMA_PERSIST_DIR", str(BASE_DIR / "chroma"))
LLM_PROVIDER = _get_env("LLM_PROVIDER", "openai_compatible")
LLM_API_KEY = _get_env("LLM_API_KEY", "")
LLM_BASE_URL = _get_env("LLM_BASE_URL", "")
LLM_MODEL_NAME = _get_env("LLM_MODEL_NAME", "")


def ensure_directories() -> None:
    Path(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
