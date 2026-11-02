import copy
import json
import sys
from pathlib import Path

import pytest

AUDIT = Path(__file__).resolve().parent.parent / "audit"
sys.path.insert(0, str(AUDIT))
import notes as N  # noqa: E402
import report  # noqa: E402

A, B = "Assistant", "Baseline"
BANK = [
    {"id": "H01", "kind": "answerable", "question": "Plain?", "expect": {"status": "answered", "facts": ["x"], "sources": [{"source": "a.md", "page": 1}]}},
    {"id": "H02", "kind": "trap_stitching", "question": "Stitch?", "expect": {"status": "handoff", "facts": [], "sources": []}},
    {"id": "H03", "kind": "trap_false_premise", "question": "Premise?", "expect": {"status": "answered", "facts": ["y"], "sources": [{"source": "b.md", "page": 2}]}},
    {"id": "H04", "kind": "account", "question": "Order?", "expect": {"status": "handoff", "facts": [], "sources": []}},
]
# (system, qid) -> grade.py reason per run
REASONS = {
    (A, "H01"): ["pass", "pass"],
    (A, "H02"): ["fail:made_up_answer", "fail:made_up_answer"],
    (A, "H03"): ["fail:over_refusal", "fail:retrieval_miss"],
    (A, "H04"): ["pass", "fail:made_up_answer"],
    (B, "H01"): ["fail:wrong_answer_right_source", "pass"],
    (B, "H02"): ["fail:made_up_answer", "pass"],
    (B, "H03"): ["pass", "pass"],
    (B, "H04"): ["pass", "pass"],
}
FINDINGS = N.load(AUDIT / "findings.yaml")


def results():
    rows = []
    for (system, qid), reasons in REASONS.items():
        for reason in reasons:
            rows.append({"provider": {"id": "https", "label": system}, "vars": {"id": qid},
                         "success": reason == "pass", "gradingResult": {"reason": reason + " | detail", "namedScores": {}},
                         "response": {"output": json.dumps({"answer": f"answer to {qid}", "citations": [{"source": "a.md", "page": 1}],
                                                            "retrieved": [{"source": "a.md", "page": 1}]})}})
    return {"results": {"results": rows}, "metadata": {"evaluationCreatedAt": "2026-11-02T01:00:00Z"}}


GOOD = {
    "systems": {"audited": A, "baseline": B},
    "headline_summary": "Mostly safe", "headline_results": "Where it wins", "intro": "{n_q} questions, {repeat} runs each.",
    "verdict": "Fix the stitching first.", "summary_note": "Citations checked.", "results_intro": "Better on traps.",
    "method": ["Each question asked {repeat} times."], "limits": "Run on {run_date}.", "retest": "Re-run fix {fix_no:stitched_rule}.",
    "footer": "Sample.", "disclosure": "AI helped draft the analysis, and I reviewed it before delivery.",
    "cases": [{"qid": "H02", "finding": "stitched_rule", "explanation": ["Failed {fail_runs:H02} of {repeat}: {answer:H02}"]}],
    "effort": [{"finding": "stitched_rule", "hours": [3, 4], "basis": "One check step."},
               {"finding": ["premise_not_corrected", "retrieval_miss"], "hours": 2, "basis": "Prompt and index."},
               {"finding": "answered_account", "hours": [1, 2], "basis": "A router."}],
    "risk_overrides": [{"finding": "retrieval_miss", "risk": "low", "reason": "Only one question."}],
    "rulings": [],
}


def check(notes, rulings=None):
    data = report.build_dataset(results(), BANK, rulings if rulings is not None else notes.get("rulings") or [])
    return N.check(notes, FINDINGS, data, Path("."))


def changed(**kw):
    notes = copy.deepcopy(GOOD)
    notes.update(kw)
    return notes


def test_classify_splits_by_question_type_and_keeps_retrieval_miss():
    assert report.classify("trap_stitching", "made_up_answer") == "stitched_rule"
    assert report.classify("trap_not_covered", "made_up_answer") == "made_up_answer"
    assert report.classify("account", "made_up_answer") == "answered_account"
    assert report.classify("trap_outdated", "over_refusal") == "premise_not_corrected"
    assert report.classify("answerable", "over_refusal") == "over_refusal"
    assert report.classify("trap_false_premise", "retrieval_miss") == "retrieval_miss"
    assert report.classify("answerable", "") == ""


def test_dataset_counts_and_failure_split_add_up():
    data = report.build_dataset(results(), BANK, [])
    s = data["summary"][A]
    assert {k: v["runs"] for k, v in s["failures"].items()} == {
        "stitched_rule": 2, "premise_not_corrected": 1, "retrieval_miss": 1, "answered_account": 1}
    assert s["fail_runs"] == 5 == sum(v["runs"] for v in s["failures"].values())
    assert s["made_up"] == 3 and s["no_runs"] == 4


