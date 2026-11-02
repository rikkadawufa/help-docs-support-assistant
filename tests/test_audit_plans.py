"""Report layer: search-or-answer causes, and the per-plan checks on the hand-written notes."""
import copy
import csv
import json
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "audit"
sys.path.insert(0, str(AUDIT))
import notes as N  # noqa: E402
import report  # noqa: E402
from test_audit_notes import BANK, FINDINGS, GOOD, A, B, results  # noqa: E402

STARTER = N.load_plan("starter")
SET = {"go_plain_pct_min": 90, "go_made_up_pct_max": 10, "no_go_plain_pct_below": 50, "no_go_made_up_pct_above": 40}


def starter(**thresholds):
    return {**STARTER, "thresholds": {**SET, **thresholds}}


def rows(spec):
    """spec: (system, qid) -> [(reason, retrieval_hit or None)] per run."""
    out = []
    for (system, qid), runs in spec.items():
        for reason, hit in runs:
            scores = {} if hit is None else {"retrieval_hit": float(hit)}
            out.append({"provider": {"id": "https", "label": system}, "vars": {"id": qid},
                        "success": reason == "pass", "gradingResult": {"reason": reason + " | x", "namedScores": scores},
                        "response": {"output": json.dumps({"answer": "a", "citations": None, "retrieved": []})}})
    return {"results": {"results": out}, "metadata": {"evaluationCreatedAt": "2026-11-02T01:00:00Z"}}


SPEC = {
    (A, "H01"): [("fail:wrong_answer_right_source", 1), ("fail:retrieval_miss", 0), ("pass", 0)],
    (A, "H02"): [("fail:made_up_answer", None), ("fail:made_up_answer", None), ("pass", None)],
    (A, "H03"): [("fail:over_refusal", 1), ("fail:over_refusal", 1), ("fail:retrieval_miss", 0)],
    (A, "H04"): [("pass", None), ("pass", None), ("pass", None)],
    (B, "H01"): [("fail:wrong_answer", None), ("pass", None), ("pass", None)],
    (B, "H02"): [("pass", None)] * 3,
    (B, "H03"): [("pass", None)] * 3,
    (B, "H04"): [("pass", None)] * 3,
}


def test_each_failed_run_on_an_answerable_question_gets_a_cause():
    data = report.build_dataset(rows(SPEC), BANK, [])
    h01 = data["runs"][A]["H01"]
    assert [r["retrieved_hit"] for r in h01] == ["hit", "miss", "miss"]
    assert [r["cause"] for r in h01] == ["retrieved_answer_wrong", "retrieval_missed", ""]
    # questions the documents don't answer have no search-or-answer cause
    assert {r["cause"] for r in data["runs"][A]["H02"]} == {""}
    # an API that does not return retrieved passages: unknown, never counted as a miss
    assert data["runs"][B]["H01"][0]["cause"] == "retrieval_unknown"


def test_question_cause_is_the_majority_and_a_tie_is_mixed():
    data = report.build_dataset(rows(SPEC), BANK, [])
    causes = data["summary"][A]["causes"]
    assert causes["retrieved_answer_wrong"] == {"runs": 3, "questions": ["H03"]}
    assert causes["retrieval_missed"] == {"runs": 2, "questions": []}
    assert causes["mixed"]["questions"] == ["H01"]
    assert data["summary"][A]["pass_without_hit"] == 1
    assert report.question_cause([{"cause": ""}, {"cause": ""}]) == ""


def test_csv_has_retrieved_and_cause_columns(tmp_path):
    (tmp_path / "results.json").write_text(json.dumps(rows(SPEC)), "utf-8")
    report.write(tmp_path / "results.json", BANK, tmp_path, Path("bank.json"))
    with (tmp_path / "per-question.csv").open(encoding="utf-8-sig") as f:
        got = list(csv.DictReader(f))
    first = next(r for r in got if r["system"] == A and r["id"] == "H01")
    assert first["retrieved"] == "hit" and first["cause"] == "retrieved_answer_wrong"
    assert "## Search or answer step" in (tmp_path / "report.md").read_text("utf-8")


def test_cause_entries_exist_for_every_cause_and_state_no_numbers():
    causes = N.causes(FINDINGS)
    assert set(causes) == set(report.CAUSES) | {"mixed"}
    assert not N.failure_types([{"id": "x", "type": "cause"}])


