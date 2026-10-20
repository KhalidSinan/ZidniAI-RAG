"""Entity and response dataclasses.

See specs/001-data-chapter-rag/data-model.md.

The three response types at the bottom are what make Principle I structural:
render.py accepts only these, and none of them can carry an exception, a
status code, or a provider name into the child's view.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


def slugify(text: str) -> str:
    """Lowercase, hyphenated, filesystem- and id-safe."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return s.strip("-")


@dataclass(frozen=True)
class Chapter:
    title: str
    start_page: int  # 1-based, inclusive
    end_page: int  # 1-based, inclusive
    spread_titles: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slugify(self.title)

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page + 1

    @property
    def spread_count(self) -> int:
        return len(self.spread_titles)


@dataclass
class Spread:
    """A two-page topic unit - the book's own organising structure."""

    title: str
    pages: list[int]


@dataclass
class Passage:
    """The retrievable unit: one section of a spread, under one heading."""

    id: str
    heading_path: list[str]
    text: str
    labels: str = ""
    see_also: list[str] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)
    page_images: list[str] = field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None
    # The page numbers PRINTED in the book, parallel to `pages` and
    # `page_images`. PDF page 82 is printed as page 80; a child turning to a
    # cited page needs the printed one.
    page_labels: list[str] = field(default_factory=list)
    image_labels: list[str] = field(default_factory=list)

    @property
    def heading_display(self) -> str:
        return " › ".join(self.heading_path)

    @property
    def section_display(self) -> str:
        """Heading path without the chapter name, which every passage shares."""
        return " › ".join(self.heading_path[1:]) or self.heading_display

    @property
    def page_display(self) -> str:
        """'Page 80' or 'Pages 86-87', in the book's own numbering."""
        labels = self.page_labels or [str(p) for p in self.pages]
        if not labels:
            return ""
        if len(labels) == 1:
            return f"Page {labels[0]}"
        return f"Pages {labels[0]}–{labels[-1]}"

    def search_text(self) -> str:
        """What BM25 indexes: prose plus labels plus heading path."""
        return " ".join([self.heading_display, self.text, self.labels]).strip()

    def embed_text(self) -> str:
        """What the dense retriever embeds: heading path plus prose.

        Labels are deliberately excluded - they are fragments like
        '1x128 + 1x64' that pollute a sentence embedding while remaining
        valuable for lexical matching.
        """
        return f"{self.heading_display}\n{self.text}".strip()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "heading_path": self.heading_path,
            "text": self.text,
            "labels": self.labels,
            "see_also": self.see_also,
            "pages": self.pages,
            "page_images": self.page_images,
            "bbox": list(self.bbox) if self.bbox else None,
            "page_labels": self.page_labels,
            "image_labels": self.image_labels,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Passage:
        bbox = d.get("bbox")
        return cls(
            id=d["id"],
            heading_path=d["heading_path"],
            text=d["text"],
            labels=d.get("labels", ""),
            see_also=d.get("see_also", []),
            pages=d.get("pages", []),
            page_images=d.get("page_images", []),
            bbox=tuple(bbox) if bbox else None,
            page_labels=d.get("page_labels", []),
            image_labels=d.get("image_labels", []),
        )


@dataclass(frozen=True)
class PageImage:
    page: int
    path: str
    dpi: int = 150


@dataclass
class Manifest:
    pdf_sha256: str
    chapter_title: str
    pipeline_version: str
    cache_key: str
    page_range: tuple[int, int]
    passage_count: int
    embedding_model: str
    created_at: str

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["page_range"] = list(self.page_range)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Manifest:
        d = dict(d)
        d["page_range"] = tuple(d["page_range"])
        return cls(**d)


@dataclass
class RetrievalResult:
    passages: list[Passage]
    scores: list[float]
    dense_ranks: dict[str, int] = field(default_factory=dict)
    sparse_ranks: dict[str, int] = field(default_factory=dict)
    passed_gate: bool = False
    # Absolute relevance of the best match. This, NOT the fused score, is what
    # the refusal gate tests - see Retriever.retrieve().
    max_cosine: float = 0.0
    # Cross-encoder scores by passage id, when the reranker is enabled. They
    # decide the ORDER only; the gate still uses max_cosine.
    rerank_scores: dict[str, float] = field(default_factory=dict)

    @property
    def top_score(self) -> float:
        """Top fused (RRF) score. Good for ordering, useless for gating."""
        return self.scores[0] if self.scores else 0.0


# ---------------------------------------------------------------------------
# Response types. render.py accepts these three and nothing else.
# ---------------------------------------------------------------------------


class RefusalReason(str, Enum):
    BELOW_THRESHOLD = "below_threshold"
    NO_CITATIONS = "no_citations"


@dataclass
class Answer:
    """A grounded answer. `cited` is never empty - see generate/answer.py."""

    text: str
    cited: list[Passage]
    page_images: list[str] = field(default_factory=list)
    # The validated [C#] numbers, parallel to `cited`.
    markers: list[int] = field(default_factory=list)
    # One supporting sentence from each cited passage, parallel to `cited`.
    quotes: list[str] = field(default_factory=list)


@dataclass
class Refusal:
    """The chapter does not cover this. Not a failure."""

    text: str
    reason: RefusalReason


@dataclass
class Trouble:
    """The system failed. `detail` is reviewer-only and never rendered."""

    text: str
    detail: str = ""


Response = Answer | Refusal | Trouble
