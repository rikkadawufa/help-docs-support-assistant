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

# Defaults reproduce the Cinderpeak demo exactly. An audit on someone else's documents sets the
# matching env vars instead of editing code (see audit/README.md, "Test assistants on new documents").
DEFAULT_BRAND = "Cinderpeak Outdoor"
DEFAULT_HANDOFF_REPLY = ("I couldn't find this in our help documents, so I've passed your question "
                         "to our support team. They'll reply by email within 1 business day.")
# Boilerplate stripped from every PDF page before chunking. An empty pattern strips nothing.
# A footer pattern may capture (?P<title>...), which is then put at the top of each chunk.
DEFAULT_PAGE_BANNER = r"^Cinderpeak Outdoor \| Help Center \| Fictional demo content\s*$"
DEFAULT_PAGE_FOOTER = r"^(?P<title>.+?) \| page \d+ of \d+\s*$"

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
    brand_name: str = DEFAULT_BRAND
    handoff_reply: str = DEFAULT_HANDOFF_REPLY
    knowledge_dir: Path = KNOWLEDGE_DIR
    index_name: str = ""            # "" = the demo's own index; any other name gets its own index
    page_banner: str = DEFAULT_PAGE_BANNER
    page_footer: str = DEFAULT_PAGE_FOOTER

    @property
    def _index_tag(self) -> str:
        return f"{self.index_name}-{self.llm_mode}" if self.index_name else self.llm_mode

    @property
    def chroma_dir(self) -> Path:
        return OUTPUT_DIR / f"chroma-{self._index_tag}"

    @property
    def manifest_path(self) -> Path:
        return OUTPUT_DIR / f"index-manifest-{self._index_tag}.json"

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
        brand_name=env.get("BRAND_NAME", DEFAULT_BRAND).strip() or DEFAULT_BRAND,
        handoff_reply=env.get("HANDOFF_REPLY", DEFAULT_HANDOFF_REPLY).strip() or DEFAULT_HANDOFF_REPLY,
        knowledge_dir=docs_path(env.get("KNOWLEDGE_DIR", "")),
        index_name=index_name(env.get("INDEX_NAME", "")),
        page_banner=env.get("PAGE_BANNER", DEFAULT_PAGE_BANNER),
        page_footer=env.get("PAGE_FOOTER", DEFAULT_PAGE_FOOTER),
    )


def docs_path(value: str) -> Path:
    """KNOWLEDGE_DIR as an absolute path; a relative one is taken from demo/."""
    if not value.strip():
        return KNOWLEDGE_DIR
    path = Path(value.strip())
    return path if path.is_absolute() else (ROOT / path).resolve()


def index_name(value: str) -> str:
    """Index names become folder names, so only letters, digits, - and _ are kept."""
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-")


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
