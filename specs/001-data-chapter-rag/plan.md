# Implementation Plan: Document-Grounded RAG for the "Data" Chapter

**Branch**: `001-data-chapter-rag` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-data-chapter-rag/spec.md`

**Constitution**: [v1.0.0](../../.specify/memory/constitution.md)

## Summary

A five-stage, file-backed RAG pipeline over one chapter of a visual children's book, answering a
child's questions in the book's own vocabulary and refusing honestly when the chapter does not
cover the question.

The technical approach is shaped by three measured properties of the source PDF (see
[research.md](./research.md)): the text layer is clean and richly structured by typography, every
page is a single full-page bitmap with no separately addressable figures, and the target chapter is
small — 18 pages, 8 topic spreads, roughly 40–70 passages. That last fact drives the central
simplification: at this corpus size exact brute-force vector search in NumPy beats any vector
database on both latency and setup cost, so no database is introduced.

Chunking follows the book's own typographic grammar rather than a token window; visuals are served
as whole page images; grounding is enforced twice, once by a pre-generation score gate and once by
a deterministic post-generation citation check that does not depend on the model obeying
instructions.

## Technical Context

**Language/Version**: Python 3.12.13 (pinned — broadest wheel availability for `onnxruntime`; the
machine's default 3.13 is newer than some binary wheels). **Installed and verified.**

**Primary Dependencies** — all installed into `.venv` and import-verified on 2026-10-18:

| Purpose | Choice | Version |
|---|---|---|
| PDF text + page rendering | PyMuPDF (import as `pymupdf`, not the deprecated `fitz`) | 1.28.2 |
| Embeddings (local) | `fastembed` with `BAAI/bge-small-en-v1.5` | 0.9.0 |
| Embedding runtime | `onnxruntime` | 1.31.0 |
| Lexical retrieval | `rank-bm25` | installed |
| Vector math | NumPy | 2.5.4 |
| LLM transport | `httpx` | 0.28.1 |
| Interface | Gradio | 6.30.0 |
| Notebook | JupyterLab | installed |
| Config / secrets | PyYAML, `python-dotenv` | installed |
| Tests | pytest | installed |

**Verified environment facts** (measured, not assumed):

- Total venv size **519 MB**, with **no PyTorch** — confirming the `fastembed` rationale in
  research §5. A `sentence-transformers` environment would be roughly 5× larger.
- Embedding model downloads in ~15 s and loads in ~18 s cold; subsequent loads use the local cache.
- Embedding throughput: 2 documents in 0.01 s. Embedding 40–70 passages is effectively free.
- Output vectors are **already L2-normalised by `fastembed`** (measured norms = 1.0), so cosine
  similarity is a plain dot product and no normalisation step is needed.
- Exact versions pinned in `requirements.txt` (140 packages).

**Storage**: Filesystem only, under `artifacts/{chapter_slug}/` — JSONL passages, a `.npy` embedding
matrix, PNG page images, and a `manifest.json`. No database.

**Testing**: pytest for unit and contract tests; a YAML evaluation set driving an end-to-end check
of answerable and must-refuse behaviour.

**Target Platform**: Local desktop, cross-platform. Developed on Windows 11.

**Project Type**: Single project — an importable library with a thin CLI and a local web UI.

**Performance Goals**: Query round-trip under 15 s (SC-009); cold ingest under 5 min, warm start
under 30 s (SC-010).

**Constraints**: Ingestion, indexing and retrieval MUST work offline; the network is used only for
answer generation. The mandated model runs on a rate-limited free tier, so transient upstream
failure is a normal operating condition.

**Scale/Scope**: One chapter at a time — 18 pages, 8 spreads, ~40–70 passages, ~18 page images,
single local user.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | Gate | Pre-Phase 0 | Post-Phase 1 |
|---|---|---|---|---|
| I | Child-First Experience | No technical text on any child-facing surface; UI has large type, spacing, contrast | PASS | PASS |
| II | Grounded or Silent | At least one grounding check independent of model instruction-following | PASS | PASS |
| III | The Book's Voice | Tone derived from retrieved passages; address/vocabulary precedence encoded in the prompt | PASS | PASS |
| IV | Show the Page | Page image accompanies answers; missing image degrades to text-only | PASS | PASS |
| V | Chapter-Agnostic Pipeline | Chapter is one config value; stages independently runnable | PASS | PASS |
| VI | Fail Gently, Fail Clearly | Refusal and failure are distinct types; no unhandled path reaches the child | PASS | PASS |
| — | Mandated Constraints | Fixed model for generation; processed output reused; setup documented | PASS | PASS |

**How the design satisfies the two non-negotiables:**

- **Principle I** is enforced structurally, not by discipline. Child-facing text can only reach the
  screen through a single rendering layer that accepts a typed `Answer`, `Refusal`, or `Trouble`
  object — none of which can carry an exception, status code, or provider name. The reviewer-facing
  inspection panel is a separate component fed by a separate type.
- **Principle II** is enforced twice, with the second check deterministic: the pre-generation score
  gate refuses before the model is ever called, and the post-generation citation check parses the
  returned text for valid passage ids and substitutes a refusal if none are present. The second
  check is plain string work and cannot be talked out of by a non-compliant model.

**Deviations**: one, tracked in [Complexity Tracking](#complexity-tracking).

## Project Structure

### Documentation (this feature)

```text
specs/001-data-chapter-rag/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── config.schema.md
│   ├── pipeline-cli.md
│   └── answer-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/kidsrag/
├── config.py              # Config dataclass + YAML loader; chapter name lives here
├── errors.py              # PipelineError, UpstreamError, ChapterNotFound
├── models.py              # Entity + response dataclasses (see data-model.md)
├── ingest/
│   ├── pdf.py             # open document, parse TOC, resolve chapter by title
│   ├── roles.py           # derive (font,size) -> role table from the chapter
│   ├── text.py            # spread grouping, heading chunking, cleanup
│   ├── pages.py           # render page PNGs
│   └── build.py           # stage orchestrator -> artifacts/
├── index/
│   ├── embed.py           # fastembed wrapper
│   ├── store.py           # load/save passages + vectors + manifest
│   └── retrieve.py        # dense + BM25, RRF fusion, score gate
├── generate/
│   ├── prompt.py          # system prompt, few-shot, context assembly
│   ├── llm.py             # OpenRouter client, retry/backoff, timeout
│   └── answer.py          # citation post-check, Answer/Refusal/Trouble results
├── render.py              # the single child-facing text surface (Principle I)
├── app.py                 # Gradio UI
└── cli.py                 # per-stage entry points (Principle V)

