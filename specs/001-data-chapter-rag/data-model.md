# Phase 1 Data Model: Document-Grounded RAG for the "Data" Chapter

**Date**: 2026-10-18 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

All state is files under `artifacts/{chapter_slug}/`. There is no database; entities below are
in-memory dataclasses with a declared on-disk form.

---

## Entity overview

```text
Chapter ──1:N── Spread ──1:N── Passage ──N:M── PageImage
                                  │
                              (retrieved)
                                  ▼
RetrievalResult ──> Answer | Refusal | Trouble ──> rendered to child
                                  ▲
                          EvaluationQuestion
```

---

## Chapter

The unit of processing. Resolved from the PDF's TOC by title.

| Field | Type | Notes |
|---|---|---|
| `title` | str | From config. Matched case-insensitively against TOC entries. |
| `slug` | str | Lowercased, hyphenated. Names the artifact directory. |
| `start_page` | int | 1-based PDF page. Derived from TOC. |
| `end_page` | int | 1-based, inclusive. Derived from the next top-level TOC entry minus one. |
| `spread_count` | int | Count of level-3 TOC entries in range. |

**Validation**

- `title` MUST match exactly one top-level TOC entry; zero matches raise `ChapterNotFound` listing
  available chapters (FR-005, spec Edge Cases).
- `end_page >= start_page`; a range of zero pages is an error, never an empty index.

**Reference values** (measured): `Data` → pages 80–97, 8 spreads.

---

## Spread

A two-page topic unit — the book's own organising structure. Intermediate; not persisted
separately.

| Field | Type | Notes |
|---|---|---|
| `title` | str | e.g. "Binary code" |
| `pages` | list[int] | Usually two facing pages |
| `passages` | list[Passage] | Produced by the heading chunker |

---

## Passage

The retrievable unit. One section of a spread, under one heading.

| Field | Type | Notes |
|---|---|---|
| `id` | str | Stable slug: `{chapter}-{spread}-{section}`, e.g. `data-binary-code-binary-to-decimal` |
| `heading_path` | list[str] | e.g. `["Data", "Binary code", "Binary to decimal"]` |
| `text` | str | Cleaned body prose only |
| `labels` | str | Diagram label text from the same region; searchable, excluded from prose |
| `see_also` | list[str] | Cross-reference targets from `SEE ALSO` panels |
| `pages` | list[int] | Source PDF page(s) |
| `page_images` | list[str] | Relative paths into `pages/` |
| `bbox` | tuple[float × 4] | Union of contributing block boxes. Unused in v1; recorded so figure cropping can be added without re-ingesting. |

**Validation**

- `id` unique within a chapter.
- `text` non-empty after cleanup; empty passages are dropped, not indexed.
- `text` MUST NOT contain folios or running heads; hyphenated line wraps MUST be rejoined (FR-009).
- `labels` MUST NOT be concatenated into `text` (FR-010).
- Every `page_images` entry MUST exist on disk, or the passage is persisted with the missing entry
  removed (FR-022 — degrade, never fail).

**On disk**: `passages.jsonl`, one JSON object per line.

**Expected volume**: 40–70 passages for the Data chapter.

---

## PageImage

A rendered chapter page — the visual unit (research §3).

| Field | Type | Notes |
|---|---|---|
| `page` | int | 1-based PDF page |
| `path` | str | `pages/p{page:03d}.png` |
| `dpi` | int | 150 |

**Validation**: exactly one image per page in the chapter range (FR-011). A page that fails to
render is logged and omitted; ingest does not abort.

**On disk**: `pages/p080.png` … `pages/p097.png` (~1152 × 1377 px each).

---

## EmbeddingMatrix

| Property | Value |
|---|---|
| Shape | `(n_passages, 384)`, float32 |
| Model | `BAAI/bge-small-en-v1.5` |
| Normalisation | None needed — `fastembed` returns L2-normalised vectors (verified: norms = 1.0), so cosine similarity is a plain dot product |
| Row order | Matches `passages.jsonl` line order exactly |

