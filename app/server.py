"""FastAPI app: /ask, /handoff, /source, /health and the chat widget pages.

Run: uvicorn app.server:create_app --factory --port 8010
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import handoff
from .answer import GroundedAssistant
from .baseline import BaselineAssistant
from .config import Settings, load_settings
from .store import open_store, retrieve

STATIC = Path(__file__).resolve().parent / "static"


class AskIn(BaseModel):
    question: str = Field(..., max_length=1000)
    mode: str = Field("grounded", pattern="^(grounded|baseline)$")

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question is empty")
        return v.strip()


class HandoffIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    note: str = Field("", max_length=1000)


def create_app(settings: Settings | None = None, store=None) -> FastAPI:
    settings = settings or load_settings()
    store = store if store is not None else open_store(settings)
    grounded = GroundedAssistant(settings, store)
    baseline = BaselineAssistant(settings, store)

    app = FastAPI(title=f"{settings.brand_name} support assistant (demo)")
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/compare")
    def compare():
        return FileResponse(STATIC / "compare.html")

    @app.get("/health")
    def health():
        return {"ok": True, "llm_mode": settings.llm_mode, "chunks": len(store.get()["ids"]),
                "chat_model": settings.chat_model, "relevance_min": settings.relevance_min}

    @app.post("/ask")
    def ask(body: AskIn):
        bot = grounded if body.mode == "grounded" else baseline
        return bot.ask(body.question).to_dict()

    @app.post("/handoff")
    def human(body: HandoffIn):
        rid = uuid.uuid4().hex[:10]
        passages = retrieve(store, body.question, settings.top_k)
        entry = handoff.notify(settings, body.question, "user_requested", passages, rid, body.note)
        return {"request_id": rid, "status": "sent", "slack": entry["slack"],
                "message": "Thanks. A person from our support team will reply by email within 1 business day."}

    @app.get("/source/{chunk_id:path}")
    def source(chunk_id: str):
        got = store.get(ids=[chunk_id])
        if not got["ids"]:
            raise HTTPException(404, "unknown chunk")
        meta = got["metadatas"][0]
        return {"chunk_id": chunk_id, "source": meta["source"], "page": meta.get("page") or None,
                "section": meta.get("section", ""), "text": got["documents"][0]}

    return app
