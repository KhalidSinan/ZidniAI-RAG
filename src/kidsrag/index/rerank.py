"""Cross-encoder reranking.

The dense retriever embeds question and passage separately and compares the
vectors; a cross-encoder reads them TOGETHER, so it can see that 'store a
letter' is answered by a passage about ASCII even when few words overlap.
That is too slow for a whole library but trivial for the ~10-20 candidates
RRF leaves here.

Runs on fastembed's ONNX runtime like the embedder - no PyTorch, no network
call per question. The weights download once on first use.
"""

from __future__ import annotations

import numpy as np

_models: dict[str, object] = {}


def get_model(name: str):
    """Loaded once per process and model name."""
    if name not in _models:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        _models[name] = TextCrossEncoder(name)
    return _models[name]


def score(name: str, question: str, documents: list[str]) -> np.ndarray:
    """Relevance logits, one per document. Higher is more relevant.

    Logits, not probabilities: comparable within one question, which is all
    ordering needs. They are NOT used for the refusal gate.
    """
    if not documents:
        return np.zeros(0, dtype=np.float32)
    return np.asarray(list(get_model(name).rerank(question, documents)), dtype=np.float32)
