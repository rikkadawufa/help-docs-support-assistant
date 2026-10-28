import pytest

from app.answer import GroundedAssistant
from app.citations import decide
from app.config import Settings
from app.store import Retrieved

RETRIEVED = {"warranty.pdf#p2#c0": "Coolers Glacier 45 5 years"}
GOOD = {"chunk_id": "warranty.pdf#p2#c0", "quote": "Coolers Glacier 45 5 years"}
BAD = {"chunk_id": "warranty.pdf#p2#c0", "quote": "Coolers have a lifetime warranty"}


def test_model_declined_hands_off():
    d = decide({"answerable": False, "answer": "", "citations": []}, RETRIEVED)
    assert (d.status, d.reason) == ("handoff", "model_declined")


def test_answer_without_valid_citation_hands_off():
    d = decide({"answerable": True, "answer": "Lifetime.", "citations": [BAD]}, RETRIEVED)
    assert (d.status, d.reason) == ("handoff", "no_valid_citation")
    assert d.invalid[0].problem == "quote_not_in_chunk"


def test_answer_with_no_citations_hands_off():
    d = decide({"answerable": True, "answer": "5 years.", "citations": []}, RETRIEVED)
    assert (d.status, d.reason) == ("handoff", "no_valid_citation")


def test_mixed_citations_answer_with_valid_ones_only():
    d = decide({"answerable": True, "answer": "5 years.", "citations": [GOOD, BAD]}, RETRIEVED)
    assert d.status == "answered"
    assert len(d.valid) == 1 and len(d.invalid) == 1


def test_all_valid_answers():
    d = decide({"answerable": True, "answer": "5 years.", "citations": [GOOD]}, RETRIEVED)
    assert d.status == "answered" and not d.invalid


# --- the relevance gate: below the threshold the model must not be called ---

class CountingLLM:
    def __init__(self):
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return {"answerable": True, "answer": "x", "citations": []}


class FakeStore:
    def __init__(self, score):
        self.score = score


@pytest.fixture
def no_side_effects(monkeypatch, tmp_path):
    import app.answer as answer_mod
    import app.handoff as handoff_mod
    monkeypatch.setattr(handoff_mod, "LOG_PATH", tmp_path / "handoff.jsonl")
    monkeypatch.setattr(answer_mod, "retrieve", lambda store, q, k: [
        Retrieved("warranty.pdf#p2#c0", "warranty.pdf", 2, "", RETRIEVED["warranty.pdf#p2#c0"], store.score)])
    return tmp_path


def make_bot(score, llm):
    bot = GroundedAssistant(Settings(llm_mode="live", relevance_min=0.4), FakeStore(score))
    bot._structured = lambda: llm
    return bot


def test_below_threshold_never_calls_model(no_side_effects):
    llm = CountingLLM()
    reply = make_bot(0.2, llm).ask("Do you rent coolers?")
    assert llm.calls == 0
    assert (reply.status, reply.reason) == ("handoff", "low_relevance")
    assert (no_side_effects / "handoff.jsonl").exists()


def test_above_threshold_calls_model(no_side_effects):
    llm = CountingLLM()
    make_bot(0.8, llm).ask("Cooler warranty?")
    assert llm.calls == 1
