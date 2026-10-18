"""Text cleanup and chunking helpers (FR-009, FR-010)."""

from __future__ import annotations

from kidsrag.index.retrieve import rrf_fuse
from kidsrag.ingest.text import clean_text, is_furniture
from kidsrag.models import Passage, slugify


# --- hyphenated line wraps -------------------------------------------------


def test_rejoins_hyphenated_wrap():
    assert clean_text("digitiza-\ntion") == "digitization"


def test_keeps_real_hyphens():
    assert clean_text("solid-state devices") == "solid-state devices"


def test_collapses_newlines_into_spaces():
    assert clean_text("one\ntwo\nthree") == "one two three"


def test_strips_soft_hyphens():
    assert clean_text("digiti­zation") == "digitization"


# --- page furniture (FR-009) -----------------------------------------------


def test_bare_folio_is_furniture():
    assert is_furniture("82", (36, 12, 60, 30))


def test_letterspaced_running_head_is_furniture():
    assert is_furniture("D ATA", (80, 12, 200, 30))


def test_running_head_with_folio_is_furniture():
    assert is_furniture("B I N A R Y  C O D E 83", (80, 12, 300, 30))


def test_body_text_in_the_margin_is_not_furniture():
    assert not is_furniture("Data is the name given to information", (36, 12, 400, 30))


def test_body_text_mid_page_is_not_furniture():
    assert not is_furniture("Binary code", (36, 300, 200, 320))


# --- passage fields --------------------------------------------------------


def test_labels_are_excluded_from_embed_text_but_present_for_search():
    p = Passage(
        id="x",
        heading_path=["Data", "Binary code", "Binary to decimal"],
        text="People usually count using the decimal system.",
        labels="1x128 + 1x64 11000101",
    )
    assert "11000101" not in p.embed_text()
    assert "11000101" in p.search_text()
    assert "Binary to decimal" in p.embed_text()


def test_slugify():
    assert slugify("Bits and digitization") == "bits-and-digitization"
    assert slugify("Why 0 and 1?") == "why-0-and-1"


# --- RRF (research.md section 7) -------------------------------------------


def test_rrf_rewards_agreement_between_retrievers():
    dense = ["a", "b", "c"]
    sparse = ["b", "a", "c"]
    fused = dict(rrf_fuse([dense, sparse], k=60))
    # 'a' and 'b' each appear at ranks 1 and 2, so they tie above 'c'.
    assert fused["a"] == fused["b"] > fused["c"]


def test_rrf_scores_descend_in_returned_order():
    ordered = rrf_fuse([["a", "b", "c"], ["a", "c", "b"]], k=60)
    scores = [s for _, s in ordered]
    assert scores == sorted(scores, reverse=True)


def test_rrf_top_k_limits_results():
    assert len(rrf_fuse([["a", "b", "c", "d"]], k=60, top_k=2)) == 2


def test_rrf_single_retriever_preserves_its_order():
    ordered = [i for i, _ in rrf_fuse([["x", "y", "z"]], k=60)]
    assert ordered == ["x", "y", "z"]


# --- letterspaced sidebar box badges ---------------------------------------


def test_strips_in_depth_badge():
    assert "I N D E P T H" not in clean_text("lost. I N D E P T H A history of data")


def test_strips_real_world_badge():
    assert "R E A L" not in clean_text("off. R E A L W O R L D Braille is")


def test_preserves_short_letter_runs_used_as_content():
    # The encryption spread genuinely prints a cipher alphabet.
    assert "A B C" in clean_text("plaintext letters A B C Z a cipher")


def test_preserves_truth_table_headers():
    assert "A AND B" in clean_text("Inclusive-OR. A B A AND B next")
