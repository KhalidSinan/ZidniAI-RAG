"""Config contract (contracts/config.schema.md) and chapter resolution."""

from __future__ import annotations

import pytest
import yaml

from kidsrag.config import load_config
from kidsrag.errors import ChapterNotFound, ConfigError

BASE = {
    "pdf": {"path": "book.pdf"},
    "chapter": {"title": "Data"},
    "ingest": {"dpi": 150, "pipeline_version": "1"},
    "retrieval": {
        "top_k": 5,
        "candidates": 10,
        "rrf_k": 60,
        "gate_min_cosine": 0.66,
    },
    "generation": {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "temperature": 0.2,
        "max_retries": 3,
        "timeout_seconds": 60,
    },
    "paths": {"artifacts_dir": "artifacts"},
}


def write_config(tmp_path, **overrides):
    data = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE.items()}
    for section, values in overrides.items():
        if isinstance(values, dict):
            data.setdefault(section, {}).update(values)
        else:
            data[section] = values
    (tmp_path / "book.pdf").write_bytes(b"%PDF-1.4\n")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_default_config_loads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = load_config(write_config(tmp_path))
    assert cfg.chapter_title == "Data"
    assert cfg.retrieval.top_k == 5
    assert cfg.generation.model.endswith(":free")


def test_chapter_slug_drives_a_per_chapter_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = load_config(write_config(tmp_path, chapter={"title": "Programming techniques"}))
    assert cfg.chapter_slug == "programming-techniques"
    assert cfg.chapter_dir.name == "programming-techniques"


@pytest.mark.parametrize(
    "section,values,field",
    [
        ("ingest", {"dpi": 10}, "ingest.dpi"),
        ("ingest", {"dpi": 1200}, "ingest.dpi"),
        ("retrieval", {"top_k": 0}, "retrieval.top_k"),
        ("retrieval", {"rrf_k": 0}, "retrieval.rrf_k"),
        ("retrieval", {"gate_min_cosine": 1.5}, "retrieval.gate_min_cosine"),
        ("generation", {"temperature": 3.0}, "generation.temperature"),
        ("generation", {"max_retries": -1}, "generation.max_retries"),
    ],
)
def test_out_of_range_fields_are_rejected_by_name(
    tmp_path, monkeypatch, section, values, field
):
    monkeypatch.chdir(tmp_path)
    path = write_config(tmp_path, **{section: values})
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert field in str(exc.value)


def test_candidates_below_top_k_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = write_config(tmp_path, retrieval={"top_k": 10, "candidates": 3})
    with pytest.raises(ConfigError):
        load_config(path)


def test_inline_api_key_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = write_config(tmp_path, generation={"openrouter_api_key": "sk-or-v1-secret"})
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert ".env" in str(exc.value)


def test_missing_pdf_is_a_startup_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = write_config(tmp_path, pdf={"path": "nope.pdf"})
    with pytest.raises(ConfigError):
        load_config(path)


def test_empty_chapter_title_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError):
        load_config(write_config(tmp_path, chapter={"title": "   "}))


def test_chapter_not_found_lists_available_chapters():
    err = ChapterNotFound("Nope", ["1 Getting started", "5 Data"])
    assert "5 Data" in str(err)
    assert "Nope" in str(err)
