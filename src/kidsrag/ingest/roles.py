"""Derive the book's typographic grammar, then classify text by role.

This book is laid out on a strict design system, so (font, size) is a near
perfect role classifier. The table is DERIVED from the chapter being
processed, never hardcoded - that is what lets the same code work on another
chapter (Principle V).

Two things this module learned the hard way, from the actual PDF:

1. Classification must happen at LINE level, not block level. A section
   heading shares its text block with the body prose beneath it, so a
   block-level role (whichever role has the most characters) always reports
   "body" and the heading is never seen.

2. Anchors must be matched EXACTLY, not banded. Diagram numerals are set at
   18-19.5pt - larger than body, smaller than the spread title - so any
   "bigger than body means heading" rule promotes '11000101' to a heading.
   Only type at the derived body/standfirst/heading/title sizes counts as
   prose structure; everything else is a label.

Measured reference for the Data chapter (research.md section 4):

    13,316 ch  MyriadPro-Light 9.0        body prose
     6,504 ch  MyriadPro-Regular 8.0      diagram labels
     5,427 ch  MyriadPro-LightSemiCn 9.0  sidebar body
     1,500 ch  MyriadPro-Semibold 10.5    spread standfirst
       787 ch  MyriadPro-Semibold(Cond) 14.0  section heading
       119 ch  MyriadPro-Regular 32.0     spread title
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum

import pymupdf


class Role(str, Enum):
    TITLE = "title"  # spread title, largest recurring type
    HEADING = "heading"  # section heading - opens a new passage
    STANDFIRST = "standfirst"  # the bold intro under a spread title
    BODY = "body"  # body prose - the substance of a passage
    LABEL = "label"  # diagram labels, captions, callout text


Style = tuple[str, float]

MIN_STYLE_VOLUME = 100  # chars; keeps one-off display type out of the anchors
SIZE_TOL = 0.35  # pt; anchors are matched exactly, within rounding noise


@dataclass
class RoleTable:
    body_size: float
    standfirst_size: float
    heading_size: float
    title_size: float

    def role_for_size(self, size: float) -> Role:
        """Exact anchor matching. Anything off-anchor is a label."""
        s = round(size, 1)
        if abs(s - self.title_size) <= SIZE_TOL:
            return Role.TITLE
        if abs(s - self.heading_size) <= SIZE_TOL:
            return Role.HEADING
        if abs(s - self.standfirst_size) <= SIZE_TOL:
            return Role.STANDFIRST
        if abs(s - self.body_size) <= SIZE_TOL:
            return Role.BODY
        if s > self.title_size:
            return Role.TITLE  # chapter-opener display type
        return Role.LABEL

    def describe(self) -> str:
        return (
            f"body={self.body_size} standfirst={self.standfirst_size} "
            f"heading={self.heading_size} title={self.title_size}"
        )


def iter_spans(page: pymupdf.Page):
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                yield span


def _volume_at(volume: Counter[Style], size: float) -> int:
    return sum(c for (_f, s), c in volume.items() if s == size)


def derive_role_table(
    doc: pymupdf.Document, start_page: int, end_page: int
) -> RoleTable:
    """Build the size anchors from the chapter's own typography.

    body       = the single style carrying the most characters
    standfirst = the highest-volume size between body and heading
    heading    = the largest substantial size below the title
    title      = the largest substantial size overall
    """
    volume: Counter[Style] = Counter()
    for pno in range(start_page - 1, end_page):
        for span in iter_spans(doc[pno]):
            volume[(span["font"], round(span["size"], 1))] += len(span["text"])

    if not volume:
        return RoleTable(9.0, 10.5, 14.0, 32.0)

    body_size = volume.most_common(1)[0][0][1]

    substantial = sorted(
        {
            s
            for (_f, s) in volume
            if s > body_size and _volume_at(volume, s) >= MIN_STYLE_VOLUME
        },
        reverse=True,
    )
    title_size = substantial[0] if substantial else body_size + 20.0
    below_title = [s for s in substantial if s < title_size]
    heading_size = below_title[0] if below_title else body_size + 5.0

    # Standfirst: the highest-volume size strictly between body and heading.
    between = [s for s in substantial if body_size < s < heading_size]
    standfirst_size = (
        max(between, key=lambda s: _volume_at(volume, s))
        if between
        else (body_size + heading_size) / 2
    )

    return RoleTable(
        body_size=body_size,
        standfirst_size=standfirst_size,
        heading_size=heading_size,
        title_size=title_size,
    )
