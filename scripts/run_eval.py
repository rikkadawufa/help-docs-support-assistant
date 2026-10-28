"""Run the eval questions and write one JSON line per answer to output/run-log/.

Usage:
  python scripts/run_eval.py --mode both                 # A-D questions, baseline and grounded
  python scripts/run_eval.py --mode grounded --only A1,C3
  python scripts/run_eval.py --calibrate                  # print relevance scores for eval/calibration.json
  python scripts/run_eval.py --scenario update            # E: returns policy v1 -> v2 -> back to v1
  python scripts/run_eval.py --scenario llm-error         # F: broken model name, then a normal question

Scoring is done afterwards by collect_results.py, never here.
"""
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

import _path  # noqa: F401
from app import handoff
from app.answer import GroundedAssistant
from app.baseline import BaselineAssistant
from app.config import OUTPUT_DIR, ROOT, load_settings
from app.ingest import sync
from app.store import open_store, retrieve

RUN_LOG = OUTPUT_DIR / "run-log"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")


def load(name: str) -> list[dict]:
    return json.loads((ROOT / "eval" / name).read_text("utf-8"))["questions"]


def write(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_questions(settings, store, mode: str, only: set[str]) -> Path:
    bot = (GroundedAssistant if mode == "grounded" else BaselineAssistant)(settings, store)
    out = RUN_LOG / f"{STAMP}-{mode}.jsonl"
    for q in load("questions.json"):
        if only and q["id"] not in only:
            continue
        reply = bot.ask(q["question"]).to_dict()
        write(out, {"id": q["id"], "category": q["category"], "question": q["question"],
                    "expect": q["expect"], "llm_mode": settings.llm_mode, **reply})
        print(f"{mode:8} {q['id']:3} {reply['status']:9} {reply['reason'] or '':18} {reply['answer'][:70]!r}")
    return out


def calibrate(settings, store) -> None:
    rows = []
    for q in load("calibration.json"):
        top = retrieve(store, q["question"], settings.top_k)[0]
        rows.append((q["id"], q["answerable"], top.score, top.label(), q["question"]))
        print(f"{q['id']} answerable={str(q['answerable']):5} top={top.score:.3f} {top.label():40} {q['question']}")
    lo = min(r[2] for r in rows if r[1])
    hi = max(r[2] for r in rows if not r[1])
    print(f"\nlowest answerable score {lo:.3f}, highest unanswerable score {hi:.3f}")
    # The gate only screens out clearly off-topic questions. Near-topic questions
    # with no answer are left to the model's answerable flag and the citation check.
    floor = round(lo - 0.05, 2)
    blocked = [r[0] for r in rows if not r[1] and r[2] < floor]
    print(f"rule: RELEVANCE_MIN = lowest answerable score - 0.05 = {floor:.2f}")
    print(f"with that floor the gate alone blocks {len(blocked)}/{sum(1 for r in rows if not r[1])} unanswerable: {blocked}")
    if hi >= lo:
        print("scores overlap, as expected for near-topic questions")


def swap(version: str) -> None:
    shutil.copyfile(ROOT / "knowledge_updates" / f"returns-policy-{version}.pdf", ROOT / "knowledge" / "returns-policy.pdf")


def scenario_update(settings) -> Path:
    out = RUN_LOG / f"{STAMP}-scenario-update.jsonl"
    question = "How many days do I have to return something?"
    swap("v1")
    sync(settings)
    steps = [("E1-before", "v1", {"status": "answered", "facts": ["\\b30\\b"], "sources": [{"source": "returns-policy.pdf", "page": 1}]}),
             ("E1-after", "v2", {"status": "answered", "facts": ["\\b14\\b"], "sources": [{"source": "returns-policy.pdf", "page": 1}]})]
    try:
        for qid, version, expect in steps:
            swap(version)
            report = sync(settings)
            print(f"{qid}: policy {version}, ingest -> {report.summary()}")
            reply = GroundedAssistant(settings, open_store(settings)).ask(question).to_dict()
            write(out, {"id": qid, "category": "E", "question": question, "expect": expect,
                        "llm_mode": settings.llm_mode, "ingest": {"added": report.added, "updated": report.updated,
                        "removed": report.removed, "unchanged": len(report.unchanged)}, **reply})
            print(f"   {reply['status']}: {reply['answer'][:90]!r}")
    finally:
        swap("v1")
        print("restored v1 ->", sync(settings).summary())
    return out


def scenario_llm_error(settings, store) -> Path:
    out = RUN_LOG / f"{STAMP}-scenario-llm-error.jsonl"
    before = handoff.LOG_PATH.read_text("utf-8").count("\n") if handoff.LOG_PATH.exists() else 0
    broken = settings.with_overrides(chat_model="gpt-does-not-exist")
    q1 = "How many days do I have to return something?"
    r1 = GroundedAssistant(broken, store).ask(q1).to_dict()
    new_lines = handoff.LOG_PATH.read_text("utf-8").splitlines()[before:] if handoff.LOG_PATH.exists() else []
    alerts = [json.loads(line) for line in new_lines]
    write(out, {"id": "F1", "category": "F", "question": q1, "expect": {"status": "degraded"},
                "llm_mode": settings.llm_mode, "alerts": alerts, **r1})
    print(f"F1 (model=gpt-does-not-exist): {r1['status']} {r1['reason']} alerts={[a['reason'] + '/' + a['slack'] for a in alerts]}")
    q2 = "What's the warranty on the Glacier 45 cooler?"
    r2 = GroundedAssistant(settings, store).ask(q2).to_dict()
    write(out, {"id": "F1-next", "category": "F", "question": q2,
                "expect": {"status": "answered", "facts": ["\\b(5|five)[- ]years?\\b"], "sources": [{"source": "warranty.pdf", "page": 2}]},
                "llm_mode": settings.llm_mode, **r2})
    print(f"F1-next (normal model): {r2['status']} {r2['answer'][:80]!r}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["grounded", "baseline", "both"])
    ap.add_argument("--only", default="", help="comma-separated question ids")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--scenario", choices=["update", "llm-error"])
    args = ap.parse_args()

    settings = load_settings()
    print(f"llm_mode={settings.llm_mode} chat_model={settings.chat_model} relevance_min={settings.relevance_min}")
    store = open_store(settings)
    if args.calibrate:
        calibrate(settings, store)
    elif args.scenario == "update":
        print("log:", scenario_update(settings).relative_to(ROOT).as_posix())
    elif args.scenario == "llm-error":
        print("log:", scenario_llm_error(settings, store).relative_to(ROOT).as_posix())
    elif args.mode:
        only = {s.strip() for s in args.only.split(",") if s.strip()}
        for mode in (["baseline", "grounded"] if args.mode == "both" else [args.mode]):
            print("log:", run_questions(settings, store, mode, only).relative_to(ROOT).as_posix())
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
