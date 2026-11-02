from app.citations import check_citation, normalize

CHUNK = "Refunds are issued to the original payment method within 5–7 business days after we receive it."
RETRIEVED = {"returns-policy.pdf#p2#c0": CHUNK}


def test_exact_quote_is_valid():
    c = check_citation("returns-policy.pdf#p2#c0", "within 5–7 business days", RETRIEVED)
    assert c.valid


def test_normalizes_case_whitespace_and_dashes():
    c = check_citation("returns-policy.pdf#p2#c0", "Issued to the  original\npayment method within 5-7", RETRIEVED)
    assert c.valid


def test_curly_quotes_and_ligatures_match_plain_text():
    retrieved = {"x#p1#c0": "We don't offer direct exchanges, effective today."}
    assert check_citation("x#p1#c0", "We don’t offer direct exchanges", retrieved).valid
    assert check_citation("x#p1#c0", "exchanges, eﬀective today", retrieved).valid


def test_dash_returned_as_escaped_utf8_bytes_still_matches():
    # seen live: the model returned "5–7" with the en dash as lone surrogates \udce2\udc80\udc93
    c = check_citation("returns-policy.pdf#p2#c0", "within 5\udce2\udc80\udc937 business days", RETRIEVED)
    assert c.valid


def test_quote_not_in_chunk_is_rejected():
    c = check_citation("returns-policy.pdf#p2#c0", "within 3 business days", RETRIEVED)
    assert not c.valid and c.problem == "quote_not_in_chunk"


def test_chunk_that_was_not_retrieved_is_rejected():
    c = check_citation("warranty.pdf#p2#c0", "within 5-7 business days", RETRIEVED)
    assert not c.valid and c.problem == "chunk_not_retrieved"


def test_tiny_quote_is_rejected():
    c = check_citation("returns-policy.pdf#p2#c0", "the", RETRIEVED)
    assert not c.valid and c.problem == "quote_too_short"


def test_normalize_collapses_whitespace():
    assert normalize("  A\n\tB  ") == "a b"


def test_joined_sentences_from_same_passage_are_valid():
    retrieved = {"m#p2#c0": "Wash in cold water. Top-loaders can tear it. Use mild soap."}
    assert check_citation("m#p2#c0", "Wash in cold water. Use mild soap.", retrieved).valid


def test_one_made_up_sentence_fails_the_whole_quote():
    retrieved = {"m#p2#c0": "Wash in cold water. Top-loaders can tear it. Use mild soap."}
    c = check_citation("m#p2#c0", "Wash in cold water. Bleach is fine too.", retrieved)
    assert not c.valid and c.problem == "quote_not_in_chunk"


def test_layout_punctuation_is_ignored_but_words_must_match():
    retrieved = {"w#p2#c0": "Items we can't take back\nFuel canisters cannot be returned.\nCoolers | Glacier 45 | 5 years"}
    assert check_citation("w#p2#c0", "Items we can't take back: Fuel canisters cannot be returned.", retrieved).valid
    assert check_citation("w#p2#c0", "Coolers, Glacier 45, 5 years", retrieved).valid
    assert not check_citation("w#p2#c0", "Coolers, Glacier 45, 7 years", retrieved).valid


def test_skipping_words_inside_a_sentence_fails():
    retrieved = {"h#p1#c0": "Runtime | 6 hours on high, 40 hours on low"}
    assert not check_citation("h#p1#c0", "Runtime 40 hours on low", retrieved).valid
