"""Load the help documents, split them into chunks and keep the Chroma index
in sync with the knowledge/ folder. Only new or changed files are re-embedded."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from .config import KNOWLEDGE_DIR, Settings
from .store import open_store

CHUNK_SIZE = 500
CHUNK_OVERLAP = 80

# Every PDF page carries the same banner and a "<title> | page N of M" footer.
BANNER = re.compile(r"^Cinderpeak Outdoor \| Help Center \| Fictional demo content\s*$", re.MULTILINE)
FOOTER = re.compile(r"^(?P<title>.+?) \| page \d+ of \d+\s*$", re.MULTILINE)
SUPPORTED = {".pdf", ".md"}

_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
_md_headers = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "title"), ("##", "section")], strip_headers=False)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "intro"


def page_text(page: pymupdf.Page) -> str:
    """Page text in reading order, with each table row kept on one line as
    "cell | cell | cell" instead of one cell per line."""
    tables = page.find_tables().tables
    boxes = [pymupdf.Rect(t.bbox) for t in tables]
    items = [(b[1], b[4]) for b in page.get_text("blocks")
             if b[6] == 0 and not any(pymupdf.Rect(b[:4]).intersects(r) for r in boxes)]
    for t, box in zip(tables, boxes):
        rows = [" | ".join(" ".join(page.get_textbox(pymupdf.Rect(c)).split()) for c in row.cells if c)
                for row in t.rows]
        items.append((box.y0, "\n".join(rows) + "\n"))
    return "".join(text for _, text in sorted(items, key=lambda x: x[0]))


def load_chunks(path: Path, source: str) -> list[Document]:
    """Split one file into chunks with deterministic ids in metadata['chunk_id']."""
    chunks: list[Document] = []
    if path.suffix == ".pdf":
        with pymupdf.open(path) as pdf:
            pages = [page_text(p) for p in pdf]
        for page, raw in enumerate(pages, start=1):
            # NFKC turns PDF ligatures (U+FB00 -> ff) back into plain letters
            content = unicodedata.normalize("NFKC", raw)
            title = m.group("title") if (m := FOOTER.search(content)) else path.stem
            # Drop the boilerplate (it only adds noise to the embedding) and put
            # the document title at the top of each chunk instead.
            content = FOOTER.sub("", BANNER.sub("", content)).strip()
            for i, text in enumerate(_splitter.split_text(content)):
                if not text.startswith(title):
                    text = f"{title}\n{text}"
                chunks.append(Document(text, metadata={
                    "source": source, "page": page, "section": "",
                    "chunk_id": f"{source}#p{page}#c{i}",
                }))
    else:
        for sec in _md_headers.split_text(path.read_text(encoding="utf-8")):
            section = sec.metadata.get("section") or sec.metadata.get("title", "")
            for i, text in enumerate(_splitter.split_text(sec.page_content)):
                chunks.append(Document(text, metadata={
                    "source": source, "page": 0, "section": section,
                    "chunk_id": f"{source}#s-{slug(section)}#c{i}",
                }))
    return chunks


@dataclass
class SyncReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    chunks_written: int = 0

    def summary(self) -> str:
        return (f"added {len(self.added)}, updated {len(self.updated)}, removed {len(self.removed)}, "
                f"unchanged {len(self.unchanged)} ({self.chunks_written} chunks embedded)")


def scan(folder: Path) -> dict[str, Path]:
    return {p.name: p for p in sorted(folder.iterdir()) if p.is_file() and p.suffix in SUPPORTED}


def plan_sync(on_disk: dict[str, str], manifest: dict[str, str]) -> SyncReport:
    """Compare file hashes with the last manifest. Pure, so it is unit tested."""
    report = SyncReport()
    for name, digest in on_disk.items():
        if name not in manifest:
            report.added.append(name)
        elif manifest[name] != digest:
            report.updated.append(name)
        else:
            report.unchanged.append(name)
    report.removed = [n for n in manifest if n not in on_disk]
    return report


def sync(settings: Settings, folder: Path = KNOWLEDGE_DIR, rebuild: bool = False) -> SyncReport:
    store = open_store(settings, reset=rebuild)
    manifest_path = settings.manifest_path
    manifest = {} if rebuild or not manifest_path.exists() else json.loads(manifest_path.read_text("utf-8"))

    files = scan(folder)
    hashes = {name: sha256(p) for name, p in files.items()}
    report = plan_sync(hashes, manifest)

    for name in report.updated + report.removed:
        old = store.get(where={"source": name})["ids"]
        if old:
            store.delete(ids=old)
    for name in report.added + report.updated:
        chunks = load_chunks(files[name], name)
        store.add_documents(chunks, ids=[c.metadata["chunk_id"] for c in chunks])
        report.chunks_written += len(chunks)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    return report
