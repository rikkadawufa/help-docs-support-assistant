"""Turn promptfoo's results.json into dataset.json, report.md and per-question.csv.

    python audit/report.py output/audit/<run> --bank ../holdout/questions.json

Every number is counted once, in build_dataset(), and written to <run>/dataset.json.
report.md, per-question.csv and any client report read that file instead of counting again.
Rulings made after a run (pass or fail changed by a person) come from <run>/audit-notes.yaml
when it exists; the graded result is kept next to the ruled one.

Reads only what audit/grade.py put in each result (pass, "fail:<type>" reason, named scores),
so the report never re-grades and never calls an LLM.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import yaml

import grade

AUDIT = Path(__file__).resolve().parent
FINDINGS = AUDIT / "findings.yaml"
FALLBACK_TEXT = {"ruled_fail": "Changed to a fail by a ruling after the run"}


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


def _label(src: dict) -> str:
    return f"{src.get('source')} p.{src.get('page')}"


def classify(question_kind: str, base: str) -> str:
    """Split grade.py's failure type by question type. A retrieval miss stays a retrieval miss."""
    if not base or base == "retrieval_miss":
        return base
    if base == "made_up_answer":
        return {"trap_stitching": "stitched_rule", "account": "answered_account"}.get(question_kind, "made_up_answer")
    if base == "over_refusal" and question_kind in ("trap_false_premise", "trap_outdated"):
        return "premise_not_corrected"
    return base


def load_rulings(run_dir: Path) -> list[dict]:
    notes = Path(run_dir) / "audit-notes.yaml"
    if not notes.exists():
        return []
    return (yaml.safe_load(notes.read_text("utf-8")) or {}).get("rulings") or []


def build_dataset(results: dict, bank: list[dict], rulings: list[dict]) -> dict:
    """One record per question, system and run, plus every count the reports use."""
    by_id = {q["id"]: q for q in bank}
    ruled = {(r["system"], r["qid"]): r for r in rulings}
    systems: list[str] = []
    runs = defaultdict(lambda: defaultdict(list))
    for row in results["results"]["results"]:
        label = row["provider"].get("label") or row["provider"]["id"]
        if label not in systems:
            systems.append(label)
        qid = row["vars"]["id"]
        g = row.get("gradingResult") or {}
        reason = g.get("reason") or row.get("error") or "fail:bad_response | no grading result"
        out = _output(row)
        graded_pass = bool(row.get("success"))
        base = _kind(reason) if not graded_pass else ""
        graded_finding = classify(by_id[qid]["kind"], base)
        ruling = ruled.get((label, qid))
        final = graded_pass if ruling is None else ruling["to"] == "pass"
        finding = "" if final else (graded_finding or "ruled_fail")
        runs[label][qid].append({
            "pass": final, "graded_pass": graded_pass, "ruled": ruling is not None,
            "base_kind": base, "graded_finding": graded_finding, "finding": finding, "reason": reason,
            "scores": g.get("namedScores") or row.get("namedScores") or {},
            "answer": " ".join((out.get("answer") or "").split()),
            "cites": out.get("citations") is not None,
            "citations": [_label(c) for c in out.get("citations") or []],
            "retrieved": [_label(c) for c in out.get("retrieved") or []],
            "ms": row.get("latencyMs") or 0})
    unknown = [f"{s} / {q}" for s, q in ruled if s not in systems or q not in by_id]
    if unknown:
        raise ValueError("rulings name a system or question not in this run: " + ", ".join(unknown))

    summary = {}
    for label in systems:
        s = defaultdict(int)
        by_kind = {}
        failures = {}
        flaky = []
        for q in bank:
            qruns = runs[label].get(q["id"], [])
            k = by_kind.setdefault(q["kind"], {"questions": 0, "runs": 0, "passed": 0, "failing": []})
            k["questions"] += 1
            k["runs"] += len(qruns)
            k["passed"] += sum(r["pass"] for r in qruns)
            if not all(r["pass"] for r in qruns):
                k["failing"].append(q["id"])
            if len({r["pass"] for r in qruns}) > 1:
                flaky.append(q["id"])
            for r in qruns:
                sc = r["scores"]
                if q["expect"]["status"] == "answered":
                    s["ans_runs"] += 1
                    s["ans_pass"] += r["pass"]
                    sources = q["expect"].get("sources") or []
                    if r["pass"] and r["cites"] and sources:
                        s["cite_runs"] += 1
                        cited = [{"source": c.rsplit(" p.", 1)[0], "page": int(c.rsplit(" p.", 1)[1])}
                                 for c in r["citations"]]
                        s["cite_ok"] += grade._match(cited, sources)
                else:
                    s["no_runs"] += 1
                    s["made_up"] += not r["pass"]
                if "retrieval_hit" in sc:
                    s["ret_runs"] += 1
                    s["ret_hit"] += int(sc["retrieval_hit"])
                if r["finding"]:
                    s["fail_runs"] += 1
                    f = failures.setdefault(r["finding"], {"runs": 0, "questions": [], "base_kinds": []})
                    f["runs"] += 1
                    if q["id"] not in f["questions"]:
                        f["questions"].append(q["id"])
                    if r["base_kind"] and r["base_kind"] not in f["base_kinds"]:
                        f["base_kinds"].append(r["base_kind"])
        repeats = {len(v) for v in runs[label].values()}
        summary[label] = {**{k: s[k] for k in ("ans_runs", "ans_pass", "cite_runs", "cite_ok", "no_runs",
                                               "made_up", "ret_runs", "ret_hit", "fail_runs")},
                          "repeat": max(repeats) if repeats else 0, "flaky": flaky,
                          "by_kind": by_kind, "failures": failures}

    meta = results.get("metadata", {})
    return {
        "promptfoo": meta.get("promptfooVersion", "?"), "created": meta.get("evaluationCreatedAt", "?"),
        "systems": systems,
        "questions": [{"id": q["id"], "kind": q["kind"], "category": q.get("category", ""),
                       "question": q["question"], "status": q["expect"]["status"],
                       "sources": q["expect"].get("sources") or []} for q in bank],
        "rulings": rulings,
        "runs": {label: dict(runs[label]) for label in systems},
        "summary": summary,
    }


