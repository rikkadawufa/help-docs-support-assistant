"""promptfoo assertion: grade one RAG reply against the question bank, in code.

The target's reply arrives as the JSON string a transform built (see transforms/):
  {"answered": true|false|null, "answer": str,
   "citations": [{"source": str, "page": int}] | null, "retrieved": [{"source": str, "page": int}]}
answered=null means the target only returns free text, so a refusal pattern decides.
citations=null means the target never returns sources, so citations are not graded.

The question's expectation comes from the bank (vars.expect):
  {"status": "answered"|"handoff", "facts": [regex], "sources": [{"source", "page"}]}
page 0 in an expected source means any page of that file.

No LLM is used for grading. Each result's reason starts with "pass" or
"fail:<failure type>" so report.py can count failure types.
"""
from __future__ import annotations

import json
import re

REFUSAL = re.compile(
    r"don't have|do not have|no information|not (mentioned|specified|covered|included|stated|provided|available)"
    r"|couldn't find|can't find|cannot find|unable to (find|confirm)|isn't (mentioned|specified)"
    r"|doesn't (mention|specify|say)|does not (mention|specify|say)|contact (our )?(customer )?support"
    r"|passed your question|support team",
    re.IGNORECASE)


def _match(got: list[dict], want: list[dict]) -> bool:
    for g in got:
        for w in want:
            if g.get("source") == w["source"] and (w.get("page", 0) == 0 or g.get("page") == w["page"]):
                return True
    return False


def grade(reply: dict, expect: dict) -> tuple[bool, str, str, dict]:
    """Return (passed, failure_type or "", detail, named scores)."""
    answer = reply.get("answer") or ""
    answered = reply.get("answered")
    if answered is None:
        answered = not REFUSAL.search(answer)
    cites = reply.get("citations") is not None
    citations = reply.get("citations") or []
    retrieved = reply.get("retrieved") or []
    want_sources = expect.get("sources") or []
    scores: dict[str, float] = {}

    if retrieved and want_sources:
        scores["retrieval_hit"] = 1.0 if _match(retrieved, want_sources) else 0.0

    if expect["status"] != "answered":
        scores["declined_correctly"] = 0.0 if answered else 1.0
        if answered:
            return False, "made_up_answer", "answered a question the documents don't cover", scores
        return True, "", "declined or handed off", scores

    if not answered:
        scores["answered_correctly"] = 0.0
        if scores.get("retrieval_hit") == 0.0:
            return False, "retrieval_miss", "said it couldn't answer; the right passage was not retrieved", scores
        return False, "over_refusal", "said it couldn't answer although the documents cover it", scores

    facts = expect.get("facts") or []
    missing = [f for f in facts if not re.search(f, answer, re.IGNORECASE)]
    cited_right = _match(citations, want_sources) if (want_sources and cites) else True
    if missing:
        scores["answered_correctly"] = 0.0
        if not cites:
            kind = "wrong_answer"
        elif not citations:
            kind = "wrong_answer_no_source"
        elif cited_right:
            kind = "wrong_answer_right_source"
        else:
            kind = "wrong_answer_wrong_source"
        return False, kind, f"missing expected fact(s): {', '.join(missing)}", scores
    scores["answered_correctly"] = 1.0
    if not cited_right:
        scores["citation_correct"] = 0.0
        return False, "wrong_citation", "right answer, but no citation to the expected file and page", scores
    if want_sources and cites:
        scores["citation_correct"] = 1.0
    cited = ", ".join(sorted({f"{c['source']} p.{c['page']}" for c in citations})) or "no sources returned"
    return True, "", f"correct ({cited})", scores


def get_assert(output: str, context) -> dict:
    expect = context["vars"]["expect"]
    if isinstance(expect, str):
        expect = json.loads(expect)
    try:
        reply = json.loads(output)
    except (TypeError, ValueError):
        return {"pass": False, "score": 0, "reason": "fail:bad_response | target reply was not the expected JSON"}
    passed, kind, detail, scores = grade(reply, expect)
    return {"pass": passed, "score": 1 if passed else 0,
            "reason": ("pass" if passed else f"fail:{kind}") + f" | {detail}",
            "named_scores": scores}
