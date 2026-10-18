# Contract: Configuration Schema

**File**: `config.yaml` (repo root) | **Loader**: `src/kidsrag/config.py`

This contract exists to satisfy Principle V and FR-012: **`chapter.title` is the only value a user
must change to target a different chapter.** Everything else has a working default.

## Schema

```yaml
pdf:
  path: "Help Your Kids with Computer Science_ ... ( PDFDrive ).pdf"

chapter:
  title: "Data"              # ← the single value that selects a chapter

ingest:
  dpi: 150
  pipeline_version: "1"      # bump to invalidate cached artifacts

retrieval:
  top_k: 5
  candidates: 10             # per retriever, before fusion
  rrf_k: 60
  score_threshold: 0.0167    # calibrated; see research.md §8

generation:
  model: "meta-llama/llama-3.3-70b-instruct:free"
  base_url: "https://openrouter.ai/api/v1"
  temperature: 0.2
  max_tokens: 500
  timeout_seconds: 60
  max_retries: 3

paths:
  artifacts_dir: "artifacts"
```

## Field contract

| Key | Type | Default | Constraint |
|---|---|---|---|
| `pdf.path` | str | — | Required. Must exist; missing file is a startup error, not a runtime one. |
| `chapter.title` | str | `"Data"` | Required. Matched case-insensitively against top-level TOC entries. Exactly one match required. |
| `ingest.dpi` | int | `150` | 72–300. Below 100 page text becomes unreadable, defeating FR-011. |
| `ingest.pipeline_version` | str | `"1"` | Participates in the cache key. Any chunker change MUST bump it. |
| `retrieval.top_k` | int | `5` | 1–20 |
| `retrieval.candidates` | int | `10` | `>= top_k` |
| `retrieval.rrf_k` | int | `60` | > 0. Standard RRF constant. |
| `retrieval.score_threshold` | float | calibrated | `>= 0`. Gate for `below_threshold` refusal. |
| `generation.model` | str | mandated id | **Fixed by the constitution.** Changing it violates Mandated Constraints. |
| `generation.temperature` | float | `0.2` | 0–1. Low by intent: grounded recall, not creativity. |
| `generation.max_retries` | int | `3` | `>= 0` |
| `paths.artifacts_dir` | str | `"artifacts"` | Per-chapter subdirectory created beneath it. |

## Secrets

`OPENROUTER_API_KEY` is read from the environment, or from a `.env` file that MUST be
git-ignored. It MUST NOT appear in `config.yaml`.

A missing key is detected **at startup**, not on the first question, and reported to the operator
in plain language. A child must never meet a credentials error (FR-003).

## Validation behaviour

| Condition | Behaviour |
|---|---|
| `pdf.path` missing | Startup error naming the expected path |
| `chapter.title` matches no TOC entry | `ChapterNotFound`, listing available chapter titles (FR-005) |
| `chapter.title` matches more than one | Startup error listing the matches |
| Numeric field out of range | Startup error naming the field and its valid range |
| `OPENROUTER_API_KEY` absent | Startup warning; ingest and retrieval still run; generation returns `Trouble` |

Configuration errors are **operator-facing** and may use technical language — they occur before
any child-facing surface exists.

## Contract tests

- Default config loads and validates.
- Changing only `chapter.title` to `"Programming techniques"` resolves a different page range
  and a different artifacts directory, with no other field altered (FR-012, SC-008).
- Each out-of-range numeric field is rejected with a message naming the field.
- A config containing an inline API key is rejected.