def write_dataset(results_path: Path, bank_list: list[dict], out: Path, bank_path: Path,
                  rulings: list[dict] | None = None) -> dict:
    results = json.loads(Path(results_path).read_text("utf-8"))
    data = build_dataset(results, bank_list, rulings if rulings is not None else load_rulings(out))
    data["run"] = Path(out).name
    data["bank"] = Path(bank_path).as_posix()
    (Path(out) / "dataset.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")
    return data


def failure_titles() -> dict[str, str]:
    entries = yaml.safe_load(FINDINGS.read_text("utf-8")) if FINDINGS.exists() else []
    return {**FALLBACK_TEXT, **{e["id"]: e["title"] for e in entries or []}}


def write_markdown(out: Path) -> None:
    data = json.loads((Path(out) / "dataset.json").read_text("utf-8"))
    titles = failure_titles()
    labels = data["systems"]
    qs = data["questions"]
    sums = data["summary"]
    n_ans = sum(1 for q in qs if q["status"] == "answered")
    repeat = max(x["repeat"] for x in sums.values())
    ruled = {(r["system"], r["qid"]) for r in data["rulings"]}

    lines = ["# RAG audit results", "",
             f"- Question bank: `{data['bank']}`: {len(qs)} questions "
             f"({n_ans} the documents answer, {len(qs) - n_ans} they don't or that need a person)",
             f"- Each question asked {repeat} times per system; every rate below counts all runs",
             f"- Graded in code (`audit/grade.py`): expected facts must appear, the citation must point to the "
             f"expected file and page, and questions the documents don't cover must be declined or handed off. No LLM grades anything.",
             f"- promptfoo {data['promptfoo']}, run {data['created']}"]
    if data["rulings"]:
        lines.append(f"- Includes {len(data['rulings'])} ruling(s) made after the run, marked * below")
    lines += ["", "## Summary", "", "| | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    rows = [
        ("Answerable questions answered correctly", lambda x: _pct(x["ans_pass"], x["ans_runs"])),
        ("Questions it should decline: answered anyway (made up)", lambda x: _pct(x["made_up"], x["no_runs"])),
        ("Correct answers citing the right file and page", lambda x: _pct(x["cite_ok"], x["cite_runs"]) if x["cite_runs"] else "n/a (no correct answers, or no sources returned)"),
        ("Right passage among the retrieved ones", lambda x: _pct(x["ret_hit"], x["ret_runs"]) if x["ret_runs"] else "not exposed"),
        ("Questions with different results across runs", lambda x: f"{len(x['flaky'])}" + (f" ({', '.join(x['flaky'])})" if x["flaky"] else "")),
    ]
    for name, fn in rows:
        lines.append(f"| {name} | " + " | ".join(fn(sums[l]) for l in labels) + " |")

    for label in labels:
        failures = sums[label]["failures"]
        lines += ["", f"## Failures: {label}", ""]
        if not failures:
            lines.append("No failures.")
            continue
        lines += ["| Failure type | Runs | Questions |", "|---|---|---|"]
        for fid, f in sorted(failures.items(), key=lambda kv: -kv[1]["runs"]):
            lines.append(f"| {titles.get(fid, fid)} | {f['runs']} | {', '.join(sorted(f['questions']))} |")

    if data["rulings"]:
        lines += ["", "## Rulings after the run", "", "| ID | System | Changed to | Reason | Decided by |",
                  "|---|---|---|---|---|"]
        for r in data["rulings"]:
            lines.append(f"| {r['qid']} | {r['system']} | {r['to']} | {' '.join(str(r['reason']).split())} | {r['decided_by']} |")

    lines += ["", "## Question by question", "",
              "| ID | Question | Expected | " + " | ".join(labels) + " |", "|---|---|---|" + "---|" * len(labels)]
    for q in qs:
        cells = []
        for label in labels:
            runs = data["runs"][label].get(q["id"], [])
            passed = sum(r["pass"] for r in runs)
            kinds = sorted({r["finding"] for r in runs if r["finding"]})
            star = "*" if (label, q["id"]) in ruled else ""
            cells.append(f"{passed}/{len(runs)} pass{star}" + (f" ({', '.join(kinds)})" if kinds else ""))
        lines.append(f"| {q['id']} | {q['question'].replace('|', '/')} | {q['status']} | " + " | ".join(cells) + " |")
    (Path(out) / "report.md").write_text("\n".join(lines) + "\n", "utf-8")


