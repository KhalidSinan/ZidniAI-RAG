"""Contract tests for the answer path and the rendering boundary.

Source: specs/001-data-chapter-rag/contracts/answer-contract.md
"""

from __future__ import annotations

import pytest

from kidsrag.generate.answer import build_response, extract_citations, select_images
from kidsrag.models import Answer, Passage, Refusal, RefusalReason, Trouble
from kidsrag.generate.evidence import claims_by_citation, pick_quotes, split_sentences
from kidsrag.render import number_citations, render, strip_citations


def passage(pid: str, images: list[str] | None = None) -> Passage:
    return Passage(
        id=pid,
        heading_path=["Data", "Binary code", pid],
        text=f"Body text for {pid}.",
        pages=[84],
        page_images=images if images is not None else [f"pages/{pid}.png"],
    )


@pytest.fixture
def passages() -> list[Passage]:
    return [passage("a"), passage("b"), passage("c")]


# --- citation check (Principle II, FR-018) ---------------------------------


def test_response_without_citations_becomes_refusal(passages):
    result = build_response("Binary code uses 0 and 1.", passages)
    assert isinstance(result, Refusal)
    assert result.reason is RefusalReason.NO_CITATIONS


def test_citation_outside_supplied_set_is_treated_as_uncited(passages):
    result = build_response("A confident claim [C9].", passages)
    assert isinstance(result, Refusal)
    assert result.reason is RefusalReason.NO_CITATIONS


def test_valid_citation_produces_answer(passages):
    result = build_response("Binary uses two digits [C1].", passages)
    assert isinstance(result, Answer)
    assert [p.id for p in result.cited] == ["a"]


def test_refusal_sentinel_is_honoured(passages):
    assert isinstance(build_response("NOT_IN_BOOK", passages), Refusal)


def test_empty_response_is_trouble_not_refusal(passages):
    """A provider returning 200 with empty content is a service failure.
    Calling it a refusal would tell the child the book lacks an answer it
    actually has (FR-020, SC-012). Observed live on a free tier."""
    result = build_response("", passages)
    assert isinstance(result, Trouble)
    assert not isinstance(result, Refusal)


def test_whitespace_only_response_is_trouble(passages):
    assert isinstance(build_response("   \n  ", passages), Trouble)


def test_extract_citations_dedupes_and_preserves_order():
    assert extract_citations("[C2] then [C1] then [C2] again", 3) == [2, 1]


def test_only_cited_passages_are_attached(passages):
    result = build_response("Claim one [C1]. Claim three [C3].", passages)
    assert isinstance(result, Answer)
    assert [p.id for p in result.cited] == ["a", "c"]


# --- image selection (FR-021, FR-022) --------------------------------------


def test_images_come_from_cited_passages_only(passages):
    result = build_response("Only the second one [C2].", passages)
    assert isinstance(result, Answer)
    assert result.page_images == ["pages/b.png"]


def test_images_are_capped_at_two():
    many = [passage(c) for c in "abcd"]
    result = build_response("[C1] [C2] [C3] [C4]", many)
    assert isinstance(result, Answer)
    assert len(result.page_images) == 2


def test_duplicate_pages_are_deduped():
    shared = [passage("a", ["pages/p084.png"]), passage("b", ["pages/p084.png"])]
    assert select_images(shared) == ["pages/p084.png"]


def test_passage_without_image_yields_text_only_answer():
    result = build_response("Grounded claim [C1].", [passage("a", [])])
    assert isinstance(result, Answer)
    assert result.page_images == []
    assert result.text  # the answer survives; only the picture is missing


# --- the rendering boundary (Principle I, FR-003, SC-007) ------------------


def test_trouble_detail_never_reaches_the_child():
    secret = (
        "Traceback (most recent call last): httpx HTTP 429 from openrouter "
        "model meta-llama/llama-3.3-70b-instruct:free"
    )
    view = render(Trouble(text="Something went wrong on my side, sorry!", detail=secret))
    lowered = view.text.lower()
    for leak in ("traceback", "429", "openrouter", "llama", "httpx"):
        assert leak not in lowered


