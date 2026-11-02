"""Record how the two test assistants are set up, before any of the client's questions are run.

Usage:
  python scripts/freeze.py [--docs <folder>] [--index <name>] [--out <file>]

Writes output/freeze/<index>-<time>.json (or --out) and prints its fingerprint. Post the fingerprint
in the workroom before running the questions, then pass the file to audit/run.py with --freeze.
Reads the same .env as the server, so run it with the settings the server was started with.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import _path  # noqa: F401
from app.config import OUTPUT_DIR, docs_path, index_name, load_settings
from app.freeze import record


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs", type=Path, help="documents folder (overrides KNOWLEDGE_DIR)")
    ap.add_argument("--index", help="index name (overrides INDEX_NAME)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    settings = load_settings()
    if args.docs:
        settings = settings.with_overrides(knowledge_dir=docs_path(str(args.docs.resolve())))
    if args.index is not None:
        settings = settings.with_overrides(index_name=index_name(args.index))
    try:
        rec = record(settings)
    except ValueError as e:
        raise SystemExit(f"Not frozen: {e}")
    out = args.out or OUTPUT_DIR / "freeze" / f"{settings.index_name or 'demo'}-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1, ensure_ascii=False), "utf-8")
    print("wrote", out)
    print(f"fingerprint {rec['fingerprint'][:16]}  (commit {rec['commit'][:7] or '?'}"
          + (", with uncommitted changes in app/" if rec["uncommitted_app_changes"] else "") + ")")
    print("Post the fingerprint in the workroom before running the client's questions.")


if __name__ == "__main__":
    main()
