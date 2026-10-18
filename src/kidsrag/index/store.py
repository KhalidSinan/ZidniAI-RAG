"""Artifact persistence and the cache key.

Layout (data-model.md):

    artifacts/{chapter_slug}/
        manifest.json
        passages.jsonl
        embeddings.npy
        pages/p080.png ...
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..config import Config
from ..errors import ArtifactsMissing
from ..models import Manifest, Passage

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def compute_cache_key(pdf_sha256: str, chapter_title: str, pipeline_version: str) -> str:
    """Includes pipeline_version so a chunker change invalidates stale output.

    Without it a reviewer editing the chunker would silently get old
    artifacts - worse than a slow rebuild.
    """
    raw = f"{pdf_sha256}|{chapter_title}|{pipeline_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def pages_dir(cfg: Config) -> Path:
    return cfg.chapter_dir / "pages"


def manifest_path(cfg: Config) -> Path:
    return cfg.chapter_dir / "manifest.json"


def passages_path(cfg: Config) -> Path:
    return cfg.chapter_dir / "passages.jsonl"


def embeddings_path(cfg: Config) -> Path:
    return cfg.chapter_dir / "embeddings.npy"


def save(
    cfg: Config,
    passages: list[Passage],
    embeddings: np.ndarray,
    manifest: Manifest,
) -> None:
    cfg.chapter_dir.mkdir(parents=True, exist_ok=True)

    with open(passages_path(cfg), "w", encoding="utf-8") as fh:
        for p in passages:
            fh.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")

    np.save(embeddings_path(cfg), embeddings.astype(np.float32))

    manifest_path(cfg).write_text(
        json.dumps(manifest.to_dict(), indent=2), encoding="utf-8"
    )


def load_passages(cfg: Config) -> list[Passage]:
    path = passages_path(cfg)
    if not path.exists():
        raise ArtifactsMissing(str(cfg.chapter_dir))
    with open(path, encoding="utf-8") as fh:
        return [Passage.from_dict(json.loads(line)) for line in fh if line.strip()]


def load_embeddings(cfg: Config) -> np.ndarray:
    path = embeddings_path(cfg)
    if not path.exists():
        raise ArtifactsMissing(str(cfg.chapter_dir))
    return np.load(path)


def load_manifest(cfg: Config) -> Manifest | None:
    path = manifest_path(cfg)
    if not path.exists():
        return None
    try:
        return Manifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, TypeError):
        return None  # Corrupt manifest: treat as absent and rebuild.


def is_cached(cfg: Config, cache_key: str) -> bool:
    """True only if a manifest exists, its key matches, and the data is intact."""
    manifest = load_manifest(cfg)
    if manifest is None or manifest.cache_key != cache_key:
        return False
    if not (passages_path(cfg).exists() and embeddings_path(cfg).exists()):
        return False
    try:
        vectors = np.load(embeddings_path(cfg), mmap_mode="r")
    except (OSError, ValueError):
        return False
    # A row/passage mismatch would misattribute citations - rebuild instead.
    return vectors.shape[0] == manifest.passage_count


def build_manifest(
    cfg: Config,
    pdf_sha256: str,
    cache_key: str,
    page_range: tuple[int, int],
    passage_count: int,
) -> Manifest:
    return Manifest(
        pdf_sha256=pdf_sha256,
        chapter_title=cfg.chapter_title,
        pipeline_version=cfg.ingest.pipeline_version,
        cache_key=cache_key,
        page_range=page_range,
        passage_count=passage_count,
        embedding_model=EMBEDDING_MODEL,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
