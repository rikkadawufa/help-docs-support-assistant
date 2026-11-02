"""Pointing the test assistants at another set of documents: settings, prompts, ingest and the freeze record."""
import hashlib
import json

import pymupdf
import pytest

import app.config as config
from app.config import DEFAULT_HANDOFF_REPLY, Settings, load_settings
from app.ingest import load_chunks
from app.llm import prompt

# sha256 of each system prompt as sent in the held-out run (git tag audit-freeze-1). With no
# BRAND_NAME set, the prompts must still be exactly these, so that run's results describe this code.
FROZEN_PROMPTS = {
    "grounded": "37f34c72b053a479fb24780ffe4253997f4a20e6fecc46838d6dc9067247ee0e",
    "baseline": "755e843583844b646beca59ef87e483c9900f6c2fbf03f7fabf2cf2de1abf181",
}
ENV = ("BRAND_NAME", "HANDOFF_REPLY", "DEGRADED_REPLY", "KNOWLEDGE_DIR", "INDEX_NAME", "PAGE_BANNER", "PAGE_FOOTER", "LLM_MODE")


@pytest.fixture
def clean_env(monkeypatch):
    for key in ENV:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.mark.parametrize("name", FROZEN_PROMPTS)
def test_default_prompts_match_the_frozen_run(name, clean_env):
    text = prompt(name, load_settings().brand_name)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == FROZEN_PROMPTS[name]


def test_brand_is_replaced_everywhere():
    for name in FROZEN_PROMPTS:
        text = prompt(name, "Acme")
        assert "Acme" in text and "Cinderpeak" not in text and "{brand}" not in text


def test_braces_in_a_prompt_are_left_alone(tmp_path, monkeypatch):
    import app.llm as llm
    (tmp_path / "x.md").write_text('Help {brand} customers. Reply as {"answer": "..."} for {brand}.', "utf-8")
    monkeypatch.setattr(llm, "PROMPTS", tmp_path)
    assert prompt("x", "Acme") == 'Help Acme customers. Reply as {"answer": "..."} for Acme.'


def test_defaults_keep_the_demo(clean_env):
    s = load_settings()
    assert s.brand_name == "Cinderpeak Outdoor" and s.handoff_reply == DEFAULT_HANDOFF_REPLY
    assert s.knowledge_dir == config.KNOWLEDGE_DIR
    assert s.chroma_dir.name == "chroma-mock" and s.manifest_path.name == "index-manifest-mock.json"


def test_env_points_at_other_documents_with_their_own_index(clean_env):
    clean_env.setenv("BRAND_NAME", "Acme Tools")
    clean_env.setenv("HANDOFF_REPLY", "A person will reply soon.")
    clean_env.setenv("KNOWLEDGE_DIR", "clients/acme")
    clean_env.setenv("INDEX_NAME", "acme 2026/11")
    clean_env.setenv("PAGE_BANNER", "")
    s = load_settings()
    assert s.brand_name == "Acme Tools" and s.handoff_reply == "A person will reply soon."
    assert s.knowledge_dir == (config.ROOT / "clients" / "acme").resolve()
    assert s.index_name == "acme-2026-11"
    assert s.chroma_dir.name == "chroma-acme-2026-11-mock" != Settings().chroma_dir.name
    assert s.page_banner == "" and s.page_footer == config.DEFAULT_PAGE_FOOTER


def test_handoff_uses_the_configured_reply(monkeypatch, tmp_path):
    import app.answer as answer_mod
    import app.handoff as handoff_mod
    monkeypatch.setattr(handoff_mod, "LOG_PATH", tmp_path / "handoff.jsonl")
    monkeypatch.setattr(answer_mod, "retrieve", lambda *a: [])
    bot = answer_mod.GroundedAssistant(Settings(handoff_reply="Acme support will email you."), store=None)
    reply = bot.ask("Anything?")
    assert reply.status == "handoff" and reply.answer == "Acme support will email you."


