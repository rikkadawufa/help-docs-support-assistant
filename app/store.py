"""Chroma vector store and embeddings, picked by LLM_MODE."""
from __future__ import annotations

import shutil
from dataclasses import dataclass

from langchain_chroma import Chroma
from langchain_core.embeddings import DeterministicFakeEmbedding, Embeddings

from .config import Settings

COLLECTION = "cinderpeak_help"


def make_embeddings(settings: Settings) -> Embeddings:
    if settings.llm_mode == "live":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=settings.embed_model, api_key=settings.openai_api_key)
    return DeterministicFakeEmbedding(size=256)


def open_store(settings: Settings, reset: bool = False) -> Chroma:
    if reset and settings.chroma_dir.exists():
        shutil.rmtree(settings.chroma_dir)
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=make_embeddings(settings),
        persist_directory=str(settings.chroma_dir),
        collection_metadata={"hnsw:space": "cosine"},  # relevance score = 1 - cosine distance
    )


@dataclass
class Retrieved:
    chunk_id: str
    source: str
    page: int
    section: str
    text: str
    score: float

    def label(self) -> str:
        return f"{self.source} p.{self.page}" if self.page else f"{self.source} > {self.section}"


def retrieve(store: Chroma, question: str, k: int) -> list[Retrieved]:
    hits = store.similarity_search_with_relevance_scores(question, k=k)
    return [
        Retrieved(
            chunk_id=doc.metadata["chunk_id"], source=doc.metadata["source"],
            page=int(doc.metadata.get("page") or 0), section=doc.metadata.get("section", ""),
            text=doc.page_content, score=round(float(score), 4),
        )
        for doc, score in hits
    ]