def write_csv(out: Path) -> None:
    data = json.loads((Path(out) / "dataset.json").read_text("utf-8"))
    qs = {q["id"]: q for q in data["questions"]}
    with (Path(out) / "per-question.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["system", "id", "category", "question", "expected", "run", "pass", "failure_type",
                    "reason", "answer", "citations", "latency_ms", "finding", "ruled", "final_pass"])
        for label in data["systems"]:
            for qid, runs in data["runs"][label].items():
                q = qs[qid]
                for i, r in enumerate(runs, 1):
                    w.writerow([label, qid, q["category"], q["question"], q["status"], i, r["graded_pass"],
                                r["base_kind"], r["reason"], r["answer"], "; ".join(r["citations"]), r["ms"],
                                r["finding"], r["ruled"], r["pass"]])


def write(results_path: Path, bank_list: list[dict], out: Path, bank_path: Path,
          rulings: list[dict] | None = None) -> dict:
    data = write_dataset(results_path, bank_list, out, bank_path, rulings)
    write_markdown(out)
    write_csv(out)
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path, help="a folder under output/audit/")
    ap.add_argument("--bank", type=Path, required=True)
    args = ap.parse_args()
    raw = json.loads(args.bank.read_text("utf-8"))
    bank = raw["questions"] if isinstance(raw, dict) else raw
    write(args.run / "results.json", bank, args.run, args.bank)
    print("wrote", (args.run / "dataset.json").as_posix(), "report.md, per-question.csv")


if __name__ == "__main__":
    main()
