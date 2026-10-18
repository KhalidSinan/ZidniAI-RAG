# Quickstart & Validation Guide

**Date**: 2026-10-18 | **Plan**: [plan.md](./plan.md)

How to run the system and verify it actually meets the spec. Each scenario below maps to success
criteria, so this doubles as the acceptance script.

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.12 | Pinned — `onnxruntime` wheel availability (research §5) |
| `uv` | Or `pip` with a virtualenv |
| The source PDF | At the path in `config.yaml` |
| An OpenRouter API key | Free tier is sufficient |
| ~400 MB disk | Embedding model weights + page images |

Ingestion and retrieval run **offline**. The network is needed only to generate answers.

## Setup

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"

cp .env.example .env
# put OPENROUTER_API_KEY=sk-or-... in .env
```

Verify the environment before building on it — this is the dependency risk flagged in research §5:

```bash
python -c "import fitz, fastembed, numpy, httpx, gradio; print('ok')"
```

If `fastembed` fails to import, fall back to `sentence-transformers` as documented in research §5
and record the change.

## Run

```bash
# 1. Process the chapter (first run downloads embedding weights)
python -m kidsrag ingest

# 2. Check the chunking before trusting anything built on it
python -m kidsrag inspect --limit 20

# 3. Ask a question
python -m kidsrag ask "How does a computer store a letter?"

# 4. Start the child-facing interface
python -m kidsrag ui
```

Expected from `ingest` on first run:

```text
Chapter: Data (pages 80–97, 8 spreads)
Passages: 52     Page images: 18
Elapsed: 2m14s   →  artifacts/data/
```

Second run should report `cached` and finish in seconds (FR-028, SC-010).

## Validation scenarios

### V1 — Grounded answer with a page image *(US1, SC-001, SC-003)*

```bash
python -m kidsrag ask "How does a computer store a letter?" --show-retrieval
```

**Pass**: an answer in plain language; the retrieval panel lists cited passage ids; at least one
page image path, and that page genuinely covers the topic.
**Fail**: any claim absent from the cited passages; an unrelated page shown.

### V2 — Refusal for another chapter's topic *(US2, SC-002)*

```bash
python -m kidsrag ask "What is a gaming console?"
```

Gaming consoles are chapter 3, not Data — this tests chapter **scoping**, which a nonsense question
would not.

**Pass**: a friendly refusal that suggests what to ask instead; no fabricated answer.
**Fail**: any answer; or a blunt refusal with no redirection (FR-002, SC-005).

### V3 — Refusal makes no network call *(research §8)*

Ask V2's question with the API key unset.

**Pass**: the same refusal, immediately. The pre-generation gate fires before any network call.
**Fail**: a `Trouble` response — meaning the gate did not fire and the model was called.

### V4 — Upstream failure is not disguised as a refusal *(SC-012, FR-020)*

Set an invalid API key and ask an **answerable** question.

**Pass**: a "something went wrong, try again" message, clearly distinct from a refusal.
**Fail**: any wording implying the book lacks the answer.

### V5 — No technical text reaches the child *(SC-007, FR-003)*

With an invalid key, inspect the UI output.

**Pass**: no status code, exception text, model name, or provider name anywhere in the child-facing
view.
**Fail**: any of the above — including the string `openrouter` or `llama`.

### V6 — Chapter switch by one value *(US3, SC-008)*

```bash
# edit config.yaml: chapter.title: "Programming techniques"
python -m kidsrag ingest
python -m kidsrag ask "What is a compiler?"
python -m kidsrag ask "What is binary code?"
```

**Pass**: the compiler question is answered; the binary question — previously answerable — is now
refused; `git diff` shows `config.yaml` as the only modified file.
**Fail**: any source file needed editing.

### V7 — Child-appropriate language *(SC-004, SC-006)*

Run the evaluation set and read ten answers.

**Pass**: no term the chapter does not itself introduce; sentences no longer than the book's own.
**Fail**: unexplained jargon, or register aimed at an adult.

### V8 — Stage independence *(FR-013, Principle V)*

Run each stage alone, in order, from a clean `artifacts/`.

**Pass**: each runs and its output is inspectable without the others.
**Fail**: any stage requiring another to be run in the same process.

## Automated check

```bash
pytest                      # unit + contract tests
python -m kidsrag eval      # the full evaluation set
```

`eval` exits non-zero if **any** must-refuse question gets answered — a grounding regression
(SC-002). Answerable questions are reported for human judgement rather than auto-failed, because
their correctness is not machine-checkable (SC-001).

## Notebook

```bash
jupyter lab notebooks/01_pipeline.ipynb
```

Walks all five stages in order using the same `src/kidsrag` package the CLI and UI use — no
duplicated logic, so what the notebook demonstrates is what actually ships.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ChapterNotFound` | Title doesn't match the TOC | Message lists valid titles; copy one exactly |
| `ingest` reports 0 passages | Role table derivation failed on an unusual chapter | Run `inspect`; check the `(font, size)` histogram |
| Every question returns `Trouble` | Missing or invalid API key | Check `.env`; startup warns about this |
| Every question is refused | Score threshold too high | Recalibrate per research §8 |
| `onnxruntime` won't install | Python version too new | Use 3.12, not 3.13 |
| Page images missing from answers | Ingest wrote no PNGs | Re-run `ingest --force`; check disk space |
