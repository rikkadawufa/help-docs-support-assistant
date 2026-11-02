"""Turn promptfoo's results.json into report.md and per-question.csv. Every number is counted here.

Reads only what audit/grade.py put in each result (pass, "fail:<type>" reason, named scores),
so the report never re-grades and never calls an LLM.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

FAILURE_TEXT = {
    "made_up_answer": "Answered a question the documents don't cover",
    "retrieval_miss": "Said it couldn't answer; the right passage was never retrieved",
    "over_refusal": "Said it couldn't answer although the documents cover it",
    "wrong_answer": "Wrong or incomplete answer",
    "wrong_answer_right_source": "Wrong or incomplete answer, though it cited the right page",
    "wrong_answer_wrong_source": "Wrong or incomplete answer, citing the wrong page",
    "wrong_answer_no_source": "Wrong or incomplete answer, with no source",
    "wrong_citation": "Right answer, but the citation points to the wrong file or page",
    "bad_response": "The API reply could not be read",
}


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({round(100 * n / d)}%)" if d else "n/a"


def _kind(reason: str) -> str:
    head = reason.split(" | ", 1)[0]
    return head.split(":", 1)[1] if head.startswith("fail:") else ""


def _output(row: dict) -> dict:
    try:
        return json.loads((row.get("response") or {}).get("output") or "{}")
    except ValueError:
        return {}


def collect(results_path: Path) -> dict[str, dict[str, list[dict]]]:
    """provider label -> question id -> one entry per run."""
    data = json.loads(results_path.read_text("utf-8"))
    by = defaultdict(lambda: defaultdict(list))
    for row in data["results"]["results"]:
        g = row.get("gradingResult") or {}
        reason = g.get("reason") or row.get("error") or "fail:bad_response | no grading result"
        out = _output(row)
        by[row["provider"].get("label") or row["provider"]["id"]][row["vars"]["id"]].append({
            "pass": bool(row.get("success")), "kind": _kind(reason), "reason": reason,
            "scores": g.get("namedScores") or row.get("namedScores") or {},
            "answer": out.get("answer", ""), "citations": out.get("citations") or [],
            "ms": row.get("latencyMs") or 0})
    return by


def summarize(runs_by_q: dict[str, list[dict]], bank: dict[str, dict]) -> dict:
    s = Counter()
    kinds = defaultdict(set)
    kind_runs = Counter()
    flaky = []
    for qid, runs in runs_by_q.items():
        expect = bank[qid]["expect"]
        for r in runs:
            sc = r["scores"]
            if expect["status"] == "answered":
                s["ans_runs"] += 1
                s["ans_pass"] += r["pass"]
                if "citation_correct" in sc:
                    s["cite_runs"] += 1
                    s["cite_ok"] += int(sc["citation_correct"])
            else:
                s["no_runs"] += 1
                s["made_up"] += int(sc.get("declined_correctly", 1) == 0)
            if "retrieval_hit" in sc:
                s["ret_runs"] += 1
                s["ret_hit"] += int(sc["retrieval_hit"])
            if r["kind"]:
                kinds[r["kind"]].add(qid)
                kind_runs[r["kind"]] += 1
        if len({r["pass"] for r in runs}) > 1:
            flaky.append(qid)
    return {"s": s, "kinds": kinds, "kind_runs": kind_runs, "flaky": sorted(flaky)}


def write(results_path: Path, bank_list: list[dict], out: Path, repeat: int, bank_path: Path) -> None:
    bank = {q["id"]: q for q in bank_list}
    by = collect(results_path)
    meta = json.loads(results_path.read_text("utf-8")).get("metadata", {})
    n_ans = sum(1 for q in bank_list if q["expect"]["status"] == "answered")
    n_no = len(bank_list) - n_ans

    lines = ["# RAG audit results", "",
             f"- Question bank: `{Path(bank_path).as_posix()}`: {len(bank_list)} questions "
             f"({n_ans} the documents answer, {n_no} they don't or that need a person)",
             f"- Each question asked {repeat} times per system; every rate below counts all runs",
             f"- Graded in code (`audit/grade.py`): expected facts must appear, the citation must point to the "
             f"expected file and page, and questions the documents don't cover must be declined or handed off. No LLM grades anything.",
             f"- promptfoo {meta.get('promptfooVersion', '?')}, run {meta.get('evaluationCreatedAt', '?')}", "",
             "## Summary", "",
             "| | " + " | ".join(by) + " |", "|---|" + "---|" * len(by)]
    sums = {label: summarize(runs, bank) for label, runs in by.items()}
    rows = [
        ("Answerable questions answered correctly", lambda x: _pct(x["s"]["ans_pass"], x["s"]["ans_runs"])),
        ("Questions it should decline: answered anyway (made up)", lambda x: _pct(x["s"]["made_up"], x["s"]["no_runs"])),
        ("Correct answers citing the right file and page", lambda x: _pct(x["s"]["cite_ok"], x["s"]["cite_runs"]) if x["s"]["cite_runs"] else "n/a (no correct answers, or no sources returned)"),
        ("Right passage among the retrieved ones", lambda x: _pct(x["s"]["ret_hit"], x["s"]["ret_runs"]) if x["s"]["ret_runs"] else "not exposed"),
        ("Questions with different results across runs", lambda x: f"{len(x['flaky'])}" + (f" ({', '.join(x['flaky'])})" if x["flaky"] else "")),
    ]
    for name, fn in rows:
        lines.append(f"| {name} | " + " | ".join(fn(sums[l]) for l in by) + " |")

    for label, x in sums.items():
        lines += ["", f"## Failures: {label}", ""]
        if not x["kinds"]:
            lines.append("No failures.")
            continue
        lines += ["| Failure type | Runs | Questions |", "|---|---|---|"]
        for kind, qids in sorted(x["kinds"].items(), key=lambda kv: -x["kind_runs"][kv[0]]):
            lines.append(f"| {FAILURE_TEXT.get(kind, kind)} | {x['kind_runs'][kind]} | {', '.join(sorted(qids))} |")

    lines += ["", "## Question by question", "",
              "| ID | Question | Expected | " + " | ".join(by) + " |", "|---|---|---|" + "---|" * len(by)]
    for q in bank_list:
        cells = []
        for label in by:
            runs = by[label].get(q["id"], [])
            passed = sum(r["pass"] for r in runs)
            kinds = sorted({r["kind"] for r in runs if r["kind"]})
            cells.append(f"{passed}/{len(runs)} pass" + (f" ({', '.join(kinds)})" if kinds else ""))
        lines.append(f"| {q['id']} | {q['question'].replace('|', '/')} | {q['expect']['status']} | " + " | ".join(cells) + " |")

    (out / "report.md").write_text("\n".join(lines) + "\n", "utf-8")

    with (out / "per-question.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["system", "id", "category", "question", "expected", "run", "pass", "failure_type",
                    "reason", "answer", "citations", "latency_ms"])
        for label, runs_by_q in by.items():
            for qid, runs in runs_by_q.items():
                for i, r in enumerate(runs, 1):
                    w.writerow([label, qid, bank[qid].get("category", ""), bank[qid]["question"],
                                bank[qid]["expect"]["status"], i, r["pass"], r["kind"], r["reason"],
                                " ".join(r["answer"].split()),
                                "; ".join(f"{c['source']} p.{c['page']}" for c in r["citations"]), r["ms"]])
