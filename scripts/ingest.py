"""Sync the vector index with the documents folder. Only new or changed files are embedded.

Usage:
  python scripts/ingest.py [--rebuild]
  python scripts/ingest.py --docs <folder> --index <name> [--rebuild]

Without --docs and --index it uses KNOWLEDGE_DIR and INDEX_NAME from .env (default: knowledge/ and
the demo's own index). Give every other document set its own --index, or its sync removes the demo's
documents from the demo index.
"""
import argparse
from pathlib import Path

import _path  # noqa: F401
from app.config import docs_path, index_name, load_settings
from app.ingest import sync


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rebuild", action="store_true", help="delete the index and embed everything again")
    ap.add_argument("--docs", type=Path, help="documents folder (overrides KNOWLEDGE_DIR)")
    ap.add_argument("--index", help="index name (overrides INDEX_NAME)")
    args = ap.parse_args()
    settings = load_settings()
    if args.docs:
        settings = settings.with_overrides(knowledge_dir=docs_path(str(args.docs.resolve())))
    if args.index is not None:
        settings = settings.with_overrides(index_name=index_name(args.index))
    if not settings.knowledge_dir.is_dir():
        raise SystemExit(f"no documents folder {settings.knowledge_dir}")
    report = sync(settings, rebuild=args.rebuild)
    print(f"[{settings.llm_mode}] {settings.knowledge_dir} -> {settings.chroma_dir.name}: {report.summary()}")
    for label, names in (("added", report.added), ("updated", report.updated), ("removed", report.removed)):
        for n in names:
            print(f"  {label}: {n}")


if __name__ == "__main__":
    main()
