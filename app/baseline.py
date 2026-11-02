"""Naive RAG used as the "before" in the comparison.

Same index and same top_k as the grounded assistant, but a one-line prompt,
free-text output, no relevance gate, no citation check and no handoff. This is
a simplified version written for this demo, not anyone's real product."""
from __future__ import annotations

import time
import uuid

from langchain_core.messages import HumanMessage, SystemMessage

from .answer import Reply, _retrieved_dicts
from .config import Settings
from .llm import MockBaseline, chat_model, prompt
from .store import retrieve


class BaselineAssistant:
    def __init__(self, settings: Settings, store):
        self.settings = settings
        self.store = store
        self._llm = None

    def ask(self, question: str) -> Reply:
        t0 = time.perf_counter()
        passages = retrieve(self.store, question, self.settings.top_k)
        context = "\n\n".join(p.text for p in passages)
        messages = [SystemMessage(prompt("baseline", self.settings.brand_name)),
                    HumanMessage(f"Context:\n{context}\n\nQuestion: {question}")]
        if self.settings.llm_mode != "live":
            text = MockBaseline().invoke(messages, passages=passages)
        else:
            if self._llm is None:
                self._llm = chat_model(self.settings)
            text = self._llm.invoke(messages).content
        return Reply(uuid.uuid4().hex[:10], "baseline", "baseline", str(text).strip(),
                     retrieved=_retrieved_dicts(passages),
                     top_score=passages[0].score if passages else 0.0,
                     model=self.settings.chat_model, ms=int((time.perf_counter() - t0) * 1000))
