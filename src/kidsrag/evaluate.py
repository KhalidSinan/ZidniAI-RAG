"""Evaluation runner.

Exits non-zero if ANY must-refuse question gets answered - that is a
grounding regression (SC-002). Answerable questions are reported but do not
fail the run: their correctness is a human judgement against the book
(SC-001), not something this script can decide.

--retrieval-only exercises the gate without spending LLM calls, which is how
the threshold gets calibrated and how CI can run without a key.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .config import Config
from .models import Answer, Refusal, Trouble


def load_questions(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("questions", [])


def run_eval(cfg: Config, path: Path, retrieval_only: bool = False) -> int:
    from .generate.answer import answer_question
    from .index.retrieve import Retriever

    if not path.exists():
        print(f"No question set at {path}")
        return 1

    questions = load_questions(path)
    retriever = Retriever.load(cfg)

    rows: list[tuple[str, str, str, bool, float]] = []
    for item in questions:
        q = item["question"]
        expect = item.get("expect", "answerable")
        result = retriever.retrieve(q)

        if retrieval_only:
            actual = "answerable" if result.passed_gate else "refuse"
        else:
            response = answer_question(cfg, q, result)
            if isinstance(response, Answer):
                actual = "answerable"
            elif isinstance(response, Refusal):
                actual = "refuse"
            elif isinstance(response, Trouble):
                actual = "trouble"
            else:  # pragma: no cover - defensive
                actual = "unknown"

        ok = actual == expect
        rows.append((q, expect, actual, ok, result.max_cosine))

    mode = "retrieval gate only" if retrieval_only else "full pipeline"
    print(f"Evaluation ({mode}) - {len(rows)} questions\n")
    print(f"{'':2s} {'cos':>6s}  {'expected':10s} {'actual':10s} question")
    for q, expect, actual, ok, cos in rows:
        mark = "ok" if ok else "XX"
        print(f"{mark:2s} {cos:6.4f}  {expect:10s} {actual:10s} {q[:52]}")

    answerable = [r for r in rows if r[1] == "answerable"]
    refusals = [r for r in rows if r[1] == "refuse"]
    a_ok = sum(1 for r in answerable if r[3])
    r_ok = sum(1 for r in refusals if r[3])

    print(f"\nAnswerable: {a_ok}/{len(answerable)} reached an answer")
    print(f"Must refuse: {r_ok}/{len(refusals)} refused")

    troubles = [r for r in rows if r[2] == "trouble"]
    if troubles:
        print(
            f"\n{len(troubles)} question(s) hit an upstream failure. "
            "That is a service problem, not a grounding result - "
            "re-run before drawing conclusions."
        )

    leaked = [r for r in refusals if r[2] == "answerable"]
    if leaked:
        print(f"\nFAIL: {len(leaked)} must-refuse question(s) were answered:")
        for q, _e, _a, _ok, cos in leaked:
            print(f"  cos={cos:.4f}  {q}")
        return 1

    print("\nPASS: every must-refuse question refused.")
    return 0
