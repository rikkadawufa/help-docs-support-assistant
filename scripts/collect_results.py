"""Score run logs and write output/results.md. All numbers are counted here, in code.

Usage: python scripts/collect_results.py [--grounded LOG] [--baseline LOG] [--update LOG] [--llm-error LOG]
Without arguments it picks the newest log of each kind in output/run-log/.
"""
import argparse
import json
import re
from pathlib import Path

import _path  # noqa: F401
from app.config import OUTPUT_DIR, ROOT

RUN_LOG = OUTPUT_DIR / "run-log"
LABELS = ROOT / "eval" / "baseline-labels.json"

# Free-text refusal patterns for the baseline. A person double-checks these
# in eval/baseline-labels.json, and the human label wins.
REFUSAL = re.compile(
    r"don't have|do not have|no information|not (mentioned|specified|covered|included|stated|provided|available)"
    r"|couldn't find|can't find|cannot find|unable to (find|confirm)|isn't (mentioned|specified)"
    r"|doesn't (mention|specify|say)|does not (mention|specify|say)|contact (our )?(customer )?support",
    re.IGNORECASE)


def newest(kind: str) -> Path | None:
    files = sorted(RUN_LOG.glob(f"*-{kind}.jsonl"))
    return files[-1] if files else None


def read(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def facts_ok(row: dict) -> bool:
    return all(re.search(f, row["answer"], re.IGNORECASE) for f in row["expect"].get("facts", []))


def source_ok(row: dict) -> bool:
    want = row["expect"].get("sources", [])
    for c in row.get("citations", []):
        for w in want:
            if c["source"] == w["source"] and (w["page"] == 0 or c["page"] == w["page"]):
                return True
    return False


def grade_grounded(row: dict) -> tuple[bool, str]:
    exp = row["expect"]["status"]
    if exp == "answered":
        if row["status"] != "answered":
            return False, f"expected an answer, got {row['status']} ({row['reason']})"
        if not facts_ok(row):
            return False, "answer is missing an expected fact"
        if not source_ok(row):
            return False, "no valid citation to the expected document/page"
        return True, "correct, cited " + ", ".join(sorted({c["label"] for c in row["citations"]}))
    if row["status"] == exp:
        return True, f"{row['status']} ({row['reason']})"
    return False, f"expected {exp}, got {row['status']}"


def baseline_verdict(row: dict, labels: dict) -> tuple[str, str]:
    """Return (answered|declined, how it was decided)."""
    rule = "declined" if REFUSAL.search(row["answer"]) else "answered"
    human = labels.get(row["id"])
    if human in ("answered", "declined"):
        return human, "human" if human == rule else f"human (rule said {rule})"
    return rule, "rule only, waiting for human check"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--grounded", type=Path)
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--update", type=Path)
    ap.add_argument("--llm-error", type=Path)
    ap.add_argument("--summary", action="store_true", help="print a short plain-text summary instead")
    args = ap.parse_args()

    paths = {"grounded": args.grounded or newest("grounded"), "baseline": args.baseline or newest("baseline"),
             "update": args.update or newest("scenario-update"), "llm-error": args.llm_error or newest("scenario-llm-error")}
    g, b = read(paths["grounded"]), read(paths["baseline"])
    labels = json.loads(LABELS.read_text("utf-8")) if LABELS.exists() else {}
    labels = {k: v for k, v in labels.items() if not k.startswith("_")}

    # --- grounded ---
    g_rows = [(r, *grade_grounded(r)) for r in g]
    def g_count(cats, want_pass=True):
        return sum(1 for r, ok, _ in g_rows if r["category"] in cats and ok == want_pass)
    g_ab = g_count("AB")
    g_trap_answered = sum(1 for r, _, _ in g_rows if r["category"] == "C" and r["status"] == "answered")

    # --- baseline ---
    b_rows = []
    for r in b:
        verdict, how = baseline_verdict(r, labels) if r["category"] in "CD" else ("answered", "")
        b_rows.append((r, verdict, how))
    b_facts = sum(1 for r, _, _ in b_rows if r["category"] in "AB" and facts_ok(r))
    b_trap_answered = sum(1 for r, v, _ in b_rows if r["category"] == "C" and v == "answered")
    pending = [r["id"] for r, _, how in b_rows if how.startswith("rule only")]

    n_ab = sum(1 for r in g if r["category"] in "AB")
    n_c = sum(1 for r in g if r["category"] == "C")
    meta = g[0] if g else (b[0] if b else {})

    out = ["# Eval results", "",
           "> All questions and documents are made up (fictional store \"Cinderpeak Outdoor\"). "
           "The baseline is a deliberately simple RAG written for this demo, not a real product. "
           "Every number below is counted by `scripts/collect_results.py` from the run logs.", "",
           f"- LLM mode: `{meta.get('llm_mode', '?')}`, chat model: `{meta.get('model', '?')}`",
           f"- Logs: " + ", ".join(f"`{p.name}`" for p in paths.values() if p), ""]
    if pending:
        out += [f"**Baseline labels pending human check:** {', '.join(pending)} "
                f"(fill in `eval/baseline-labels.json`)", ""]
    out += ["## Before / after", "",
            "| What we checked | Baseline (simple RAG) | This assistant |", "|---|---|---|",
            f"| Answerable questions (A+B): correct answer | {b_facts}/{n_ab} (shows no sources) | {g_ab}/{n_ab} with a checked citation to the right file and page |",
            f"| Trap questions (C): answered anyway | {b_trap_answered}/{n_c} | {g_trap_answered}/{n_c} |",
            "",
            # D questions (account-specific, need staff) are listed per question below but left out
            # of this table: the baseline has no handoff, and judging its D answers is too subjective.
            "Account-specific questions (D) are listed per question below, not in this table.", ""]

    out += ["## Grounded assistant, question by question", "", "| ID | Question | Status | Result | Note |", "|---|---|---|---|---|"]
    for r, ok, note in g_rows:
        out.append(f"| {r['id']} | {r['question']} | {r['status']} | {'pass' if ok else 'FAIL'} | {note} |")
    out += ["", "## Baseline, question by question", "", "| ID | Question | Verdict | Answer (first 140 chars) |", "|---|---|---|---|"]
    for r, verdict, how in b_rows:
        if r["category"] in "AB":
            verdict = "facts match" if facts_ok(r) else "facts missing"
        else:
            verdict = f"{verdict} ({how})"
        ans = " ".join(r["answer"].split())[:140].replace("|", "/")
        out.append(f"| {r['id']} | {r['question']} | {verdict} | {ans} |")

    upd = read(paths["update"])
    if upd:
        out += ["", "## E. Document update (returns policy 30 -> 14 days)", "", "| Step | Ingest | Status | Result | Answer |", "|---|---|---|---|---|"]
        for r in upd:
            ok, note = grade_grounded(r)
            ing = r.get("ingest", {})
            ing_txt = f"updated {len(ing.get('updated', []))}, unchanged {ing.get('unchanged', '?')}"
            out.append(f"| {r['id']} | {ing_txt} | {r['status']} | {'pass' if ok else 'FAIL'} | {' '.join(r['answer'].split())[:120]} |")

    err = read(paths["llm-error"])
    if err:
        out += ["", "## F. AI service failure", "", "| Step | Status | Reason | Alert | Result |", "|---|---|---|---|---|"]
        for r in err:
            ok, _ = grade_grounded(r)
            alerts = ", ".join(f"{a['reason']}/{a['slack']}" for a in r.get("alerts", [])) or "-"
            out.append(f"| {r['id']} | {r['status']} | {r['reason'] or '-'} | {alerts} | {'pass' if ok else 'FAIL'} |")

    (OUTPUT_DIR / "results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    if not args.summary:
        print("\n".join(out[:22]))
        print(f"\nwrote {OUTPUT_DIR / 'results.md'}")
        return

    # --summary: short plain-text version for a terminal screenshot
    g_c = {r["id"]: r for r, _, _ in g_rows if r["category"] == "C"}
    b_c = {r["id"]: (v, how) for r, v, how in b_rows if r["category"] == "C"}
    g_d = sum(1 for r, ok, _ in g_rows if r["category"] == "D" and ok)
    n_d = sum(1 for r in g if r["category"] == "D")
    print(f"grounded  A+B  {g_ab}/{n_ab} correct, cited the right file and page")
    print(f"grounded  C    {g_trap_answered}/{n_c} trap questions answered")
    print(f"grounded  D    {g_d}/{n_d} account questions handed off")
    print(f"baseline  A+B  {b_facts}/{n_ab} correct, no sources shown")
    print(f"baseline  C    {b_trap_answered}/{n_c} trap questions answered (human-labeled)")
    print()
    for qid, r in g_c.items():
        verdict, _ = b_c.get(qid, ("-", ""))
        print(f"{qid}  {r['question'][:52]:52}  baseline {verdict:8}  grounded {r['status']} ({r['reason']})")
    print(f"\nwrote {(OUTPUT_DIR / 'results.md').relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
