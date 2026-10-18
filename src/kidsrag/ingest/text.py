"""Text cleanup, spread grouping, and heading-based chunking.

A passage is one section of a topic spread, under one heading - the book's
own unit of explanation. Fixed-size windows scramble these pages, because a
spread interleaves prose, a SEE ALSO sidebar, an IN DEPTH box and diagram
labels (research.md section 4).

Work happens at LINE level: a section heading shares its text block with the
prose beneath it, so block-level classification never sees the heading.

Diagram labels are kept on the passage but OUT of its prose: they are
fragments like '1x128 + 1x64' that pollute a sentence embedding while
remaining valuable for lexical matching (FR-010).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

from ..models import Chapter, Passage, slugify
from .pdf import spread_starts
from .roles import Role, RoleTable, derive_role_table

HEADER_BAND = 48.0  # page is ~660pt tall
FOOTER_BAND = 636.0

SEE_ALSO_RE = re.compile(r"^\s*SEE\s+ALSO\b", re.IGNORECASE)
XREF_RE = re.compile(r"\d{2,3}\s*[-–—]\s*\d{2,3}")
# Letterspaced running head, with optional folio. Kerning means PyMuPDF
# reports these with irregular gaps - 'D ATA', not 'D A T A' - so the groups
# must allow runs of letters, not just single characters. This test only runs
# for text already known to sit in the header/footer band, so an all-caps
# phrase in the body is never caught by it.
RUNNING_HEAD_RE = re.compile(r"^[A-Z0-9]+(\s+[A-Z0-9]+)+\s*$")
CALLOUT_MARK_RE = re.compile(r"^[\s▷▽◁△-]+")
# A heading is short; anything long at heading size is a stray.
MAX_HEADING_CHARS = 70


@dataclass
class Line:
    text: str
    role: Role
    bbox: tuple[float, float, float, float]
    page: int


# Letterspaced category badges on sidebar boxes: 'I N D E P T H',
# 'R E A L  W O R L D', 'T O P  T E C H'. They sit inside the prose column,
# so the margin-band furniture test never sees them.
#
# Five or more single letters is the discriminator. It deliberately spares
# genuine short runs the book uses as content - the cipher alphabet 'A B C'
# and truth-table headers like 'A B A AND B' are three letters or fewer
# between words, and survive.
BOX_BADGE_RE = re.compile(r"\b(?:[A-Z]\s){4,}[A-Z]\b")


def clean_text(text: str) -> str:
    """Rejoin hyphenated line wraps, drop box badges, normalise whitespace.

    'digitiza-\\ntion' -> 'digitization'
    """
    text = text.replace("­", "")  # soft hyphen
    text = re.sub(r"(\w)[-‐]\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = BOX_BADGE_RE.sub(" ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def is_furniture(text: str, bbox: tuple[float, float, float, float]) -> bool:
    """Folios and running heads - never part of a passage (FR-009)."""
    s = text.strip()
    if not s:
        return True
    if re.fullmatch(r"\d{1,3}", s):
        return True
    in_margin = bbox[3] < HEADER_BAND or bbox[1] > FOOTER_BAND
    if in_margin:
        # 'D ATA 82' -> drop the folio, then test for a letterspaced head.
        core = re.sub(r"\s*\d{1,3}\s*$", "", s).strip()
        if RUNNING_HEAD_RE.match(core) or core.isdigit():
            return True
    return False


def extract_lines(page: pymupdf.Page, table: RoleTable, page_no: int) -> list[Line]:
    """Classify every line on the page by its dominant span size."""
    out: list[Line] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            spans = line["spans"]
            if not spans:
                continue
            raw = "".join(sp["text"] for sp in spans)
            text = clean_text(raw)
            bbox = tuple(line["bbox"])
            if not text or is_furniture(text, bbox):
                continue
            # Dominant size = the size covering the most characters on the line.
            tally: dict[float, int] = {}
            for sp in spans:
                tally[round(sp["size"], 1)] = tally.get(round(sp["size"], 1), 0) + len(
                    sp["text"]
                )
            dominant = max(tally.items(), key=lambda kv: kv[1])[0]
            role = table.role_for_size(dominant)
            out.append(Line(text=text, role=role, bbox=bbox, page=page_no))

    # Reading order: column first (this book uses a 2-column grid), then top
    # to bottom. Sorting purely by y interleaves the two columns.
    page_mid = page.rect.width / 2.0
    out.sort(key=lambda ln: (0 if ln.bbox[0] < page_mid else 1, ln.bbox[1], ln.bbox[0]))
    return out


def _merge_wrapped(lines: list[Line]) -> list[Line]:
    """Join consecutive lines of the same role into paragraphs."""
    merged: list[Line] = []
    for ln in lines:
        if (
            merged
            and merged[-1].role is ln.role
            and ln.role in (Role.BODY, Role.STANDFIRST, Role.LABEL)
            and ln.page == merged[-1].page
        ):
            prev = merged[-1]
            joined = clean_text(f"{prev.text}\n{ln.text}")
            merged[-1] = Line(
                text=joined,
                role=prev.role,
                bbox=(
                    min(prev.bbox[0], ln.bbox[0]),
                    min(prev.bbox[1], ln.bbox[1]),
                    max(prev.bbox[2], ln.bbox[2]),
                    max(prev.bbox[3], ln.bbox[3]),
                ),
                page=prev.page,
            )
        else:
            merged.append(ln)
    return merged


@dataclass
class _Builder:
    chapter: str
    spread: str
    heading: str
    pages: set[int] = field(default_factory=set)
    body: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)
    bbox: list[float] | None = None

    def add_bbox(self, b: tuple[float, float, float, float]) -> None:
        if self.bbox is None:
            self.bbox = list(b)
        else:
            self.bbox = [
                min(self.bbox[0], b[0]),
                min(self.bbox[1], b[1]),
                max(self.bbox[2], b[2]),
                max(self.bbox[3], b[3]),
            ]

    def finish(self, page_image_for: dict[int, str]) -> Passage | None:
        text = " ".join(t for t in self.body if t).strip()
        if len(text) < 40:
            return None  # Empty or stub passages are dropped, never indexed.
        pages = sorted(self.pages)
        pid = "-".join(
            filter(
                None,
                [slugify(self.chapter), slugify(self.spread), slugify(self.heading)],
            )
        )
        return Passage(
            id=pid,
            heading_path=[
                p for p in (self.chapter, self.spread, self.heading) if p
            ],
            text=text,
            labels=" ".join(self.labels).strip(),
            see_also=self.see_also,
            pages=pages,
            page_images=[page_image_for[p] for p in pages if p in page_image_for],
            bbox=tuple(self.bbox) if self.bbox else None,
        )


def _is_section_heading(ln: Line) -> bool:
    if ln.role is not Role.HEADING:
        return False
    return 0 < len(ln.text) <= MAX_HEADING_CHARS


# Callout bodies ('> Binary translators: Humans find binary numbers...') are
# set at the same size as diagram labels, so size alone cannot separate them.
# Prose is long and punctuated; a diagram label is a short fragment.
MIN_CALLOUT_PROSE = 80


def _is_callout_prose(text: str) -> bool:
    return len(text) >= MIN_CALLOUT_PROSE and bool(re.search(r"[.!?](\s|$)", text))


def build_passages(
    doc: pymupdf.Document,
    chapter: Chapter,
    page_image_for: dict[int, str] | None = None,
    table: RoleTable | None = None,
) -> list[Passage]:
    """Chunk a chapter into passages following spread -> heading structure."""
    page_image_for = page_image_for or {}
    spreads = spread_starts(doc, chapter)
    if not spreads:
        return []

    if table is None:
        table = derive_role_table(doc, spreads[0][1], chapter.end_page)

    bounds: list[tuple[str, int, int]] = []
    for i, (title, start) in enumerate(spreads):
        end = spreads[i + 1][1] - 1 if i + 1 < len(spreads) else chapter.end_page
        bounds.append((title, start, end))

    passages: list[Passage] = []
    for spread_title, start, end in bounds:
        current = _Builder(chapter.title, spread_title, "")

        for pno in range(start, end + 1):
            lines = _merge_wrapped(extract_lines(doc[pno - 1], table, pno))
            for ln in lines:
                if SEE_ALSO_RE.match(ln.text) or (
                    XREF_RE.search(ln.text) and len(ln.text) < 220
                ):
                    current.see_also.append(ln.text)
                    continue

                if ln.role is Role.TITLE:
                    continue  # The spread title already heads the passage.

                if _is_section_heading(ln):
                    done = current.finish(page_image_for)
                    if done:
                        passages.append(done)
                    heading = CALLOUT_MARK_RE.sub("", ln.text).strip()
                    current = _Builder(chapter.title, spread_title, heading)
                    current.pages.add(ln.page)
                    current.add_bbox(ln.bbox)
                    continue

                cleaned = CALLOUT_MARK_RE.sub("", ln.text).strip()
                if ln.role in (Role.BODY, Role.STANDFIRST) or _is_callout_prose(
                    cleaned
                ):
                    current.body.append(cleaned)
                else:
                    current.labels.append(ln.text)
                current.pages.add(ln.page)
                current.add_bbox(ln.bbox)

        done = current.finish(page_image_for)
        if done:
            passages.append(done)

    return _dedupe_ids(passages)


def _dedupe_ids(passages: list[Passage]) -> list[Passage]:
    """Passage ids must be unique within a chapter (data-model.md)."""
    seen: dict[str, int] = {}
    for p in passages:
        if p.id in seen:
            seen[p.id] += 1
            p.id = f"{p.id}-{seen[p.id]}"
        else:
            seen[p.id] = 1
    return passages
