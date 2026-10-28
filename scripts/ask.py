"""Ask one question from the command line.

Usage: python scripts/ask.py "How long is the cooler warranty?" [--mode grounded|baseline]
"""
import argparse
import json

import _path  # noqa: F401
from app.answer import GroundedAssistant
from app.baseline import BaselineAssistant
from app.config import load_settings
from app.store import open_store


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("question")
    ap.add_argument("--mode", choices=["grounded", "baseline"], default="grounded")
    args = ap.parse_args()
    settings = load_settings()
    store = open_store(settings)
    bot = GroundedAssistant if args.mode == "grounded" else BaselineAssistant
    print(json.dumps(bot(settings, store).ask(args.question).to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