tests/
├── unit/                  # role table, cleanup, RRF, citation parsing
├── contract/              # config schema, answer contract
└── eval/
    ├── questions.yaml     # answerable + must-refuse fixtures
    └── test_eval.py

notebooks/
└── 01_pipeline.ipynb      # the five stages, in order, using src/kidsrag

docs/                      # repo-level deliverables (AI-task.md §4, §6)
├── technical-decisions.md # decision rationale + alternatives + trade-offs
└── ai-development-report.md  # AI-assisted development workflow report

artifacts/                 # generated; git-ignored except .gitkeep
└── data/                  # per-chapter output

README.md                  # setup instructions, how to run, project tour
config.yaml                # the single chapter switch
requirements.txt           # pinned dependency specification (generated)
pyproject.toml             # package metadata + dev extras
.env.example               # documents OPENROUTER_API_KEY; real .env git-ignored
```

**Structure Decision**: Single project. The pipeline is a library (`src/kidsrag/`) with two thin
entry points — `cli.py` for stage-by-stage execution and `app.py` for the child-facing UI — plus a
notebook that imports the same library rather than duplicating it. This directly serves Principle V
(each stage independently runnable) and keeps the notebook honest: it demonstrates the shipped code
instead of a parallel copy.

The `render.py` module exists specifically to make Principle I structural. It is the only module
permitted to produce child-facing strings, which makes "did technical text leak?" a question
answerable by inspecting one file.

## Brief Coverage Check

*GATE: every requirement and deliverable in [AI-task.md](../../AI-task.md) maps to something in
this plan. Checked 2026-10-18; this pass found and closed three gaps, marked ⚠ below.*

### §2 Product Requirements

| Requirement | Where satisfied |
|---|---|
| Document grounding; state when unanswerable | FR-015/FR-016/FR-018; two gates (research §8); `Refusal` type |
| Language and tone reflect the book and audience | FR-001/FR-019; prompt contract; constitution I & III |
| Reasonable effort to present relevant images | FR-021/FR-022; whole-page images (research §3) |

### §3 Implementation Requirements

| Requirement | Where satisfied |
|---|---|
| Complete pipeline, ingestion → generation | Five stages; `src/kidsrag/{ingest,index,generate}` |
| Clear, isolated, reproducible across chapters | FR-012/FR-013; `cli.py` per-stage commands; `config.yaml` |
| Testing interface for questions + retrieved content | FR-023/FR-024; `app.py`; `ask --show-retrieval` |
| Mandated OpenRouter model | `config.yaml` `generation.model`; constitution Mandated Constraints |
| Document rationale, alternatives, trade-offs | `docs/technical-decisions.md` ⚠ *(was missing)* |

### §4 AI-Assisted Development

| Requirement | Where satisfied |
|---|---|
| Markdown report: workflow, context given to agents, delegated tasks, review and validation | `docs/ai-development-report.md` ⚠ *(was missing)* |

### §5 Non-Functional

| Requirement | Where satisfied |
|---|---|
| Reliability — graceful processing and retrieval failure | FR-026/FR-027; `Trouble` type; CLI exit codes |
| Consistency — factual consistency, uniform grounding | `temperature: 0.2`; one grounding path for all queries |
| Performance — responsive, no repeated processing | FR-028; manifest cache key (research §11); SC-009/SC-010 |
| Reproducibility — documented dependencies and setup | `README.md` ⚠ *(was missing)*, `requirements.txt`, quickstart |

### §6 Deliverables

| Deliverable | Artifact |
|---|---|
| Complete implementation + runnable notebook | `src/kidsrag/`, `notebooks/01_pipeline.ipynb` |
| Pipeline organised for independent execution and inspection | `cli.py` five commands; `inspect` |
| Simple question-answering interface | `app.py` (Gradio) |
| Setup instructions + dependency specifications | `README.md`, `requirements.txt`, `pyproject.toml` |
| AI-assisted development report + decision rationale | `docs/ai-development-report.md`, `docs/technical-decisions.md` |
| Git history with meaningful commits **and branches** | Branch per stage; commits at real checkpoints — see note below |

**Git history is a deliverable, not a by-product.** Branches: `feat/ingestion` → `feat/indexing`
→ `feat/generation` → `feat/interface` → `docs/reports`, each merged on completion, with commits
made as work actually progresses. Reconstructing a tidy history afterwards is both detectable and
contrary to the constitution's "honest history" rule.

## Complexity Tracking

Two kinds of entry: complexity deliberately added because a brief requirement demands it, and
simplicity deliberately accepted at a cost. Both are recorded so neither reads as an oversight.

### Justified complexity

| Decision | Why needed | Simpler alternative rejected because |
|---|---|---|
| Reviewer-facing inspection panel uses technical language — a scoped exception to Principle I | §3 requires an interface for "inspecting generated answers and relevant retrieved content"; scores and passage ids are inherently technical | Child-friendly wording would make retrieval unauditable and defeat the requirement. Mitigated: separate component, separate data type, never mixed into the answer surface. |
| Typographic role table derived per chapter, instead of a standard text splitter | §3 demands chapter-level reproducibility, and this layout scrambles under fixed-size windows (research §4) | A character/token splitter is simpler but demonstrably interleaves prose, sidebars and diagram labels, degrading both retrieval and answer faithfulness (§7 criterion 1). |
| Two grounding gates rather than one prompt instruction | §2 grounding and §7 "handling of unsupported questions" are scored separately; prompt-only grounding fails on weak-but-nonzero retrievals | A single prompt instruction is simpler but offers no guarantee when the model disobeys. Gate 2 is deterministic string matching and cannot be talked around. |
| Hybrid retrieval with RRF rather than dense-only | Chapter is jargon-dense (`ASCII`, `LSB`, `11000101`) where embeddings are weak, while children ask in plain words | Dense-only is simpler but misses exact tokens; BM25-only misses child phrasing. Both failure modes are visible in §7 criterion 1. |

### Accepted simplifications

| Decision | What is given up | Why acceptable |
|---|---|---|
| Whole-page images instead of cropped figures | Precision against §2 "retrieve and present relevant images" and §7 criterion 3 | §2 asks for *reasonable effort*. The PDF has no separately addressable figures (research §3); a working crop prototype exists but over-segments and needs validation time the deadline does not allow. A correct page is a defensible answer; a wrong crop is worse than none. |
| No vector database — NumPy brute force | Nothing measurable at 40–70 passages | Exact search, sub-millisecond, one fewer dependency and persistence format. Adding an ANN index would be complexity serving no principle. |
| No automated faithfulness scoring | Machine-checkable answer quality | §7 criterion 1 is judged by a human reviewer anyway. Refusal behaviour — the binary, regression-prone half — *is* automated in `eval`. |
| Single chapter ingested at a time | Cross-chapter questions | §1 requires one chapter. Multi-chapter ingest would also weaken the must-refuse tests, which depend on other chapters being out of scope. |
