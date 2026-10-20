"""Supporting quotes: which sentence of a cited passage backs the answer.

A citation that says only 'page 84' makes the child (or reviewer) reread the
whole page. For each cited passage we pick the one sentence most similar to
the answer sentences that cite it, and show it verbatim - it is the book's
own text, so it cannot introduce anything the book does not say.

Similarity uses the same local embedder as retrieval. If that fails, the
passage's opening sentence is used: a weaker quote, never a missing answer.
"""

from __future__ import annotations

import logging
import re

import numpy as np

from ..index import embed
from ..models import Passage

log = logging.getLogger(__name__)

# Split after . ! ? when followed by a space and a capital/digit/quote.
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])")
MARKER_RE = re.compile(r"\[C(\d+)\]")
MAX_QUOTE_CHARS = 240
MIN_QUOTE_CHARS = 60


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]


def claims_by_citation(answer: str) -> dict[int, list[str]]:
    """Answer sentences grouped by the [C#] markers they carry, markers removed."""
    out: dict[int, list[str]] = {}
    for sentence in split_sentences(answer):
        clean = re.sub(r"\s+([.,;:!?])", r"\1", MARKER_RE.sub("", sentence)).strip()
        for n in {int(m) for m in MARKER_RE.findall(sentence)}:
            out.setdefault(n, []).append(clean)
    return out


def _trim(sentences: list[str], best: int) -> str:
    """The best sentence, plus the next one if the best is a fragment."""
    quote = sentences[best]
    if len(quote) < MIN_QUOTE_CHARS and best + 1 < len(sentences):
        quote = f"{quote} {sentences[best + 1]}"
    if len(quote) > MAX_QUOTE_CHARS:
        quote = quote[:MAX_QUOTE_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return quote


def pick_quotes(answer: str, cited: list[Passage], indices: list[int]) -> list[str]:
    """One quote per cited passage. `indices` are the 1-based [C#] numbers."""
    claims = claims_by_citation(answer)
    quotes: list[str] = []
    for passage, n in zip(cited, indices):
        sentences = split_sentences(passage.text)
        if not sentences:
            quotes.append("")
            continue
        best = 0
        claim = " ".join(claims.get(n, []))
        if claim and len(sentences) > 1:
            try:
                vecs = embed.embed_documents([claim, *sentences])
                best = int(np.argmax(vecs[1:] @ vecs[0]))
            except Exception as exc:  # noqa: BLE001 - a quote is optional
                log.warning("Quote selection fell back to first sentence: %s", exc)
        quotes.append(_trim(sentences, best))
    return quotes
