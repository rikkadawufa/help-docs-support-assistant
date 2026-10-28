import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.server import create_app


class FakeStore:
    def __init__(self):
        self.docs = {"faq.md#s-payment-methods#c0": ("We accept Visa and PayPal.",
                                                    {"source": "faq.md", "page": 0, "section": "Payment methods"})}

    def get(self, ids=None, where=None):
        keys = [k for k in self.docs if ids is None or k in ids]
        return {"ids": keys, "documents": [self.docs[k][0] for k in keys], "metadatas": [self.docs[k][1] for k in keys]}


@pytest.fixture
def client(monkeypatch, tmp_path):
    import app.answer as answer_mod
    import app.handoff as handoff_mod
    import app.server as server_mod
    from app.store import Retrieved

    monkeypatch.setattr(handoff_mod, "LOG_PATH", tmp_path / "handoff.jsonl")
    hit = [Retrieved("faq.md#s-payment-methods#c0", "faq.md", 0, "Payment methods", "We accept Visa and PayPal.", 0.9)]
    monkeypatch.setattr(answer_mod, "retrieve", lambda *a: hit)
    monkeypatch.setattr(server_mod, "retrieve", lambda *a: hit)
    settings = Settings(llm_mode="live", slack_mode="slack", slack_webhook_url="https://hooks.slack.com/services/T/B/x",
                        relevance_min=0.3)
    return TestClient(create_app(settings, FakeStore()))


def test_blank_question_is_422(client):
    assert client.post("/ask", json={"question": "   "}).status_code == 422


def test_long_question_is_422(client):
    assert client.post("/ask", json={"question": "x" * 1001}).status_code == 422


def test_llm_failure_returns_200_degraded(client, monkeypatch):
    import app.answer as answer_mod

    class Broken:
        def invoke(self, messages):
            raise openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))

    monkeypatch.setattr(answer_mod.GroundedAssistant, "_structured", lambda self: Broken())
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(200))
    r = client.post("/ask", json={"question": "Do you take PayPal?"})
    assert r.status_code == 200
    body = r.json()
    assert (body["status"], body["reason"]) == ("degraded", "llm_error")


def test_handoff_survives_slack_failure(client, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(httpx, "post", boom)
    r = client.post("/handoff", json={"question": "I was charged twice"})
    assert r.status_code == 200
    assert r.json()["slack"].startswith("error")


def test_source_lookup(client):
    assert client.get("/source/faq.md#s-payment-methods#c0".replace("#", "%23")).json()["source"] == "faq.md"
    assert client.get("/source/nope").status_code == 404
