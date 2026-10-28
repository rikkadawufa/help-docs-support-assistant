"""Sync the vector index with knowledge/. Only new or changed files are embedded.

Usage: python scripts/ingest.py [--rebuild]
"""
import argparse

import _path  # noqa: F401
from app.config import load_settings
from app.ingest import sync


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rebuild", action="store_true", help="delete the index and embed everything again")
    args = ap.parse_args()
    settings = load_settings()
    report = sync(settings, rebuild=args.rebuild)
    print(f"[{settings.llm_mode}] {report.summary()}")
    for label, names in (("added", report.added), ("updated", report.updated), ("removed", report.removed)):
        for n in names:
            print(f"  {label}: {n}")


if __name__ == "__main__":
    main()
