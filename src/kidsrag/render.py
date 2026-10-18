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


@dataclass
class ChildView:
    """Everything the child sees, and nothing else."""

    text: str
    images: list[str] = field(default_factory=list)
    kind: str = "answer"  # answer | refusal | trouble - for styling only


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


def render(response: Response) -> ChildView:
    """Turn a response into what the child sees.

    Note the absence of a generic `else` that formats an unknown object:
    anything not of the three known types is a programming error, and failing
    loudly here is safer than leaking a repr into a child's view.
    """
    if isinstance(response, Answer):
        return ChildView(
            text=strip_citations(response.text),
            images=list(response.page_images),
            kind="answer",
        )

    if isinstance(response, Refusal):
        # reason is reviewer-only; the child sees one consistent message.
        assert isinstance(response.reason, RefusalReason)
        return ChildView(text=REFUSAL_TEXT, images=[], kind="refusal")

    if isinstance(response, Trouble):
        # response.detail is deliberately NOT read.
        return ChildView(text=TROUBLE_TEXT, images=[], kind="trouble")

    raise TypeError(f"render() cannot display {type(response).__name__}")
