"""The child-facing surface.

This is the ONLY module that produces text a child reads (Principle I, FR-003).

It accepts Answer, Refusal, or Trouble and nothing else. None of those types
can carry an exception, a status code, a model name, or a provider name, so
technical detail cannot reach the screen through this door. Trouble.detail
exists for reviewers and is deliberately never read here.

If you are tempted to format an error for the UI somewhere else: don't. Add a
case here instead, so "did technical text leak?" stays answerable by reading
one file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import Answer, Refusal, RefusalReason, Response, Trouble

CITATION_RE = re.compile(r"\[C\d+\]")
CITATION_NUM_RE = re.compile(r"\[C(\d+)\]")


@dataclass
class BookPage:
    """A page picture, captioned with the number printed in the book."""

    path: str
    label: str


@dataclass
class Source:
    """One 'where I found this' entry. `number` matches the [n] in the text."""

    number: int
    section: str
    pages: str
    quote: str
    image: str | None = None


@dataclass
class ChildView:
    """Everything the child sees, and nothing else."""

    text: str
    images: list[BookPage] = field(default_factory=list)
    kind: str = "answer"  # answer | refusal | trouble - for styling only
    sources: list[Source] = field(default_factory=list)


# --- Fixed copy -------------------------------------------------------------
# Consistent wording across questions (FR-002). Friendly, never blunt, and
# always offering a way forward.

REFUSAL_TEXT = (
    "I couldn't find anything about that in this part of the book.\n\n"
    "This part is all about **data** — things like binary code, secret codes, "
    "how pictures and sounds are stored, and how computers keep information "
    "in databases.\n\n"
    "Would you like to ask me about one of those?"
)

TROUBLE_TEXT = (
    "Something went wrong on my side, sorry about that!\n\n"
    "It's not a problem with your question. Please try asking again in a moment."
)


def strip_citations(text: str) -> str:
    """Remove [C1]-style markers from child-facing prose.

    The markers are how grounding is enforced, but they are noise to a child.
    The passages themselves stay visible to reviewers via the retrieval panel.
    """
    cleaned = CITATION_RE.sub("", text)
    cleaned = re.sub(r" +([.,;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def number_citations(text: str, order: list[int]) -> str:
    """Turn the model's [C3]-style markers into reading-order footnotes [1].

    `order` is the passage numbers in first-cited order, so the first source
    the child meets is [1] whatever retrieval rank it had. Markers outside
    `order` were already rejected by the grounding gate and are dropped.
    """
    number = {c: i for i, c in enumerate(order, start=1)}

    def swap(m: re.Match) -> str:
        n = number.get(int(m.group(1)))
        return f"[{n}]" if n else ""

    out = CITATION_NUM_RE.sub(swap, text)
    out = re.sub(r"(\[\d+\])(?:\s*\1)+", r"\1", out)  # [1] [1] -> [1]
    out = re.sub(r"(\[\d+\])\s+(?=\[\d+\])", r"\1", out)  # [1] [2] -> [1][2]
    out = re.sub(r" +(\[\d+\])", r"\1", out)  # 'digits [1].' -> 'digits[1].'
    out = re.sub(r" +([.,;:!?])", r"\1", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _answer_view(response: Answer) -> ChildView:
    label_for = {
        img: lbl
        for p in response.cited
        for img, lbl in zip(p.page_images, p.image_labels)
    }

    def caption(img: str) -> str:
        # No guessing from the file name: that is the PDF's numbering, which
        # differs from the printed one. Old artifacts get a neutral caption.
        return f"Page {label_for[img]}" if img in label_for else "Book page"

    # Answers built by build_response always carry markers; this keeps a
    # hand-built Answer (tests, notebook) readable too.
    markers = response.markers or list(range(1, len(response.cited) + 1))
    sources = [
        Source(
            number=i,
            section=p.section_display,
            pages=p.page_display,
            quote=response.quotes[i - 1] if i - 1 < len(response.quotes) else "",
            image=p.page_images[0] if p.page_images else None,
        )
        for i, p in enumerate(response.cited, start=1)
    ]
    return ChildView(
        text=number_citations(response.text, markers),
        images=[BookPage(img, caption(img)) for img in response.page_images],
        kind="answer",
        sources=sources,
    )


def render(response: Response) -> ChildView:
    """Turn a response into what the child sees.

    Note the absence of a generic `else` that formats an unknown object:
    anything not of the three known types is a programming error, and failing
    loudly here is safer than leaking a repr into a child's view.
    """
    if isinstance(response, Answer):
        return _answer_view(response)

    if isinstance(response, Refusal):
        # reason is reviewer-only; the child sees one consistent message.
        assert isinstance(response.reason, RefusalReason)
        return ChildView(text=REFUSAL_TEXT, images=[], kind="refusal")

    if isinstance(response, Trouble):
        # response.detail is deliberately NOT read.
        return ChildView(text=TROUBLE_TEXT, images=[], kind="trouble")

    raise TypeError(f"render() cannot display {type(response).__name__}")
