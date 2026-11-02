"""Chat model factory. LLM_MODE=mock returns canned replies so the whole app
and the eval can run offline without spending API credit."""
from __future__ import annotations

import re
from pathlib import Path

from .config import DEFAULT_BRAND, Settings

PROMPTS = Path(__file__).resolve().parent / "prompts"

GROUNDED_SCHEMA = {
    "title": "GroundedAnswer",
    "description": "Answer built only from the provided help-document passages.",
    "type": "object",
    "properties": {
        "answerable": {"type": "boolean", "description": "True only if the passages clearly answer the question."},
        "answer": {"type": "string", "description": "Short answer, or empty when answerable is false."},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_id": {"type": "string"},
                    "quote": {"type": "string", "description": "Word-for-word text from that passage."},
                },
                "required": ["chunk_id", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answerable", "answer", "citations"],
    "additionalProperties": False,
}


def prompt(name: str, brand: str = DEFAULT_BRAND) -> str:
    """The system prompt with the business name filled in. Plain replacement, not str.format(),
    so braces elsewhere in a prompt are left alone."""
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8").replace("{brand}", brand)


def format_passages(passages) -> str:
    return "\n\n".join(f"[chunk_id: {p.chunk_id}] ({p.label()})\n{p.text}" for p in passages)


def chat_model(settings: Settings):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=settings.chat_model, temperature=0, timeout=20, max_retries=1,
                      api_key=settings.openai_api_key)


class MockGrounded:
    """Quotes the first sentence of the top passage. Good enough to exercise
    the pipeline; says nothing about answer quality."""

    def invoke(self, messages, passages=()):
        if not passages:
            return {"answerable": False, "answer": "", "citations": []}
        top = passages[0]
        sentence = re.split(r"(?<=[.!?])\s+", " ".join(top.text.split()))[0][:200]
        return {"answerable": True, "answer": f"(mock) {sentence}",
                "citations": [{"chunk_id": top.chunk_id, "quote": sentence}]}


class MockBaseline:
    def invoke(self, messages, passages=()):
        return "(mock) " + (" ".join(passages[0].text.split())[:200] if passages else "I'm not sure.")
