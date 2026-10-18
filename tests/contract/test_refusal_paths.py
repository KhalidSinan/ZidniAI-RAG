"""The refusal and failure paths.

The critical assertion here is that a below-threshold question makes ZERO
network calls (research.md section 8), and that upstream failure produces
Trouble and never Refusal (SC-012).
"""

from __future__ import annotations

import pytest

from kidsrag.config import Config, GenerationConfig, RetrievalConfig
from kidsrag.errors import UpstreamError
from kidsrag.generate import answer as answer_mod
from kidsrag.generate.answer import answer_question
from kidsrag.models import Passage, Refusal, RefusalReason, RetrievalResult, Trouble


@pytest.fixture
def cfg(tmp_path) -> Config:
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    return Config(
        pdf_path=pdf,
        chapter_title="Data",
        retrieval=RetrievalConfig(gate_min_cosine=0.66),
        generation=GenerationConfig(max_retries=0),
        artifacts_dir=tmp_path / "artifacts",
    )


def a_passage() -> Passage:
    return Passage(id="p1", heading_path=["Data", "X"], text="Body.", pages=[82])


def test_below_threshold_refuses_without_any_network_call(cfg, monkeypatch):
    called = False

    def explode(*_a, **_k):
        nonlocal called
        called = True
        raise AssertionError("the model must not be called below threshold")

    monkeypatch.setattr(answer_mod.llm, "complete", explode)

    result = RetrievalResult(
        passages=[a_passage()], scores=[0.01], max_cosine=0.40, passed_gate=False
    )
    response = answer_question(cfg, "Who won the World Cup?", result)

    assert isinstance(response, Refusal)
    assert response.reason is RefusalReason.BELOW_THRESHOLD
    assert called is False


def test_empty_retrieval_refuses(cfg):
    result = RetrievalResult(passages=[], scores=[], passed_gate=True)
    assert isinstance(answer_question(cfg, "anything", result), Refusal)


def test_upstream_failure_yields_trouble_not_refusal(cfg, monkeypatch):
    def rate_limited(*_a, **_k):
        raise UpstreamError("HTTP 429: rate limited")

    monkeypatch.setattr(answer_mod.llm, "complete", rate_limited)

    result = RetrievalResult(
        passages=[a_passage()], scores=[0.03], max_cosine=0.80, passed_gate=True
    )
    response = answer_question(cfg, "What is binary code?", result)

    assert isinstance(response, Trouble)
    assert not isinstance(response, Refusal)
    assert "429" in response.detail  # retained for the reviewer


def test_missing_api_key_yields_trouble(cfg, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = RetrievalResult(
        passages=[a_passage()], scores=[0.03], max_cosine=0.80, passed_gate=True
    )
    assert isinstance(answer_question(cfg, "What is binary code?", result), Trouble)


def test_uncited_answer_downgrades_to_refusal(cfg, monkeypatch):
    monkeypatch.setattr(
        answer_mod.llm, "complete", lambda *_a, **_k: "Confident but ungrounded."
    )
    result = RetrievalResult(
        passages=[a_passage()], scores=[0.03], max_cosine=0.80, passed_gate=True
    )
    response = answer_question(cfg, "What is binary code?", result)
    assert isinstance(response, Refusal)
    assert response.reason is RefusalReason.NO_CITATIONS
