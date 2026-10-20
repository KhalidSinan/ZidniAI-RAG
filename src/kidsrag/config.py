"""Configuration loading and validation.

Contract: specs/001-data-chapter-rag/contracts/config.schema.md

Configuration errors are operator-facing and may be technical - they occur
before any child-facing surface exists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .errors import ConfigError
from .models import slugify

DEFAULT_CONFIG_PATH = Path("config.yaml")
MANDATED_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


@dataclass
class IngestConfig:
    dpi: int = 150
    pipeline_version: str = "1"


@dataclass
class RetrievalConfig:
    top_k: int = 5
    candidates: int = 10
    rrf_k: int = 60
    gate_min_cosine: float = 0.66
    # fastembed cross-encoder name, or None to keep plain RRF order.
    reranker: str | None = None


@dataclass
class GenerationConfig:
    model: str = MANDATED_MODEL
    base_url: str = "https://openrouter.ai/api/v1"
    temperature: float = 0.2
    max_tokens: int = 500
    timeout_seconds: int = 60
    max_retries: int = 3


@dataclass
class Config:
    pdf_path: Path
    chapter_title: str
    ingest: IngestConfig = field(default_factory=IngestConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    artifacts_dir: Path = Path("artifacts")

    @property
    def chapter_slug(self) -> str:
        return slugify(self.chapter_title)

    @property
    def chapter_dir(self) -> Path:
        """Per-chapter artifacts. Two chapters coexist without collision."""
        return self.artifacts_dir / self.chapter_slug

    @property
    def api_key(self) -> str | None:
        return os.environ.get("OPENROUTER_API_KEY") or None


def _require(d: dict, *path: str) -> object:
    node: object = d
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise ConfigError(f"Missing required config key: {'.'.join(path)}")
        node = node[key]
    return node


def _check_range(name: str, value: float, lo: float, hi: float | None = None) -> None:
    if value < lo or (hi is not None and value > hi):
        bound = f"{lo}-{hi}" if hi is not None else f">= {lo}"
        raise ConfigError(f"Config '{name}' is {value}; valid range is {bound}")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> Config:
    """Load, validate, and return the configuration.

    Raises ConfigError on any violation of contracts/config.schema.md.
    """
    load_dotenv()

    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse {path}: {exc}") from exc

    # Secrets must never live in the config file.
    flat = yaml.safe_dump(raw).lower()
    if "openrouter_api_key" in flat or "sk-or-" in flat:
        raise ConfigError(
            "An API key appears to be inline in config.yaml. "
            "Put OPENROUTER_API_KEY in .env instead - config.yaml is committed."
        )

    # Relative paths resolve against the CONFIG FILE's directory, not the
    # current working directory, so the same config works from the repo root,
    # from notebooks/, or from anywhere else.
    root = path.resolve().parent

    def _resolve(p: str | Path) -> Path:
        p = Path(p)
        return p if p.is_absolute() else (root / p)

    pdf_path = _resolve(str(_require(raw, "pdf", "path")))
    if not pdf_path.exists():
        raise ConfigError(f"PDF not found at configured path: {pdf_path}")

    chapter_title = str(_require(raw, "chapter", "title")).strip()
    if not chapter_title:
        raise ConfigError("Config 'chapter.title' must not be empty")

    ing = raw.get("ingest") or {}
    ingest = IngestConfig(
        dpi=int(ing.get("dpi", 150)),
        pipeline_version=str(ing.get("pipeline_version", "1")),
    )
    _check_range("ingest.dpi", ingest.dpi, 72, 300)

    ret = raw.get("retrieval") or {}
    retrieval = RetrievalConfig(
        top_k=int(ret.get("top_k", 5)),
        candidates=int(ret.get("candidates", 10)),
        rrf_k=int(ret.get("rrf_k", 60)),
        gate_min_cosine=float(ret.get("gate_min_cosine", 0.66)),
        reranker=str(ret.get("reranker") or "").strip() or None,
    )
    _check_range("retrieval.top_k", retrieval.top_k, 1, 20)
    _check_range("retrieval.rrf_k", retrieval.rrf_k, 1)
    _check_range("retrieval.gate_min_cosine", retrieval.gate_min_cosine, 0.0, 1.0)
    if retrieval.candidates < retrieval.top_k:
        raise ConfigError(
            f"Config 'retrieval.candidates' ({retrieval.candidates}) must be "
            f">= 'retrieval.top_k' ({retrieval.top_k})"
        )

    gen = raw.get("generation") or {}
    generation = GenerationConfig(
        model=str(gen.get("model", MANDATED_MODEL)),
        base_url=str(gen.get("base_url", "https://openrouter.ai/api/v1")),
        temperature=float(gen.get("temperature", 0.2)),
        max_tokens=int(gen.get("max_tokens", 500)),
        timeout_seconds=int(gen.get("timeout_seconds", 60)),
        max_retries=int(gen.get("max_retries", 3)),
    )
    _check_range("generation.temperature", generation.temperature, 0.0, 1.0)
    _check_range("generation.max_retries", generation.max_retries, 0)
    _check_range("generation.timeout_seconds", generation.timeout_seconds, 1)

    paths = raw.get("paths") or {}
    artifacts_dir = _resolve(str(paths.get("artifacts_dir", "artifacts")))

    return Config(
        pdf_path=pdf_path,
        chapter_title=chapter_title,
        ingest=ingest,
        retrieval=retrieval,
        generation=generation,
        artifacts_dir=artifacts_dir,
    )
