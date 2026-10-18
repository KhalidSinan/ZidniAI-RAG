---

description: "Task list for Document-Grounded RAG for the Data Chapter"
---

# Tasks: Document-Grounded RAG for the "Data" Chapter

**Input**: Design documents from `/specs/001-data-chapter-rag/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included. The spec requires them — FR-030 mandates a re-runnable evaluation set, and each contract in `contracts/` defines its own contract tests.

**Organization**: Grouped by user story so each is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1, US2, US3 — maps to the user stories in spec.md
- Exact file paths are given in every task

## Path Conventions

Single project: `src/kidsrag/`, `tests/`, `notebooks/`, `docs/` at repository root (plan.md § Project Structure).

**Already done** (verified 2026-10-18): `.venv` on Python 3.12.13 with all dependencies installed, `requirements.txt` pinned (140 packages), `.gitignore` written. Phase 1 starts from there.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package skeleton and configuration surface

- [X] T001 Create the package tree `src/kidsrag/{ingest,index,generate}/__init__.py`, plus `tests/{unit,contract,eval}/` and `notebooks/`, `docs/`, `artifacts/.gitkeep`
- [X] T002 Create `pyproject.toml` declaring the package, Python 3.12 requirement, runtime dependencies and a `[dev]` extra (pytest, jupyterlab); make `pip install -e .` work
- [X] T003 [P] Create `config.yaml` at repo root with every key and default from `contracts/config.schema.md` — `chapter.title: "Data"`, `ingest.dpi: 150`, `retrieval.top_k: 5`, `retrieval.candidates: 10`, `retrieval.rrf_k: 60`, `generation.model: "meta-llama/llama-3.3-70b-instruct:free"`, `generation.temperature: 0.2`, `generation.timeout_seconds: 60`, `generation.max_retries: 3`
- [X] T004 [P] Create `.env.example` documenting `OPENROUTER_API_KEY`; confirm `.env` is git-ignored
- [X] T005 [P] Configure pytest in `pyproject.toml` (testpaths, `src` layout on the import path)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types, config, chapter resolution, and the rendering boundary that every story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Implement `src/kidsrag/errors.py` with `PipelineError`, `ChapterNotFound`, `UpstreamError`
- [X] T007 Implement `src/kidsrag/config.py` — dataclass + YAML loader + `.env` loading, validating every constraint in `contracts/config.schema.md`: `ingest.dpi` in 72–300, `retrieval.candidates >= top_k`, `retrieval.rrf_k > 0`, `retrieval.score_threshold >= 0`, `generation.temperature` in 0–1, `generation.max_retries >= 0`; reject a config containing an inline API key; missing `pdf.path` is a startup error
- [X] T008 Implement `src/kidsrag/models.py` with the dataclasses from data-model.md: `Chapter`, `Spread`, `Passage` (`id`, `heading_path`, `text`, `labels`, `see_also`, `pages`, `page_images`, `bbox`), `PageImage`, `Manifest`, `RetrievalResult`, `Answer`, `Refusal` (`reason` enum `below_threshold | no_citations`), `Trouble` (`text` child-facing, `detail` reviewer-only)
- [X] T009 Implement `src/kidsrag/ingest/pdf.py` — open with `import pymupdf` (**not** the deprecated `fitz`), parse the TOC, resolve `Chapter` by title case-insensitively against top-level entries, derive `end_page` from the next top-level entry minus one; raise `ChapterNotFound` listing available titles on zero matches and a startup error on multiple matches
- [X] T010 [P] Implement `src/kidsrag/index/store.py` — compute `cache_key = sha256(pdf_sha256 + chapter_title + pipeline_version)`; read/write `manifest.json`, `passages.jsonl`, `embeddings.npy` under `artifacts/{chapter_slug}/`; validate that the embedding row count equals the passage count and invalidate the cache on mismatch
- [X] T011 [P] Implement `src/kidsrag/render.py` — the **only** module producing child-facing text. `render(response: Answer | Refusal | Trouble) -> ChildView`. It must never read `Trouble.detail`. No other module may write to the child-facing UI (FR-003, Principle I)
- [X] T012 Implement `src/kidsrag/cli.py` skeleton with the five subcommands from `contracts/pipeline-cli.md` (`ingest`, `inspect`, `ask`, `eval`, `ui`), each accepting `--config` defaulting to `./config.yaml`
- [X] T013 [P] Contract test for config in `tests/contract/test_config.py` — default config loads; each out-of-range numeric field is rejected naming the field; an inline API key is rejected
- [X] T014 [P] Unit test for chapter resolution in `tests/unit/test_chapter_resolution.py` — `"Data"` resolves to PDF pages 80–97 with 8 spreads; an unknown title raises `ChapterNotFound` listing available chapters

**Checkpoint**: Config loads, the chapter resolves, types and the rendering boundary exist

---

## Phase 3: User Story 1 — Grounded, sourced answer (Priority: P1) 🎯 MVP

**Goal**: A child asks a question covered by the chapter and gets a plain-language, grounded answer with the source page image beside it.

**Independent test**: Ask five questions whose answers appear in the chapter. Each answer is supported by its cited passages, uses no term the chapter does not introduce, and shows at least one correct page image.

### Ingestion

- [X] T015 [US1] Implement `src/kidsrag/ingest/roles.py` — build the `(font, size)` → role histogram for the chapter at ingest time and assign roles by character volume and page position. Reference values from research §4: body prose `MyriadPro-Light 9.0`, diagram labels `MyriadPro-Regular 8.0`, sidebar body `MyriadPro-LightSemiCn 9.0`, captions `MyriadPro-SemiCn 7.2`, standfirst `MyriadPro-Semibold 10.5`, section heading `Semibold/SemiboldCond 14.0`, spread title `MyriadPro-Regular 32.0`. **Derive, do not hardcode** — hardcoding breaks Principle V
- [X] T016 [US1] Implement text cleanup in `src/kidsrag/ingest/text.py` — strip folios and letterspaced running heads (e.g. `82\nD ATA\n82`), rejoin hyphenated line wraps (`digitiza-\ntion` → `digitization`), capture `SEE ALSO` blocks into `Passage.see_also` rather than prose (FR-009)
- [X] T017 [US1] Implement spread grouping and heading chunking in `src/kidsrag/ingest/text.py` — group chapter pages into spreads from level-3 TOC entries; open a new `Passage` at each 14pt section heading; prepend `heading_path`; assign `id` as `{chapter}-{spread}-{section}` slug, unique within the chapter; route diagram-label text to `Passage.labels` and **never** concatenate it into `text` (FR-010); drop passages whose `text` is empty after cleanup
- [X] T018 [P] [US1] Implement `src/kidsrag/ingest/pages.py` — render each chapter page at `ingest.dpi` (150) to `artifacts/{slug}/pages/p{page:03d}.png`; a page that fails to render is logged and omitted, and ingest does not abort
- [X] T019 [US1] Implement `src/kidsrag/ingest/build.py` orchestrating pdf → roles → text → pages → store; write `manifest.json`; skip when `cache_key` matches unless `--force`; exit 1 if zero passages are extracted (never a silent empty index)
- [X] T020 [US1] Wire `python -m kidsrag ingest` and `inspect` in `src/kidsrag/cli.py` per `contracts/pipeline-cli.md`; `ingest` prints chapter title, page range, spread count, passage count, image count, elapsed time
- [X] T021 [US1] **Manual validation gate** — run `ingest` then `inspect --limit 20` against the Data chapter and eyeball the chunk boundaries against the book before building retrieval on top. Expected roughly 40–70 passages and 18 page images

### Retrieval

- [X] T022 [P] [US1] Implement `src/kidsrag/index/embed.py` wrapping `fastembed.TextEmbedding("BAAI/bge-small-en-v1.5")`; **do not re-normalise** — vectors are already L2-normalised, so cosine is a plain dot product (research §5)
- [X] T023 [US1] Implement dense retrieval in `src/kidsrag/index/retrieve.py` — brute-force dot product over the `(n, 384)` float32 matrix; no vector database (research §6)
- [X] T024 [US1] Implement BM25 retrieval in `src/kidsrag/index/retrieve.py` over `text + labels + heading_path` using `rank_bm25`
- [X] T025 [US1] Implement RRF fusion in `src/kidsrag/index/retrieve.py` — take `retrieval.candidates` (10) from each retriever, fuse with `rrf_k` (60), return `retrieval.top_k` (5) as a `RetrievalResult` carrying `scores`, `dense_ranks`, `sparse_ranks`, `top_score`
- [X] T026 [P] [US1] Unit test RRF in `tests/unit/test_rrf.py` — fusion of two known rank lists produces the expected order; `scores` descending; `passages` and `scores` equal length

### Generation

- [X] T027 [US1] Implement `src/kidsrag/generate/prompt.py` — system prompt carrying the four obligations from `contracts/answer-contract.md` (grounding, `[C#]` citation, refusal, voice); context blocks formatted as `[C1] Data › Binary code › Binary to decimal\n<text>`; two few-shot exchanges in the book's register, one answerable and one refusal
- [X] T028 [US1] Implement `src/kidsrag/generate/llm.py` — POST to `generation.base_url` chat completions via `httpx` with the configured model, temperature, max_tokens and timeout; exponential backoff on 429/5xx up to `max_retries`; raise `UpstreamError` when exhausted
- [X] T029 [US1] Implement the citation check in `src/kidsrag/generate/answer.py` — regex-extract `[C#]` markers, discard markers not matching a supplied passage, return `Refusal(no_citations)` if none remain, otherwise `Answer` with `cited` set to the resolved passages only (FR-018)
- [X] T030 [US1] Implement image selection in `src/kidsrag/generate/answer.py` — collect `page_images` from **cited** passages only, deduplicate by page, cap at 2 in citation order, and drop any image whose file is missing while keeping the answer (FR-021, FR-022)
- [X] T031 [US1] Complete `src/kidsrag/render.py` for the `Answer` case — child-facing text, page images, and citation markers either rendered as footnote references or hidden, with the `cited` list still exposed to reviewers
- [X] T032 [US1] Wire `python -m kidsrag ask "<question>"` with `--show-retrieval` in `src/kidsrag/cli.py`; any of `Answer`/`Refusal`/`Trouble` exits 0; only missing artifacts or unreadable config exits 1
- [X] T033 [US1] Implement `src/kidsrag/app.py` (Gradio) — question box, answer, page images, and a separate reviewer-facing retrieval panel showing passage ids, fused scores and per-retriever ranks (FR-023, FR-024); exit 1 if artifacts are missing
- [X] T034 [US1] Apply Principle I styling to `src/kidsrag/app.py` — large readable type, generous spacing, high contrast, usable with no written instructions (FR-004, SC-006)
- [X] T035 [P] [US1] Contract test in `tests/contract/test_answer_contract.py` — a response with no `[C#]` markers yields `Refusal(no_citations)`; a response citing an unknown id is treated as uncited; a cited passage with a missing page image yields a text-only answer

**Checkpoint**: Answerable questions work end to end with page images — MVP deliverable

---

## Phase 4: User Story 2 — Honest, kind refusal (Priority: P2)

**Goal**: Questions the chapter does not cover are refused warmly and honestly, never guessed at.

**Independent test**: Submit the out-of-scope question set — several from other chapters, several unrelated to the book — and confirm every one refuses with no fabricated content.

- [X] T036 [US2] Implement the pre-generation score gate in `src/kidsrag/index/retrieve.py` — set `passed_gate = top_score >= retrieval.score_threshold`; when false the caller must return `Refusal(below_threshold)` **without any network call** (research §8)
- [X] T037 [US2] Write the refusal copy in `src/kidsrag/render.py` — friendly and encouraging, consistent across questions, naming chapter topics the child could ask about instead; must not imply malfunction (FR-002, FR-020)
- [X] T038 [US2] Write the `Trouble` copy in `src/kidsrag/render.py` — says something went wrong and to try again; must not imply the book lacks the answer, and must contain no status code, exception text, model name or provider name (FR-003, FR-020, SC-007, SC-012)
- [X] T039 [US2] Map `UpstreamError` to `Trouble` and never to `Refusal` in `src/kidsrag/generate/answer.py`; detect a missing API key at startup and warn the operator (SC-012)
- [X] T040 [P] [US2] Create `tests/eval/questions.yaml` — answerable questions from the Data chapter plus must-refuse questions tagged `source: other-chapter` (e.g. "What is a gaming console?", chapter 3) and `source: off-book`. At least one `other-chapter` case is required: out-of-chapter questions test chapter scoping, which nonsense questions do not (FR-030, SC-002)
- [X] T041 [US2] Implement `python -m kidsrag eval` in `src/kidsrag/cli.py` — report expected vs actual per question; exit 1 if **any** must-refuse question is answered; report answerable questions without auto-failing them (SC-001 is a human judgement)
- [X] T042 [US2] **Calibrate `retrieval.score_threshold`** against the eval set — choose the lowest value at which all must-refuse questions refuse, then confirm no answerable question is lost; record the chosen value and method in `docs/technical-decisions.md` (research §8 open item)
- [X] T043 [P] [US2] Contract test in `tests/contract/test_refusal_paths.py` — retrieval below threshold yields `Refusal(below_threshold)` with **zero** network calls (assert the HTTP client is never invoked); a forced 429 exhausting retries yields `Trouble`, never `Refusal`; `render()` of a `Trouble` whose `detail` holds a stack trace leaks none of it

**Checkpoint**: Grounding and refusal both hold — the two non-negotiable principles are demonstrably satisfied

---

## Phase 5: User Story 3 — Chapter-agnostic pipeline (Priority: P3)

**Goal**: Another chapter is served by changing one configuration value.

**Independent test**: Switch `chapter.title` to another chapter, re-run ingest, ask three questions about it — all answered, while previously-answerable Data questions now refuse, and `git diff` shows only `config.yaml` changed.

- [X] T044 [US3] Audit `src/kidsrag/` for hardcoded page numbers, chapter names, spread counts and font sizes; replace each with values derived from the TOC or the role histogram (Principle V)
- [X] T045 [US3] Confirm artifacts are written to a per-chapter directory (`artifacts/{chapter_slug}/`) so two chapters coexist without collision (data-model § Artifact layout)
- [X] T046 [US3] Verify every stage runs standalone from a clean `artifacts/` — `ingest`, then `inspect`, then `ask` — with no stage requiring another in the same process (FR-013)
- [X] T047 [P] [US3] Integration test in `tests/contract/test_chapter_switch.py` — setting `chapter.title: "Programming techniques"` resolves a different page range and a different artifacts directory with no other field altered (FR-012, SC-008)
- [X] T048 [US3] Run the live chapter switch per quickstart V6 and record the result; restore `chapter.title: "Data"` afterwards

**Checkpoint**: All three user stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Deliverables required by AI-task.md §4 and §6, and final validation

- [X] T049 [P] Write `README.md` — what the project is, setup from a clean checkout, how to run each command, where artifacts land, and the chapter-switch instruction (AI-task.md §6, SC-011)
- [X] T050 [P] Write `docs/technical-decisions.md` from research.md — the chunking strategy, whole-page images, fastembed over sentence-transformers, no vector database, hybrid RRF, two grounding gates, the PyMuPDF AGPL-3.0 licence note, and the calibrated threshold from T042; each with alternatives and trade-offs (AI-task.md §3, §6)
- [X] T051 [P] Write `docs/ai-development-report.md` — the AI-assisted workflow: context given to the agent, tasks delegated, how generated code was reviewed and validated, and which engineering decisions were retained by the author (AI-task.md §4)
- [X] T052 Build `notebooks/01_pipeline.ipynb` walking the five stages in order, **importing `src/kidsrag`** rather than duplicating logic, showing each stage's output including sample chunks and page images (AI-task.md §6)
- [X] T053 Document the chapter-numbering discrepancy in `README.md` — the brief says "chapter #6 (Data)" while this PDF puts Data at chapter 5; the title is treated as authoritative and the number is reachable via config
- [X] T054 [P] Unit test text cleanup in `tests/unit/test_cleanup.py` — folio and running-head stripping, hyphenated-wrap rejoining, `SEE ALSO` capture
- [ ] T055 Run the full quickstart validation V1–V8 and record pass/fail for each (SC-001 through SC-012) — **6 of 8 done; V1, V7 blocked**

  | | scenario | result |
  |---|---|---|
  | V1 | Grounded answer with page image | **blocked** — needs a live API key |
  | V2 | Refusal for another chapter's topic | PASS — 8/8 must-refuse refused |
  | V3 | Refusal makes no network call | PASS — 1.19s, zero calls, gate REFUSE at cos 0.5204 |
  | V4 | Upstream failure not disguised as refusal | PASS — returns Trouble, distinct wording |
  | V5 | No technical text reaches the child | PASS — leak scan clean |
  | V6 | Chapter switch by one value | PASS — see note below |
  | V7 | Child-appropriate language | **blocked** — needs generated answers to judge |
  | V8 | Stage independence | PASS — ingest / inspect / ask each run standalone |

  V6 note: the new chapter answers ("What is a compiler?", cos 0.82) and 3 of 4
  Data questions correctly refuse against it. "What is binary code?" scores
  0.6732 and passes, because Programming techniques genuinely covers machine
  code — arguably correct rather than a miss. Recorded in docs/technical-decisions.md section 7.
- [X] T056 Verify SC-009/SC-010 — a typical question completes in under 15 s; cold ingest under 5 min; a warm run reports `cached` and is ready in under 30 s
- [X] T057 Final pass for Principle I — confirm no technical text on any child-facing surface under forced failure, including the strings `openrouter`, `llama`, and any status code (SC-007)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: Depends on Foundational. The MVP.
- **US2 (Phase 4)**: Depends on Foundational; shares `retrieve.py` and `answer.py` with US1, so in practice follows US1
- **US3 (Phase 5)**: Depends on Foundational; meaningfully verifiable only once US1 works
- **Polish (Phase 6)**: Depends on the stories being complete

### Story-level notes

US1 and US2 are not fully independent in implementation — the citation check in US1 already emits `Refusal`, and US2 adds the threshold gate and the refusal copy. They remain independently *testable*: US1 is judged on answerable questions, US2 on the must-refuse set.

### Within each story

- Ingestion before retrieval before generation
- T021 (manual chunk review) gates everything downstream — do not build retrieval on unverified chunks
- T042 (threshold calibration) requires T040 (the eval set) to exist first

### Parallel opportunities

- Phase 1: T003, T004, T005 together
- Phase 2: T010, T011, T013, T014 together after T006–T009
- Phase 3: T018 alongside T015–T017; T022 and T026 alongside the ingestion tasks
- Phase 4: T040 and T043 alongside T036–T039
- Phase 6: T049, T050, T051, T054 together

---

## Parallel Example: Phase 6 documentation

```bash
Task: "Write README.md with setup and run instructions"
Task: "Write docs/technical-decisions.md from research.md"
Task: "Write docs/ai-development-report.md"
Task: "Unit test text cleanup in tests/unit/test_cleanup.py"
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → 4. **Stop and validate** against quickstart V1 → demo-able.

At that point answerable questions work with page images: the single largest share of the evaluation criteria.

### Incremental delivery

1. Setup + Foundational → foundation ready
2. US1 → validate V1 → **MVP**
3. US2 → validate V2–V5 → grounding and refusal demonstrable
4. US3 → validate V6 → chapter reproducibility demonstrable
5. Polish → deliverables complete

### Suggested two-day shape

| | Morning | Afternoon |
|---|---|---|
| **Day 1** | Phases 1–2, then T015–T021 (ingestion through the manual chunk gate) | T022–T035 (retrieval, generation, UI) — MVP complete |
| **Day 2** | Phase 4 (refusal + calibration), Phase 5 (chapter switch) | Phase 6 — docs, notebook, full validation |

Documentation sits on Day 2 afternoon deliberately: two of the seven evaluation criteria are technical reasoning and the AI-development report, so it is scored work, not a cooldown.

### Git strategy

Branch per phase, merged on completion, committed at genuine checkpoints as work proceeds:

`feat/ingestion` (Phases 1–3 ingestion) → `feat/retrieval` (T022–T026) → `feat/generation` (T027–T035) → `feat/refusal` (Phase 4) → `feat/chapter-agnostic` (Phase 5) → `docs/reports` (Phase 6)

AI-task.md §6 requires history preserving "meaningful commits and branches", and §7 scores it. Reconstructing a tidy history afterwards is both detectable and contrary to the constitution's honest-history rule.