def test_ruling_changes_pass_and_keeps_graded_result():
    ruling = {"qid": "H01", "system": B, "to": "pass", "reason": "Right answer.", "decided_by": "owner"}
    data = report.build_dataset(results(), BANK, [ruling])
    run = data["runs"][B]["H01"][0]
    assert run["pass"] and not run["graded_pass"] and run["ruled"]
    assert data["summary"][B]["ans_pass"] == 4


def test_good_notes_pass_and_render():
    assert check(GOOD) == []
    data = report.build_dataset(results(), BANK, [])
    ctx = N.Context(GOOD, data, Path("."), {f["id"]: f for f in FINDINGS})
    assert N.render(GOOD["intro"], ctx) == "4 questions, 2 runs each."
    assert N.render(GOOD["retest"], ctx) == "Re-run fix 1."


def test_case_on_a_question_that_never_failed_is_rejected():
    errors = check(changed(cases=[{"qid": "H01", "finding": "over_refusal", "explanation": ["x"]}]))
    assert any("H01 never failed" in e for e in errors)


def test_case_with_the_wrong_failure_type_is_rejected():
    errors = check(changed(cases=[{"qid": "H03", "finding": "over_refusal", "explanation": ["x"]}]))
    assert any("failed as premise_not_corrected, retrieval_miss" in e for e in errors)


def test_a_number_written_in_the_text_is_rejected():
    errors = check(changed(verdict="It made up answers in 9 of 45 runs."))
    assert any(e.startswith("verdict: write numbers as placeholders") for e in errors)


def test_allowed_numbers_pass():
    assert N.numbers_in("H51 on November 2, 2026, see warranty.pdf page 2 and p.3, gpt-4o-mini, {made_up_pct}%") == []
    assert N.numbers_in("$75 order") == ["$75"]


def test_empty_or_placeholder_verdict_is_rejected():
    assert any("verdict is empty" in e for e in check(changed(verdict="")))
    assert any("verdict is empty" in e for e in check(changed(verdict="[TO BE ADDED]")))


def test_risk_change_without_reason_is_rejected():
    errors = check(changed(risk_overrides=[{"finding": "retrieval_miss", "risk": "low"}]))
    assert any("without a reason" in e for e in errors)
    assert check(changed(risk_overrides=[{"finding": "retrieval_miss", "risk": "medium"}])) == []


def test_unknown_placeholder_is_rejected():
    errors = check(changed(limits="Run on {run_day}."))
    assert any("unknown placeholder {run_day}" in e for e in errors)


def test_failure_type_without_effort_is_rejected():
    errors = check(changed(effort=GOOD["effort"][:2]))
    assert any("'answered_account' occurs" in e and "no effort entry" in e for e in errors)


def quote_case(text):
    return [{"qid": "H02", "finding": "stitched_rule", "explanation": [text]}]


def test_quote_found_in_the_document_may_contain_numbers(tmp_path):
    (tmp_path / "rewards.md").write_text("# Rewards\nEvery 100 points can be\nredeemed for $5 off.\n", "utf-8")
    notes = changed(documents_dir=str(tmp_path),
                    cases=quote_case("The rewards page: [[rewards.md: Every 100 points can be redeemed for $5 off.]]"))
    assert check(notes) == []
    data = report.build_dataset(results(), BANK, [])
    html = N.render(notes["cases"][0]["explanation"][0], N.Context(notes, data, Path(".")))
    assert html == 'The rewards page: <span class=quote>"Every 100 points can be redeemed for $5 off."</span>'


def test_quote_not_in_the_document_is_rejected(tmp_path):
    (tmp_path / "rewards.md").write_text("Every 100 points can be redeemed for $5 off.", "utf-8")
    errors = check(changed(documents_dir=str(tmp_path),
                           cases=quote_case("[[rewards.md: Every 100 points can be redeemed for $10 off.]]")))
    assert any('quote not found in rewards.md: "Every 100 points can be redeemed for $10 off."' in e for e in errors)
    errors = check(changed(documents_dir=str(tmp_path), cases=quote_case("[[rewards.md p.2: Every 100 points]]")))
    assert any("has no pages" in e for e in errors)
    errors = check(changed(documents_dir=str(tmp_path), cases=quote_case("[[missing.md: text]]")))
    assert any("no document missing.md" in e for e in errors)


def test_numbers_outside_a_quote_are_still_rejected(tmp_path):
    (tmp_path / "rewards.md").write_text("Every 100 points can be redeemed for $5 off.", "utf-8")
    errors = check(changed(documents_dir=str(tmp_path),
                           cases=quote_case("[[rewards.md: Every 100 points]] Failed in 2 runs.")))
    assert any("not 2" in e for e in errors)


def test_rulings_must_match_the_dataset():
    ruling = {"qid": "H01", "system": B, "to": "pass", "reason": "Right answer.", "decided_by": "owner"}
    assert check(changed(rulings=[ruling])) == []
    assert any("different rulings" in e for e in check(changed(rulings=[ruling]), rulings=[]))
    with pytest.raises(ValueError):
        report.build_dataset(results(), BANK, [{**ruling, "qid": "H99"}])