**Validation**: row count MUST equal passage count. A mismatch invalidates the cache and forces
re-ingest rather than risking misattributed citations.

**On disk**: `embeddings.npy`.

---

## Manifest

The cache key and provenance record (FR-028).

| Field | Type | Notes |
|---|---|---|
| `pdf_sha256` | str | Of the source file |
| `chapter_title` | str | As configured |
| `pipeline_version` | str | Bumped on any chunker or cleanup change |
| `cache_key` | str | `sha256(pdf_sha256 + chapter_title + pipeline_version)` |
| `page_range` | [int, int] | |
| `passage_count` | int | |
| `embedding_model` | str | |
| `created_at` | str | ISO 8601 |

**Validation**: on start, ingest is skipped only if a manifest exists **and** its `cache_key`
matches the recomputed value. Any mismatch triggers a full rebuild (research §11).

**On disk**: `manifest.json`.

---

## RetrievalResult

In-memory only.

| Field | Type | Notes |
|---|---|---|
| `passages` | list[Passage] | Top-k after fusion, k=5 |
| `scores` | list[float] | Fused RRF scores, descending |
| `dense_ranks` / `sparse_ranks` | dict[str, int] | Per-retriever ranks, for the inspection panel |
| `top_score` | float | Drives the pre-generation gate |
| `passed_gate` | bool | False → refuse without calling the model |

**Validation**: `scores` descending; `passages` and `scores` equal length.

---

## Response types

Three mutually exclusive types. **This separation is how Principle I is enforced structurally** —
the renderer accepts only these, and none can carry an exception, status code, or provider name.

### Answer

| Field | Type | Notes |
|---|---|---|
| `text` | str | Child-facing. Carries `[C#]` citation markers. |
| `cited` | list[Passage] | Only passages actually cited |
| `page_images` | list[str] | Deduped, max 2 (FR-021) |

**Validation**: `cited` MUST be non-empty — an answer citing nothing is converted to a `Refusal`
(FR-018). Citation ids MUST resolve to retrieved passages; unknown ids are treated as no citation.

### Refusal

| Field | Type | Notes |
|---|---|---|
| `text` | str | Friendly, encouraging, suggests what to ask instead (FR-002) |
| `reason` | enum | `below_threshold` \| `no_citations` — reviewer-facing only, never rendered |

**Validation**: `text` MUST NOT imply system malfunction (FR-020).

### Trouble

| Field | Type | Notes |
|---|---|---|
| `text` | str | Child-facing: something went wrong, try again |
| `detail` | str | Reviewer-facing only. Never rendered to the child (FR-003). |

**Validation**: `text` MUST NOT imply the book lacks the answer (FR-020, SC-012), and MUST NOT
contain status codes, exception text, model or provider names (FR-003, SC-007).

---

## EvaluationQuestion

| Field | Type | Notes |
|---|---|---|
| `question` | str | |
| `expect` | enum | `answerable` \| `refuse` |
| `source` | str | `data` \| `other-chapter` \| `off-book` — provenance of must-refuse cases |
| `note` | str | Optional rationale |

**Validation**: the set MUST contain at least one `other-chapter` case. Out-of-chapter questions
are what actually test chapter scoping; nonsense questions prove little (FR-030, SC-002).

**On disk**: `tests/eval/questions.yaml`.

---

## Artifact layout

```text
artifacts/data/
├── manifest.json
├── passages.jsonl
├── embeddings.npy
└── pages/
    ├── p080.png
    └── … p097.png
```

Pointing the pipeline at another chapter creates a sibling directory (`artifacts/programming-techniques/`)
with no collision — the layout itself carries Principle V.

---

## State transitions

```text
question
   │
   ▼
retrieve ──► passed_gate == false ──► Refusal(below_threshold)
   │
   ▼ passed_gate == true
generate ──► upstream failure after retries ──► Trouble
   │
   ▼
citation check ──► no valid citations ──► Refusal(no_citations)
   │
   ▼
Answer
```

Every path terminates in exactly one of the three response types. There is no fourth outcome and
no path that reaches the child without passing through `render.py` (FR-027).
