"""Citation checks and the answer/handoff decision. Pure functions, no I/O."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

MIN_QUOTE_CHARS = 12

_QUOTE_MAP = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-", " ": " ",
})


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_QUOTE_MAP).lower()
    return re.sub(r"\s+", " ", text).strip()


def loose(text: str) -> str:
    """normalize() plus ignoring layout punctuation (colons after headings,
    commas or pipes between table cells). The words themselves must still match."""
    return re.sub(r"\s+", " ", re.sub(r"[:;,|()\"*#_]", " ", normalize(text))).strip()


@dataclass
class CheckedCitation:
    chunk_id: str
    quote: str
    valid: bool
    problem: str = ""  # why it failed, empty when valid


def check_citation(chunk_id: str, quote: str, retrieved: dict[str, str]) -> CheckedCitation:
    """A citation is valid only if it points at a chunk we actually retrieved
    and the quote appears word for word (after normalizing) in that chunk."""
    quote = quote or ""
    if chunk_id not in retrieved:
        return CheckedCitation(chunk_id, quote, False, "chunk_not_retrieved")
    q = normalize(quote).strip(" .\"'")
    if len(q) < MIN_QUOTE_CHARS:
        return CheckedCitation(chunk_id, quote, False, "quote_too_short")
    chunk = loose(retrieved[chunk_id])
    # Models sometimes join two sentences from the same passage and skip the one
    # in between. Accept that only if every sentence is in the passage word for word.
    sentences = [loose(x).strip(" .'") for x in re.split(r"(?<=[.!?])\s+", q)]
    if not all(x in chunk for x in sentences if x):
        return CheckedCitation(chunk_id, quote, False, "quote_not_in_chunk")
    return CheckedCitation(chunk_id, quote, True)


@dataclass
class Decision:
    status: str               # answered | handoff
    reason: str = ""          # empty when answered
    valid: list[CheckedCitation] = field(default_factory=list)
    invalid: list[CheckedCitation] = field(default_factory=list)


def decide(parsed: dict | None, retrieved: dict[str, str]) -> Decision:
    """Turn the model's structured reply into answered/handoff.

    parsed is the raw dict from the model. Anything malformed counts as
    no_valid_citation rather than raising.
    """
    if not isinstance(parsed, dict):
        return Decision("handoff", "no_valid_citation")
    if parsed.get("answerable") is not True:
        return Decision("handoff", "model_declined")
    answer = parsed.get("answer")
    raw = parsed.get("citations")
    if not isinstance(answer, str) or not answer.strip() or not isinstance(raw, list):
        return Decision("handoff", "no_valid_citation")

    checked = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        checked.append(check_citation(str(item.get("chunk_id", "")), str(item.get("quote", "")), retrieved))
    valid = [c for c in checked if c.valid]
    invalid = [c for c in checked if not c.valid]
    if not valid:
        return Decision("handoff", "no_valid_citation", valid, invalid)
    return Decision("answered", "", valid, invalid)
