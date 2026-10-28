"""Start the API and chat widget on http://127.0.0.1:8010

Usage: python scripts/serve.py [--live] [--slack] [--port 8010]
Without flags it uses LLM_MODE / SLACK_MODE from .env (mock / log by default).
"""
import argparse
import os

import _path  # noqa: F401


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="use the real OpenAI API")
    ap.add_argument("--slack", action="store_true", help="post handoffs to Slack")
    ap.add_argument("--port", type=int, default=8010)
    args = ap.parse_args()
    if args.live:
        os.environ["LLM_MODE"] = "live"
    if args.slack:
        os.environ["SLACK_MODE"] = "slack"

    import uvicorn
    uvicorn.run("app.server:create_app", factory=True, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