# ---------- plans ----------

STARTER_NOTES = {k: v for k, v in GOOD.items() if k not in ("headline_results", "results_intro", "effort", "retest")}
STARTER_NOTES.update(verdict_choice="fix_docs_first", cases=GOOD["cases"] + [
    {"qid": "H03", "finding": "premise_not_corrected", "explanation": ["Handed off."]},
    {"qid": "H03", "finding": "retrieval_miss", "explanation": ["Search missed it."]},
    {"qid": "H04", "finding": "answered_account", "explanation": ["Answered an order question."]}])


def check(notes, plan):
    data = report.build_dataset(results(), BANK, notes.get("rulings") or [])
    return N.check(notes, FINDINGS, data, Path("."), plan)


def test_standard_is_the_default_plan():
    assert check(GOOD, None) == [] == check(GOOD, N.load_plan("standard"))


def test_starter_needs_no_effort_and_rejects_fields_it_never_prints():
    # H01 passes every run (100%), made-up runs 3 of 4 (75%) -> no_go with SET
    notes = dict(STARTER_NOTES, verdict_choice="no_go")
    assert check(notes, starter()) == []
    errors = check(dict(notes, effort=GOOD["effort"], retest="Re-run."), starter())
    assert any("effort is not used in the Starter report" in e for e in errors)
    assert any("retest is not used" in e for e in errors)


def test_starter_needs_an_example_of_every_failure_type():
    notes = dict(STARTER_NOTES, verdict_choice="no_go", cases=STARTER_NOTES["cases"][:2])
    errors = check(notes, starter())
    assert any("'retrieval_miss' occurs" in e and "has no case" in e for e in errors)


def test_starter_verdict_must_be_one_of_three():
    errors = check(dict(STARTER_NOTES, verdict_choice="maybe"), starter())
    assert any("verdict_choice must be one of go, fix_docs_first, no_go" in e for e in errors)
    assert any("verdict_choice is empty" in e for e in check(dict(STARTER_NOTES, verdict_choice=""), starter()))


def test_verdict_against_the_thresholds_needs_a_reason():
    errors = check(dict(STARTER_NOTES, verdict_choice="go"), starter())
    assert any("thresholds suggest 'no_go'" in e for e in errors)
    assert check(dict(STARTER_NOTES, verdict_choice="go", verdict_reason="The made-up answers are all one order "
                      "question the client will route to a person."), starter()) == []


def test_unset_thresholds_block_the_report():
    errors = check(dict(STARTER_NOTES, verdict_choice="go"), STARTER)  # plans.yaml as shipped: not decided yet
    assert any("verdict thresholds not set yet" in e for e in errors)


def test_suggested_verdict():
    assert N.suggested_verdict({"plain_pct": 95, "made_up_pct": 5}, SET) == "go"
    assert N.suggested_verdict({"plain_pct": 80, "made_up_pct": 20}, SET) == "fix_docs_first"
    assert N.suggested_verdict({"plain_pct": 40, "made_up_pct": 5}, SET) == "no_go"
    assert N.suggested_verdict({"plain_pct": 95, "made_up_pct": 50}, SET) == "no_go"
    assert N.suggested_verdict({"plain_pct": 95, "made_up_pct": 5}, {**SET, "go_plain_pct_min": None}) is None


def test_citation_claim_is_checked_against_the_run():
    claim = "Every correct answer cited the expected file and page."
    assert check(dict(GOOD, summary_note=claim), None) == []
    data = report.build_dataset(results(), BANK, [])
    data["summary"][A]["cite_ok"] -= 1
    errors = N.check(dict(GOOD, summary_note=claim), FINDINGS, data, Path("."))
    assert any("summary_note: says every correct answer cited the expected file and page" in e for e in errors)


def test_question_counts_come_before_runs():
    data = report.build_dataset(results(), BANK, [])
    v = N.Context(GOOD, data, Path(".")).values
    # H01 passes both runs; H02 never hands off; H04 hands off in one of two runs
    assert (v["plain_q_ok"], v["plain_q"], v["plain_ok"], v["plain_runs"]) == (1, 1, 2, 2)
    assert (v["handoff_q_ok"], v["handoff_q"]) == (0, 2)
    assert (v["account_q_ok"], v["account_q"], v["account_ok"], v["account_runs"]) == (0, 1, 1, 2)
