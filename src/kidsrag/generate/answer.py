"""Answer assembly: the second grounding gate, and image selection.

The citation check here is plain string matching. It holds regardless of
whether the model followed its instructions, which is exactly what
Principle II requires: at least one grounding check that does not depend on
model compliance (FR-018).
"""

from __future__ import annotations

import re

from ..config import Config
from ..errors import UpstreamError
from ..models import (
    Answer,
    Passage,
    Refusal,
    RefusalReason,
    Response,
    RetrievalResult,
    Trouble,
)
from ..render import REFUSAL_TEXT, TROUBLE_TEXT
from . import llm
from .prompt import build_messages

CITATION_RE = re.compile(r"\[C(\d+)\]")
REFUSAL_SENTINEL = "NOT_IN_BOOK"
MAX_IMAGES = 2


def extract_citations(text: str, n_passages: int) -> list[int]:
    """Valid 1-based citation indices, in order of first appearance.

    Markers pointing outside the supplied set are discarded - a model that
    invents [C9] against five passages has cited nothing.
    """
    seen: list[int] = []
    for match in CITATION_RE.finditer(text):
        idx = int(match.group(1))
        if 1 <= idx <= n_passages and idx not in seen:
            seen.append(idx)
    return seen


def select_images(cited: list[Passage]) -> list[str]:
    """Page images from CITED passages only, deduped, capped.

    Merely-retrieved pages are not shown: that would present a page the
    answer did not use as if it were the source (FR-021).
    """
    out: list[str] = []
    for p in cited:
        for path in p.page_images:
            if path not in out:
                out.append(path)
    return out[:MAX_IMAGES]


def build_response(raw: str, passages: list[Passage]) -> Response:
    """Turn raw model text into a validated response."""
    text = (raw or "").strip()

    # An EMPTY response is a service failure, not a statement about the book.
    # Free-tier providers return 200 with empty content under load, and
    # calling that a refusal would tell the child the book lacks an answer it
    # actually contains - exactly what FR-020 and SC-012 forbid.
    if not text:
        return Trouble(text=TROUBLE_TEXT, detail="Model returned an empty response")

    if REFUSAL_SENTINEL in text.upper():
        return Refusal(text=REFUSAL_TEXT, reason=RefusalReason.NO_CITATIONS)

    indices = extract_citations(text, len(passages))
    if not indices:
        # The model answered without grounding it. Discard the answer.
        return Refusal(text=REFUSAL_TEXT, reason=RefusalReason.NO_CITATIONS)

    cited = [passages[i - 1] for i in indices]
    return Answer(text=text, cited=cited, page_images=select_images(cited))


def answer_question(
    cfg: Config, question: str, retrieval: RetrievalResult
) -> Response:
    """Full answering path, including both grounding gates."""
    # Gate 1: refuse before spending a network call (research.md section 8).
    if not retrieval.passed_gate or not retrieval.passages:
        return Refusal(text=REFUSAL_TEXT, reason=RefusalReason.BELOW_THRESHOLD)

    messages = build_messages(question, retrieval.passages)

    try:
        raw = llm.complete(cfg, messages)
    except UpstreamError as exc:
        # Never a Refusal: a broken service is not a silent book (SC-012).
        return Trouble(text=TROUBLE_TEXT, detail=str(exc))

    # Gate 2: deterministic, model-independent.
    return build_response(raw, retrieval.passages)
