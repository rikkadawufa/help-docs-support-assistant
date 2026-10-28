"""Send a question to the human support team.

Every handoff is appended to output/handoff-log.jsonl. With SLACK_MODE=slack it
is also posted to the Slack webhook. A Slack failure never breaks the reply."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from .config import OUTPUT_DIR, Settings, mask
from .store import Retrieved

LOG_PATH = OUTPUT_DIR / "handoff-log.jsonl"

REASON_TEXT = {
    "low_relevance": "No help document matched the question closely enough",
    "model_declined": "The documents don't answer this question",
    "no_valid_citation": "The AI's answer could not be traced back to a document",
    "user_requested": "The customer asked to talk to a person",
    "llm_error": "The AI service failed",
}


def slack_text(question: str, reason: str, retrieved: list[Retrieved], request_id: str, note: str = "") -> str:
    lines = [
        f":raising_hand: *Support handoff* ({REASON_TEXT.get(reason, reason)})",
        f"*Question:* {question}",
    ]
    if note:
        lines.append(f"*Customer note:* {note}")
    if retrieved:
        lines.append("*Closest document passages:*")
        for r in retrieved[:3]:
            snippet = " ".join(r.text.split())[:160]
            lines.append(f"> `{r.label()}` (score {r.score:.2f}) {snippet}...")
    else:
        lines.append("_No passages retrieved._")
    lines.append(f"_request {request_id}_")
    return "\n".join(lines)


def notify(settings: Settings, question: str, reason: str, retrieved: list[Retrieved],
           request_id: str, note: str = "") -> dict:
    entry = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "request_id": request_id, "reason": reason, "question": question, "note": note,
        "passages": [r.chunk_id for r in retrieved[:3]], "slack": "skipped",
    }
    if settings.slack_mode == "slack" and settings.slack_webhook_url:
        try:
            resp = httpx.post(settings.slack_webhook_url,
                              json={"text": slack_text(question, reason, retrieved, request_id, note)},
                              timeout=5)
            entry["slack"] = "sent" if resp.status_code == 200 else f"http_{resp.status_code}"
        except httpx.HTTPError as exc:
            entry["slack"] = "error: " + mask(type(exc).__name__)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry
