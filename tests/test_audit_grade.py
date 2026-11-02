import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "audit"))
import grade  # noqa: E402

ANSWERABLE = {"status": "answered", "facts": [r"\b(5|five)[- ]years?\b"],
              "sources": [{"source": "warranty.pdf", "page": 2}]}
TRAP = {"status": "handoff"}
RIGHT = [{"source": "warranty.pdf", "page": 2}]
WRONG = [{"source": "warranty.pdf", "page": 1}]


def reply(answered=True, answer="It's covered for 5 years.", citations=RIGHT, retrieved=RIGHT):
    return {"answered": answered, "answer": answer, "citations": citations, "retrieved": retrieved}


def kind(r, expect):
    return grade.grade(r, expect)[1]


def test_correct_answer_with_right_citation_passes():
    ok, k, _, scores = grade.grade(reply(), ANSWERABLE)
    assert ok and k == ""
    assert scores == {"retrieval_hit": 1.0, "answered_correctly": 1.0, "citation_correct": 1.0}


def test_failure_types_for_answerable_questions():
    assert kind(reply(citations=WRONG), ANSWERABLE) == "wrong_citation"
    assert kind(reply(answer="2 years", citations=RIGHT), ANSWERABLE) == "wrong_answer_right_source"
    assert kind(reply(answer="2 years", citations=WRONG), ANSWERABLE) == "wrong_answer_wrong_source"
    assert kind(reply(answer="2 years", citations=[]), ANSWERABLE) == "wrong_answer_no_source"
    assert kind(reply(answered=False, retrieved=WRONG), ANSWERABLE) == "retrieval_miss"
    assert kind(reply(answered=False, retrieved=RIGHT), ANSWERABLE) == "over_refusal"
    assert kind(reply(answered=False, retrieved=[]), ANSWERABLE) == "over_refusal"


def test_page_zero_matches_any_page_of_the_file():
    expect = {**ANSWERABLE, "sources": [{"source": "warranty.pdf", "page": 0}]}
    assert grade.grade(reply(citations=WRONG), expect)[0]


def test_trap_questions():
    assert grade.grade(reply(answered=False), TRAP)[0]
    assert kind(reply(answered=True), TRAP) == "made_up_answer"


def test_free_text_target_uses_refusal_pattern_and_skips_citations():
    free = reply(answered=None, citations=None)
    assert grade.grade(free, ANSWERABLE)[0]
    assert kind({**free, "answer": "2 years"}, ANSWERABLE) == "wrong_answer"
    assert grade.grade({**free, "answer": "Sorry, that isn't mentioned in our documents."}, TRAP)[0]
    assert kind({**free, "answer": "Yes, we price match."}, TRAP) == "made_up_answer"


def test_get_assert_reason_prefix_and_bad_json():
    ctx = {"vars": {"expect": ANSWERABLE}}
    assert grade.get_assert(json.dumps(reply()), ctx)["reason"].startswith("pass")
    assert grade.get_assert(json.dumps(reply(citations=WRONG)), ctx)["reason"].startswith("fail:wrong_citation")
    bad = grade.get_assert("not json", ctx)
    assert not bad["pass"] and bad["reason"].startswith("fail:bad_response")
