import pytest

from app.citations import decide

RETRIEVED = {"faq.md#s-payment-methods#c0": "We accept Visa, Mastercard, American Express, Discover, PayPal and Apple Pay."}


@pytest.mark.parametrize("parsed", [
    None,
    "not a dict",
    {},
    {"answerable": True},
    {"answerable": True, "answer": "", "citations": []},
    {"answerable": True, "answer": "Visa.", "citations": "faq.md"},
    {"answerable": True, "answer": 42, "citations": []},
    {"answerable": True, "answer": "Visa.", "citations": ["not a dict", 3]},
    {"answerable": "yes", "answer": "Visa.", "citations": []},
])
def test_malformed_model_output_hands_off_without_raising(parsed):
    d = decide(parsed, RETRIEVED)
    assert d.status == "handoff"