def test_trouble_does_not_imply_the_book_lacks_the_answer():
    view = render(Trouble(text="x", detail=""))
    assert "book" not in view.text.lower()


def test_refusal_offers_a_way_forward(passages):
    view = render(Refusal(text="", reason=RefusalReason.BELOW_THRESHOLD))
    assert "?" in view.text  # invites another question
    assert "data" in view.text.lower()


def test_both_refusal_reasons_render_identically_to_the_child():
    a = render(Refusal(text="", reason=RefusalReason.BELOW_THRESHOLD)).text
    b = render(Refusal(text="", reason=RefusalReason.NO_CITATIONS)).text
    assert a == b  # the reason is reviewer-only


def test_citation_markers_become_numbered_footnotes():
    view = render(Answer(text="Binary uses two digits [C1].", cited=[passage("a")]))
    assert "[C1]" not in view.text
    assert "Binary uses two digits[1]." in view.text


def test_footnotes_follow_reading_order_not_retrieval_rank():
    # The model cited passage 3 first, so it is the child's source [1].
    text = "First claim [C3]. Second [C3] [C1]. Bogus [C9]."
    assert number_citations(text, [3, 1]) == "First claim[1]. Second[1][2]. Bogus."


def test_sources_line_up_with_footnotes_and_use_printed_pages():
    a = passage("a")
    a.page_labels = ["82"]  # PDF page 84 is printed as 82
    a.image_labels = ["82"]
    b = passage("b")
    b.pages, b.page_labels = [88, 89], ["86", "87"]
    response = build_response("From b [C2]. From a [C1].", [a, b])
    response.quotes = ["quote b", "quote a"]

    view = render(response)

    assert view.text == "From b[1]. From a[2]."
    assert [(s.number, s.pages, s.quote) for s in view.sources] == [
        (1, "Pages 86–87", "quote b"),
        (2, "Page 82", "quote a"),
    ]
    assert view.sources[0].section == "Binary code › b"
    assert [(i.path, i.label) for i in view.images][1] == ("pages/a.png", "Page 82")


def test_claims_are_grouped_by_the_marker_they_carry():
    claims = claims_by_citation("Bits are 0 or 1 [C1]. A byte is 8 bits [C2] [C1].")
    assert claims == {1: ["Bits are 0 or 1.", "A byte is 8 bits."], 2: ["A byte is 8 bits."]}


def test_quote_is_a_verbatim_sentence_from_the_passage(monkeypatch):
    import numpy as np

    from kidsrag.generate import evidence

    p = passage("a")
    p.text = (
        "People usually count in decimal. "
        "A byte is made of 8 bits and can store one character of text. "
        "Half a byte is a nibble."
    )

    # Fake embedder: the claim and sentence 2 point the same way.
    def fake_embed(texts):
        return np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, 1.0]])

    monkeypatch.setattr(evidence.embed, "embed_documents", fake_embed)
    [quote] = pick_quotes("A byte holds one letter [C1].", [p], [1])
    assert quote == "A byte is made of 8 bits and can store one character of text."
    assert quote in split_sentences(p.text)


def test_quote_falls_back_to_first_sentence_if_embedding_fails(monkeypatch):
    from kidsrag.generate import evidence

    def broken(texts):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(evidence.embed, "embed_documents", broken)
    p = passage("a")
    p.text = "Binary uses two digits, 0 and 1, for everything a computer does. More text."
    assert pick_quotes("Claim [C1].", [p], [1]) == [
        "Binary uses two digits, 0 and 1, for everything a computer does."
    ]


def test_strip_citations_tidies_spacing():
    assert strip_citations("A claim [C1]. Another [C2].") == "A claim. Another."


def test_render_rejects_unknown_types():
    with pytest.raises(TypeError):
        render({"text": "not a response type"})  # type: ignore[arg-type]
