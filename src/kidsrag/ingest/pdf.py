"""PDF access and chapter resolution.

The chapter is resolved from the document's own table of contents by title.
No page numbers are hardcoded anywhere - that is what makes the pipeline work
on other chapters without edits (Principle V, FR-005).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf  # NOT `fitz`: that entry point is deprecated in PyMuPDF 1.26+

from ..errors import AmbiguousChapter, ChapterNotFound
from ..models import Chapter

# TOC levels as this book uses them: 2 = chapter, 3 = topic spread.
CHAPTER_LEVEL = 2
SPREAD_LEVEL = 3


def open_document(pdf_path: str | Path) -> pymupdf.Document:
    return pymupdf.open(str(pdf_path))


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def list_chapters(doc: pymupdf.Document) -> list[tuple[str, int]]:
    """Every top-level chapter as (title, 1-based start page)."""
    return [(t[1].strip(), t[2]) for t in doc.get_toc() if t[0] == CHAPTER_LEVEL]


def _strip_leading_number(title: str) -> str:
    """'5 Data' -> 'Data'. The brief and the book disagree on numbering, so we
    match on the name and ignore whatever number precedes it."""
    parts = title.split(None, 1)
    if len(parts) == 2 and parts[0].rstrip(".").isdigit():
        return parts[1].strip()
    return title.strip()


def resolve_chapter(doc: pymupdf.Document, title: str) -> Chapter:
    """Resolve a chapter by title, case-insensitively.

    Raises ChapterNotFound (listing what is available) or AmbiguousChapter.
    """
    chapters = list_chapters(doc)
    wanted = title.strip().lower()

    matches = [
        (i, name, page)
        for i, (name, page) in enumerate(chapters)
        if _strip_leading_number(name).lower() == wanted or name.lower() == wanted
    ]

    if not matches:
        # Fall back to substring matching before giving up.
        matches = [
            (i, name, page)
            for i, (name, page) in enumerate(chapters)
            if wanted in name.lower()
        ]

    if not matches:
        raise ChapterNotFound(title, [name for name, _ in chapters])
    if len(matches) > 1:
        raise AmbiguousChapter(title, [m[1] for m in matches])

    idx, name, start_page = matches[0]
    if idx + 1 < len(chapters):
        end_page = chapters[idx + 1][1] - 1
    else:
        end_page = doc.page_count

    if end_page < start_page:
        raise ChapterNotFound(title, [n for n, _ in chapters])

    spreads = [
        t[1].strip()
        for t in doc.get_toc()
        if t[0] == SPREAD_LEVEL and start_page <= t[2] <= end_page
    ]

    return Chapter(
        title=_strip_leading_number(name),
        start_page=start_page,
        end_page=end_page,
        spread_titles=spreads,
    )


def spread_starts(doc: pymupdf.Document, chapter: Chapter) -> list[tuple[str, int]]:
    """Topic spreads in this chapter as (title, 1-based start page).

    Titles in the TOC carry a trailing book-page number ('Binary code 82');
    it is stripped so the title reads cleanly in a heading path.
    """
    out: list[tuple[str, int]] = []
    for t in doc.get_toc():
        if t[0] != SPREAD_LEVEL:
            continue
        if not (chapter.start_page <= t[2] <= chapter.end_page):
            continue
        name = t[1].strip()
        parts = name.rsplit(None, 1)
        if len(parts) == 2 and parts[1].isdigit():
            name = parts[0].strip()
        out.append((name, t[2]))
    return out
