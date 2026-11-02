"""Run a question bank against one or more RAG HTTP APIs with promptfoo, then write the report.

Usage:
  python audit/run.py --bank eval/questions.json --target audit/targets/cinderpeak-grounded.json
  python audit/run.py --bank eval/questions.json \
      --target audit/targets/cinderpeak-baseline.json --target audit/targets/cinderpeak-grounded.json --repeat 3

Each run gets its own folder under output/audit/: the generated promptfoo config,
promptfoo's raw results.json, and the report (dataset.json, report.md, per-question.csv).
Grading is audit/grade.py (code only, no LLM). The report is audit/report.py.
--freeze copies a record from scripts/freeze.py into the run folder as freeze.json, so the report
can state when and at which version the test assistants were fixed. The setup is recorded again
first, from the same .env the server reads; if any code, setting, prompt or document differs from the
freeze, the run stops before a question is asked.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parent
PROMPTFOO = "promptfoo@0.124.1"

sys.path.insert(0, str(AUDIT))
import report  # noqa: E402

sys.path.insert(0, str(ROOT))
from app.config import docs_path, load_settings  # noqa: E402
from app.freeze import drift, record, verify  # noqa: E402


def rel(path: Path, start: Path) -> str:
    return os.path.relpath(path, start).replace("\\", "/")


def load_bank(path: Path, only: set[str]) -> list[dict]:
    data = json.loads(path.read_text("utf-8"))
    questions = data["questions"] if isinstance(data, dict) else data
    return [q for q in questions if not only or q["id"] in only]


def build_config(bank: list[dict], targets: list[Path], out: Path, url: str = "") -> dict:
    providers = []
    for t in targets:
        spec = json.loads(t.read_text("utf-8"))
        providers.append({
            "id": "https",
            "label": spec["label"],
            "config": {
                "url": url or spec["url"],
                "method": spec.get("method", "POST"),
                "headers": spec.get("headers", {"Content-Type": "application/json"}),
                "body": spec["body"],
                "transformResponse": "file://" + rel(t.parent.parent / spec["transform"], out),
            },
        })
    return {
        "description": "RAG audit",
        "prompts": ["{{question}}"],
        "providers": providers,
        "defaultTest": {"assert": [{"type": "python", "value": "file://" + rel(AUDIT / "grade.py", out)}]},
        "tests": [{"description": q["id"],
                   "vars": {"id": q["id"], "category": q.get("category", ""), "question": q["question"],
                            "expect": q["expect"]}}
                  for q in bank],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", type=Path, required=True)
    ap.add_argument("--target", type=Path, action="append", required=True)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--only", default="", help="comma-separated question ids")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--url", default="", help="override every target's url (e.g. another port)")
    ap.add_argument("--freeze", type=Path, help="record from scripts/freeze.py, copied into the run folder")
    args = ap.parse_args()
    if args.freeze:
        rec = json.loads(args.freeze.read_text("utf-8"))
        if not verify(rec):
            sys.exit(f"{args.freeze} does not match its own fingerprint; make a new one with scripts/freeze.py")
        settings = load_settings()
        if rec.get("documents_dir"):
            settings = settings.with_overrides(knowledge_dir=docs_path(rec["documents_dir"]))
        try:
            changes = drift(rec, record(settings))
        except ValueError as e:
            sys.exit(f"Not run: {e}")
        if changes:
            sys.exit("Not run: the test setup changed after it was frozen.\n  - " + "\n  - ".join(changes)
                     + "\nPut it back, or freeze again and post the new fingerprint before running.")

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    bank = load_bank(args.bank.resolve(), only)
    out = ROOT / "output" / "audit" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    if args.freeze:
        shutil.copyfile(args.freeze, out / "freeze.json")
    config = build_config(bank, [t.resolve() for t in args.target], out, args.url)
    # JSON is valid YAML, so promptfoo reads this file as its config.
    (out / "promptfooconfig.yaml").write_text(json.dumps(config, indent=2, ensure_ascii=False), "utf-8")

    env = {**os.environ, "PROMPTFOO_DISABLE_TELEMETRY": "1", "PROMPTFOO_DISABLE_UPDATE": "1",
           "PROMPTFOO_PYTHON": sys.executable}
    cmd = ["npx", "-y", PROMPTFOO, "eval", "-c", "promptfooconfig.yaml", "-o", "results.json",
           "--repeat", str(args.repeat), "--no-cache", "--max-concurrency", str(args.concurrency)]
    print("running:", " ".join(cmd), f"(in {rel(out, ROOT)})")
    # promptfoo exits non-zero when any assertion fails; that is a normal audit outcome.
    subprocess.run(cmd, cwd=out, env=env, shell=os.name == "nt")
    results = out / "results.json"
    if not results.exists():
        sys.exit("promptfoo did not write results.json; see its output above")
    report.write(results, bank, out, bank_path=args.bank)
    print("report:", rel(out / "report.md", ROOT))


if __name__ == "__main__":
    main()
