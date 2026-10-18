"""Local embeddings.

fastembed on ONNX Runtime, so no PyTorch. Verified: 519 MB total environment,
model loads in ~18s cold and embeds a chapter in well under a second
(research.md section 5).

Vectors come back L2-normalised, so cosine similarity is a plain dot product.
Do not normalise again.
"""

from __future__ import annotations

import numpy as np

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384

_model = None


def get_model():
    """Loaded once per process; the weights are cached on disk after first use."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(MODEL_NAME)
    return _model


def embed_documents(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, DIMENSIONS), dtype=np.float32)
    vectors = list(get_model().embed(texts))
    return np.asarray(vectors, dtype=np.float32)


def embed_query(text: str) -> np.ndarray:
    """bge models expect a short instruction prefix on queries, not documents."""
    prefixed = f"Represent this sentence for searching relevant passages: {text}"
    vectors = list(get_model().query_embed(prefixed))
    return np.asarray(vectors[0], dtype=np.float32)
