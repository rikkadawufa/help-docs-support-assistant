"""A record of everything that decides how the two test assistants answer, taken before any of the
client's questions are run. Its fingerprint is posted to the client first, so the time of that
message shows the assistants were fixed before the questions were asked.

The record holds the code (git commit plus a hash of app/, so uncommitted edits are caught), the
settings that change answers, both system prompts as sent, and a hash of every document. The index
manifest must match the documents, or the index was not rebuilt after they changed.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT, Settings
from .ingest import scan, sha256
from .llm import prompt

APP = ROOT / "app"
ANSWER_SETTINGS = ("llm_mode", "chat_model", "embed_model", "top_k", "relevance_min", "brand_name",
                   "handoff_reply", "degraded_reply", "page_banner", "page_footer", "index_name")


def _digest(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def code_hash() -> str:
    """Hash of every file under app/ (line endings normalized, so a checkout on another OS matches)."""
    files = sorted(p for p in APP.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return _digest({p.relative_to(APP).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                    for p in files})


def record(settings: Settings) -> dict:
    """The freeze record. Raises ValueError when the index does not match the documents."""
    docs = {name: sha256(path) for name, path in scan(settings.knowledge_dir).items()}
    if not docs:
        raise ValueError(f"no PDF or Markdown documents in {settings.knowledge_dir}")
    manifest = (json.loads(settings.manifest_path.read_text("utf-8"))
                if settings.manifest_path.exists() else {})
    if manifest != docs:
        raise ValueError(f"the index ({settings.manifest_path.name}) does not match the documents in "
                         f"{settings.knowledge_dir}; run scripts/ingest.py first")
    frozen = {
        "commit": _git("rev-parse", "HEAD"),
        "uncommitted_app_changes": bool(_git("status", "--porcelain", "--", "app")),
        "code_sha256": code_hash(),
        "settings": {k: getattr(settings, k) for k in ANSWER_SETTINGS},
        "prompts_sha256": {n: hashlib.sha256(prompt(n, settings.brand_name).encode("utf-8")).hexdigest()
                           for n in ("grounded", "baseline")},
        "documents": docs,
        "documents_sha256": _digest(docs),
    }
    return {"created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fingerprint": _digest(frozen), **frozen}


def verify(rec: dict) -> bool:
    """True when the fingerprint still matches the rest of the record (nothing was edited by hand)."""
    body = {k: v for k, v in rec.items() if k not in ("created", "fingerprint")}
    return rec.get("fingerprint") == _digest(body)
