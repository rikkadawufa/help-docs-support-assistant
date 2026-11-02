"""Grounded answer chain: relevance gate -> structured answer -> citation check
-> answer or hand off to a person."""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field

import httpx
import openai
from langchain_core.messages import HumanMessage, SystemMessage

from . import handoff
from .citations import decide
from .config import DEFAULT_DEGRADED_REPLY, DEFAULT_HANDOFF_REPLY, Settings, mask
from .llm import GROUNDED_SCHEMA, MockGrounded, chat_model, format_passages, prompt
from .store import Retrieved, retrieve

HANDOFF_REPLY = DEFAULT_HANDOFF_REPLY   # the demo's reply; Settings.handoff_reply is the one used
DEGRADED_REPLY = DEFAULT_DEGRADED_REPLY  # the demo's reply; Settings.degraded_reply is the one used

LLM_ERRORS = (openai.OpenAIError, httpx.HTTPError, TimeoutError)


@dataclass
class Reply:
    request_id: str
    mode: str
    status: str                     # answered | handoff | degraded | baseline
    answer: str
    reason: str = ""
    citations: list[dict] = field(default_factory=list)
    rejected_citations: list[dict] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    top_score: float = 0.0
    model: str = ""
    ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _retrieved_dicts(passages: list[Retrieved]) -> list[dict]:
    return [{"chunk_id": p.chunk_id, "label": p.label(), "score": p.score} for p in passages]


class GroundedAssistant:
    def __init__(self, settings: Settings, store):
        self.settings = settings
        self.store = store
        self._llm = None

    def _structured(self):
        if self.settings.llm_mode != "live":
            return MockGrounded()
        if self._llm is None:
            self._llm = chat_model(self.settings).with_structured_output(GROUNDED_SCHEMA, method="json_schema")
        return self._llm

    def ask(self, question: str) -> Reply:
        t0 = time.perf_counter()
        rid = uuid.uuid4().hex[:10]
        passages = retrieve(self.store, question, self.settings.top_k)
        top = passages[0].score if passages else 0.0
        reply = Reply(rid, "grounded", "", "", retrieved=_retrieved_dicts(passages),
                      top_score=top, model=self.settings.chat_model)

        if top < self.settings.relevance_min:
            return self._handoff(reply, question, passages, "low_relevance", t0)

        messages = [
            SystemMessage(prompt("grounded", self.settings.brand_name)),
            HumanMessage(f"Passages:\n\n{format_passages(passages)}\n\nCustomer question: {question}"),
        ]
        try:
            llm = self._structured()
            parsed = llm.invoke(messages, passages=passages) if isinstance(llm, MockGrounded) else llm.invoke(messages)
        except LLM_ERRORS as exc:
            reply.status, reply.answer, reply.reason = "degraded", self.settings.degraded_reply, "llm_error"
            reply.rejected_citations = [{"error": mask(f"{type(exc).__name__}: {exc}")[:300]}]
            handoff.notify(self.settings, question, "llm_error", passages, rid)
            reply.ms = int((time.perf_counter() - t0) * 1000)
            return reply

        by_id = {p.chunk_id: p for p in passages}
        decision = decide(parsed, {cid: p.text for cid, p in by_id.items()})
        reply.rejected_citations = [{"chunk_id": c.chunk_id, "quote": c.quote, "problem": c.problem}
                                    for c in decision.invalid]
        if decision.status == "handoff":
            return self._handoff(reply, question, passages, decision.reason, t0)

        reply.status, reply.answer = "answered", parsed["answer"].strip()
        reply.citations = [{"chunk_id": c.chunk_id, "quote": c.quote, "source": by_id[c.chunk_id].source,
                            "page": by_id[c.chunk_id].page, "label": by_id[c.chunk_id].label()}
                           for c in decision.valid]
        reply.ms = int((time.perf_counter() - t0) * 1000)
        return reply

    def _handoff(self, reply: Reply, question: str, passages, reason: str, t0: float) -> Reply:
        reply.status, reply.answer, reply.reason = "handoff", self.settings.handoff_reply, reason
        handoff.notify(self.settings, question, reason, passages, reply.request_id)
        reply.ms = int((time.perf_counter() - t0) * 1000)
        return reply
