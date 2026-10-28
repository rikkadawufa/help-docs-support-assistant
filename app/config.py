"""Settings read from demo/.env. Secrets never leave this module unmasked."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"
OUTPUT_DIR = ROOT / "output"

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_mode: str = "mock"          # mock | live
    slack_mode: str = "log"         # log | slack
    chat_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-3-small"
    top_k: int = 5
    relevance_min: float = 0.35
    openai_api_key: str = ""
    slack_webhook_url: str = ""

    @property
    def chroma_dir(self) -> Path:
        return OUTPUT_DIR / f"chroma-{self.llm_mode}"

    @property
    def manifest_path(self) -> Path:
        return OUTPUT_DIR / f"index-manifest-{self.llm_mode}.json"

    def with_overrides(self, **kwargs) -> "Settings":
        return replace(self, **kwargs)


def load_settings() -> Settings:
    env = os.environ
    return Settings(
        llm_mode=env.get("LLM_MODE", "mock").strip().lower(),
        slack_mode=env.get("SLACK_MODE", "log").strip().lower(),
        chat_model=env.get("CHAT_MODEL", "gpt-4o-mini").strip(),
        embed_model=env.get("EMBED_MODEL", "text-embedding-3-small").strip(),
        top_k=int(env.get("TOP_K", "5")),
        relevance_min=float(env.get("RELEVANCE_MIN", "0.35")),
        openai_api_key=env.get("OPENAI_API_KEY", "").strip(),
        slack_webhook_url=env.get("SLACK_WEBHOOK_URL", "").strip(),
    )


_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"https://hooks\.slack\.com/\S+"),
]


def mask(text: str) -> str:
    """Replace anything that looks like an API key or webhook URL with ***."""
    out = str(text)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("***", out)
    return out
