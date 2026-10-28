"""Switch knowledge/returns-policy.pdf between v1 (30 days) and v2 (14 days).

Both versions are kept in knowledge_updates/ by make_docs.py. After a swap,
run scripts/ingest.py: it should report exactly one updated file.

Usage: python scripts/swap_returns_policy.py v1|v2
"""
import argparse
import shutil

import _path  # noqa: F401
from app.config import KNOWLEDGE_DIR, ROOT


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("version", choices=["v1", "v2"])
    args = ap.parse_args()
    target = KNOWLEDGE_DIR / "returns-policy.pdf"
    shutil.copyfile(ROOT / "knowledge_updates" / f"returns-policy-{args.version}.pdf", target)
    print(f"knowledge/returns-policy.pdf is now {args.version}")


if __name__ == "__main__":
    main()