def test_model_failure_uses_the_configured_reply(monkeypatch, tmp_path):
    import app.answer as answer_mod
    import app.handoff as handoff_mod
    from app.store import Retrieved

    class Failing:
        def invoke(self, *a, **k):
            raise TimeoutError("model timed out")

    monkeypatch.setattr(handoff_mod, "LOG_PATH", tmp_path / "handoff.jsonl")
    monkeypatch.setattr(answer_mod, "retrieve",
                        lambda *a: [Retrieved("faq.md#c0", "faq.md", 0, "", "Returns take 30 days.", 0.9)])
    bot = answer_mod.GroundedAssistant(Settings(degraded_reply="Please email Acme support."), store=None)
    monkeypatch.setattr(bot, "_structured", lambda: Failing())
    reply = bot.ask("How long do returns take?")
    assert reply.status == "degraded" and reply.answer == "Please email Acme support."


def test_degraded_reply_comes_from_env(clean_env):
    assert load_settings().degraded_reply == config.DEFAULT_DEGRADED_REPLY
    clean_env.setenv("DEGRADED_REPLY", "Please email Acme support.")
    assert load_settings().degraded_reply == "Please email Acme support."


def _pdf(path, lines):
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text((72, 72 + 18 * i), line)
    doc.save(path)


def test_page_boilerplate_patterns_are_settings(tmp_path):
    import re
    path = tmp_path / "guide.pdf"
    _pdf(path, ["Acme Tools | Internal", "Returns are accepted for 30 days.", "Returns guide | p1"])
    # demo patterns: neither line matches, so both stay and the title is the file name
    text = load_chunks(path, "guide.pdf")[0].page_content
    assert text.startswith("guide\n") and "Acme Tools | Internal" in text and "Returns guide | p1" in text
    banner = re.compile(r"^Acme Tools \| Internal\s*$", re.MULTILINE)
    footer = re.compile(r"^(?P<title>.+?) \| p\d+\s*$", re.MULTILINE)
    text = load_chunks(path, "guide.pdf", banner, footer)[0].page_content
    assert text == "Returns guide\nReturns are accepted for 30 days."
    # no patterns: nothing is stripped
    text = load_chunks(path, "guide.pdf", None, None)[0].page_content
    assert "Acme Tools | Internal" in text and "Returns guide | p1" in text


def _frozen_settings(tmp_path, monkeypatch):
    from app.ingest import sync
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A\n\n## Hours\nOpen 9 to 5.\n", "utf-8")
    settings = Settings(llm_mode="mock", knowledge_dir=docs, index_name="acme")
    sync(settings)
    return settings, docs


def test_freeze_record_covers_settings_prompts_and_documents(tmp_path, monkeypatch):
    from app.freeze import ANSWER_SETTINGS, record, verify
    settings, docs = _frozen_settings(tmp_path, monkeypatch)
    rec = record(settings)
    assert verify(rec)
    assert set(rec["settings"]) == set(ANSWER_SETTINGS)
    for key in ("chat_model", "embed_model", "top_k", "relevance_min", "brand_name", "handoff_reply",
                "page_banner", "page_footer"):
        assert key in rec["settings"]
    assert set(rec["documents"]) == {"a.md"} and set(rec["prompts_sha256"]) == {"grounded", "baseline"}
    assert rec["code_sha256"] and "commit" in rec

    other = record(settings.with_overrides(handoff_reply="Something else."))
    assert other["fingerprint"] != rec["fingerprint"]
    edited = json.loads(json.dumps(rec))
    edited["settings"]["top_k"] = 9
    assert not verify(edited)


def test_freeze_refuses_an_index_that_does_not_match_the_documents(tmp_path, monkeypatch):
    from app.freeze import record
    settings, docs = _frozen_settings(tmp_path, monkeypatch)
    (docs / "b.md").write_text("# B\nNew page.\n", "utf-8")
    with pytest.raises(ValueError, match="does not match the documents"):
        record(settings)
