"""Hybrid retrieval: dense + BM25, fused with Reciprocal Rank Fusion,
optionally reordered by a cross-encoder.

The two retrievers fail in complementary ways on this corpus. Children ask
plainly ('how do computers remember pictures?') where only semantics match;
the chapter is also dense with exact tokens (ASCII, LSB, 11000101) where
lexical match is decisive. RRF needs no score normalisation between them,
which matters because cosine and BM25 scores are not comparable.

No vector database: at 40-70 passages a brute-force dot product is exact and
sub-millisecond (research.md section 6).

With `retrieval.reranker` set, every RRF candidate (not just the top_k) is
rescored by a cross-encoder and the best top_k kept - so the reranker can
promote a passage RRF ranked 8th. See docs/technical-decisions.md section 14.
"""

from __future__ import annotations

import re

import numpy as np
from rank_bm25 import BM25Okapi

from ..config import Config
from ..models import Passage, RetrievalResult
from . import embed, rerank, store

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


class Retriever:
    """Holds the index in memory. Build once, query many times."""

    def __init__(self, cfg: Config, passages: list[Passage], vectors: np.ndarray):
        self.cfg = cfg
        self.passages = passages
        self.vectors = vectors
        self.bm25 = BM25Okapi([tokenize(p.search_text()) for p in passages])
        if cfg.retrieval.reranker:
            # Load now so the first child's question doesn't pay for it.
            rerank.get_model(cfg.retrieval.reranker)

    @classmethod
    def load(cls, cfg: Config) -> "Retriever":
        passages = store.load_passages(cfg)
        vectors = store.load_embeddings(cfg)
        if vectors.shape[0] != len(passages):
            raise ValueError(
                f"Index is inconsistent: {vectors.shape[0]} vectors for "
                f"{len(passages)} passages. Re-run: python -m kidsrag ingest --force"
            )
        return cls(cfg, passages, vectors)

    def _dense_scores(self, question: str) -> np.ndarray:
        if self.vectors.shape[0] == 0:
            return np.zeros(0, dtype=np.float32)
        q = embed.embed_query(question)
        # Vectors are already L2-normalised, so this dot product IS cosine.
        return self.vectors @ q

    def _sparse_ranking(self, question: str, k: int) -> list[int]:
        scores = self.bm25.get_scores(tokenize(question))
        return list(np.argsort(-np.asarray(scores))[:k])

    def retrieve(self, question: str) -> RetrievalResult:
        cfg = self.cfg.retrieval
        if not self.passages:
            return RetrievalResult(passages=[], scores=[], passed_gate=False)

        dense_scores = self._dense_scores(question)
        dense = list(np.argsort(-dense_scores)[: cfg.candidates])
        sparse = self._sparse_ranking(question, cfg.candidates)

        dense_rank = {int(idx): r + 1 for r, idx in enumerate(dense)}
        sparse_rank = {int(idx): r + 1 for r, idx in enumerate(sparse)}

        fused: dict[int, float] = {}
        for ranking in (dense_rank, sparse_rank):
            for idx, rank in ranking.items():
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (cfg.rrf_k + rank)

        ordered = sorted(fused.items(), key=lambda kv: -kv[1])
        max_cosine = float(dense_scores.max()) if dense_scores.size else 0.0
        passed_gate = max_cosine >= cfg.gate_min_cosine

        rerank_scores: dict[str, float] = {}
        # Only when the gate passes: a refusal never uses the order, and the
        # cross-encoder costs ~1s on CPU that a refused child shouldn't wait.
        if cfg.reranker and passed_gate:
            idxs = [i for i, _ in ordered]
            logits = rerank.score(
                cfg.reranker, question, [self.passages[i].embed_text() for i in idxs]
            )
            rerank_scores = {
                self.passages[i].id: float(s) for i, s in zip(idxs, logits)
            }
            ordered.sort(key=lambda kv: -rerank_scores[self.passages[kv[0]].id])
        ordered = ordered[: cfg.top_k]

        passages = [self.passages[i] for i, _ in ordered]
        scores = [s for _, s in ordered]

        result = RetrievalResult(
            passages=passages,
            scores=scores,
            dense_ranks={
                self.passages[i].id: r for i, r in dense_rank.items()
            },
            sparse_ranks={
                self.passages[i].id: r for i, r in sparse_rank.items()
            },
            max_cosine=max_cosine,
            rerank_scores=rerank_scores,
            passed_gate=passed_gate,
        )
        # The pre-generation gate: below threshold we refuse without ever
        # calling the model (Principle II, research.md section 8).
        #
        # Gating on the FUSED score does not work, and this was measured, not
        # assumed: RRF scores depend only on rank, so the top result always
        # scores ~1/(k+1) whether it is relevant or not. Observed top fused
        # score was 0.0315 for "How does a computer store a letter?" and
        # 0.0296 for "What did I eat for breakfast?" - indistinguishable.
        #
        # Raw cosine is an absolute measure and separates cleanly:
        #   in-scope      0.68 - 0.86
        #   out-of-scope  0.47 - 0.60
        # RRF (or the reranker) decides the ORDER; cosine decides whether to
        # answer. The cross-encoder's score was tested as a gate and does not
        # separate better - see docs/technical-decisions.md section 14.
        return result


def rrf_fuse(
    rankings: list[list[str]], k: int = 60, top_k: int | None = None
) -> list[tuple[str, float]]:
    """Standalone RRF over ranked id lists. Exposed for unit testing."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            fused[item] = fused.get(item, 0.0) + 1.0 / (k + rank)
    ordered = sorted(fused.items(), key=lambda kv: -kv[1])
    return ordered[:top_k] if top_k else ordered
