"""Chapter resolution and the one-value chapter switch (FR-012, SC-008).

These run against the real PDF. They are skipped if it is absent, so the
suite still passes on a checkout without the book.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kidsrag.config import load_config
from kidsrag.errors import ChapterNotFound
from kidsrag.ingest.pdf import open_document, resolve_chapter, spread_starts

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config.yaml"


@pytest.fixture(scope="module")
def doc():
    if not CONFIG.exists():
        pytest.skip("config.yaml not present")
    cfg = load_config(CONFIG)
    if not cfg.pdf_path.exists():
        pytest.skip("source PDF not present")
    return open_document(cfg.pdf_path)


def test_data_chapter_resolves_to_its_printed_range(doc):
    chapter = resolve_chapter(doc, "Data")
    assert (chapter.start_page, chapter.end_page) == (80, 97)
    assert chapter.spread_count == 8
    assert chapter.slug == "data"


def test_data_chapter_spreads_match_the_book(doc):
    titles = [t for t, _ in spread_starts(doc, resolve_chapter(doc, "Data"))]
    assert titles == [
        "Bits and digitization",
        "Binary code",
        "ASCII and unicode",
        "Logic gates",
        "Databases",
        "Encoding images",
        "Encoding audio and video",
        "Encryption",
    ]


def test_chapter_lookup_is_case_insensitive(doc):
    assert resolve_chapter(doc, "data").start_page == 80
    assert resolve_chapter(doc, "DATA").start_page == 80


def test_leading_chapter_number_is_ignored(doc):
    """The brief says 'chapter #6 (Data)'; the PDF says '5 Data'. The title
    is authoritative, and the number in the TOC entry must not interfere."""
    assert resolve_chapter(doc, "Data").title == "Data"


def test_switching_chapter_changes_range_and_directory(doc):
    data = resolve_chapter(doc, "Data")
    other = resolve_chapter(doc, "Programming techniques")

    assert (other.start_page, other.end_page) == (98, 117)
    assert other.slug != data.slug
    # Ranges must not overlap, or artifacts would mix.
    assert other.start_page > data.end_page


def test_unknown_chapter_lists_what_is_available(doc):
    with pytest.raises(ChapterNotFound) as exc:
        resolve_chapter(doc, "Quantum Gardening")
    message = str(exc.value)
    assert "Quantum Gardening" in message
    assert "Data" in message  # tells the user what they could have asked for


def test_role_table_generalises_to_an_untuned_chapter(doc):
    """The same derivation must produce the same anchors on a chapter it was
    never tuned against - the core evidence for chapter reproducibility."""
    from kidsrag.ingest.roles import derive_role_table

    def anchors(name: str) -> str:
        ch = resolve_chapter(doc, name)
        start = spread_starts(doc, ch)[0][1]
        return derive_role_table(doc, start, ch.end_page).describe()

    assert anchors("Data") == anchors("Programming techniques")


def test_chapter_switch_needs_only_the_title(tmp_path, doc):
    """Changing chapter.title alone must retarget everything."""
    import yaml

    base = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    base["pdf"]["path"] = str(load_config(CONFIG).pdf_path)

    def write(title: str) -> Path:
        base["chapter"]["title"] = title
        p = tmp_path / f"{title.replace(' ', '_')}.yaml"
        p.write_text(yaml.safe_dump(base), encoding="utf-8")
        return p

    a = load_config(write("Data"))
    b = load_config(write("Programming techniques"))

    assert a.chapter_dir != b.chapter_dir
    assert a.chapter_dir.name == "data"
    assert b.chapter_dir.name == "programming-techniques"
    # Everything else is untouched.
    assert a.retrieval == b.retrieval
    assert a.generation == b.generation
    assert a.pdf_path == b.pdf_path
