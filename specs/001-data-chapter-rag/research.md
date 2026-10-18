# Phase 0 Research: Document-Grounded RAG for the "Data" Chapter

**Date**: 2026-10-18 | **Plan**: [plan.md](./plan.md)

Findings below marked **measured** were obtained by running extraction code against the actual
source PDF during planning. Findings marked **assessed** are judgement calls from known properties
of the libraries involved, with a verification task attached where the risk is material.

---

## 1. Source document structure

**Measured.** `Help Your Kids with Computer Science`, 258 pages, 122 TOC entries.

| Property | Value |
|---|---|
| "Data" chapter range | PDF pages 80–97 (18 pages) |
| Topic spreads in chapter | 8 (Bits and digitization, Binary code, ASCII and unicode, Logic gates, Databases, Encoding images, Encoding audio and video, Encryption) |
| Page size | 552.8 × 660.5 pt |
| Text per page | ~2,000–2,600 characters |
| Text layer quality | Clean Unicode, including `▷`/`▽` callout markers. No OCR needed. |

**Decision**: Resolve the chapter by title from the embedded TOC, deriving the end of the range
from the next top-level entry.

**Rationale**: Satisfies FR-005/FR-012 and makes chapter switching a one-value change. Hardcoded
page numbers would silently break on any other chapter.

**Alternatives considered**: Hardcoded ranges (rejected — violates Principle V); heading detection
by font size alone (rejected — the TOC is authoritative and already present).

---

## 2. The chapter numbering conflict

**Measured.** The brief says "chapter number #6 (Data)". The PDF's own TOC says `5 Data` and
`6 Programming techniques`.

**Decision**: Treat the chapter *title* as authoritative; target "Data". Make the numbering
interpretation reachable by changing one config value.

**Rationale**: The title is unambiguous where the number is not, and FR-012 makes being wrong
cheap — the other chapter is one line away.

**Alternatives considered**: Targeting chapter 6 by number (rejected — contradicts the brief's own
parenthetical); ingesting both chapters (rejected — doubles ingest time for no scored benefit, and
muddies the refusal tests, which depend on other chapters being *out* of scope).

---

## 3. Visual content: how figures are stored

**Measured, and this reversed an earlier assumption.**

- `page.get_images()` returns exactly **one 2008×2400 bitmap per page**, whose bounding box is
  `Rect(0, 0, 552.7, 660.5)` — the entire page. Every illustration is baked into it.
- `page.get_drawings()` returns ~80 objects per page, but inspection showed these are **prepress
  registration marks**, mostly at negative coordinates outside the page. They are not artwork.

An ink-minus-text segmentation prototype (render → threshold → mask text bboxes → connected
components) did successfully isolate individual figures, producing clean crops. But a sweep over
the chapter returned 101 candidate figures where ~25–35 are real, i.e. it over-segments multi-part
diagrams, and it needs column-grid-aware merging plus visual validation to be trustworthy.

**Decision**: Serve **whole page images** as the visual unit. Render each chapter page once at
150 DPI to PNG.

**Rationale**: The brief asks for "reasonable effort" on visuals, and a correctly selected page
satisfies FR-021 while removing the single largest schedule risk. The segmentation work is
real but unfinished, and two days does not accommodate finishing *and* validating it.

**Alternatives considered**: Ink-minus-text cropping (deferred — working prototype exists, needs
merge tuning and a contact-sheet review; the natural first enhancement if time permits); a
vision-language model to detect and caption figures (rejected for ingest — adds a model dependency
and non-determinism; permitted by the brief, which fixes the model only for generation); embedded
image extraction (impossible here — returns the whole page).

**Residual risk**: A page image shows content beyond the answer's scope. Accepted — the alternative
is showing nothing.

---

## 4. Chunking strategy

**Measured.** The book uses a consistent typographic design system. Across the Data chapter,
`(font, size)` pairs map cleanly to semantic roles:

| Chars | Font / size | Role |
|---|---|---|
| 13,316 | MyriadPro-Light 9.0 | body prose |
| 6,504 | MyriadPro-Regular 8.0 | diagram labels |
| 5,427 | MyriadPro-LightSemiCn 9.0 | sidebar body (`IN DEPTH`) |
| 2,464 | MyriadPro-SemiCn 7.2 | captions / small labels |
| 1,500 | MyriadPro-Semibold 10.5 | spread standfirst |
| 658 / 226 | Bold 8.0 / BlackCond 7.0 | callout titles |
| 505 / 282 | Semibold(Cond) 14.0 | section heading |
| 119 | MyriadPro-Regular 32.0 | spread title |
| 113 | AndaleMonoMTStd-Bold 8.5 | code |

**Decision**: Derive the role table at ingest time from the chapter's own `(font, size)` histogram
(cluster, rank by character volume, assign by rank and page position). Chunk by **spread → section
heading**, prepending the heading path. Keep diagram labels in a separate `labels` field on the
passage rather than inlining them into prose.

**Rationale**: A fixed-size token window scrambles these pages — a spread interleaves prose, a
cross-reference sidebar, an `IN DEPTH` box and diagram labels, so a naive window glues unrelated
fragments together. Deriving the table rather than hardcoding it is what makes the chunker work on
other chapters (Principle V). Separating labels keeps the dense vector clean while still letting
BM25 match exact strings like `11000101`.

**Alternatives considered**: Fixed-size overlapping windows (rejected — demonstrably scrambles
this layout); one chunk per page (rejected — splits topics that span a spread); one chunk per
spread (rejected — too coarse, ~2,500 words dilutes retrieval); semantic chunking via an embedding
model (rejected — slower, non-deterministic, and strictly worse than structure the document
already encodes).

**Cleanups required** (all observed in extracted text): strip folios and letterspaced running
heads (`82\nD ATA\n82`); rejoin hyphenated line wraps (`digitiza-\ntion`); hold `SEE ALSO`
cross-reference blocks as metadata rather than prose.

---

## 5. Embeddings

**Assessed.** No embeddings endpoint exists on OpenRouter, so embedding must be local regardless.

**Decision**: `fastembed` with `BAAI/bge-small-en-v1.5` (384-dim).

**Rationale**: `fastembed` runs on ONNX Runtime and pulls no PyTorch. The usual alternative,
`sentence-transformers`, drags in torch at roughly 2–2.5 GB, which directly threatens SC-011
(reviewer sets up from a clean checkout) and SC-010 (cold ingest under 5 minutes) — most of that
budget would be spent downloading a deep learning framework to embed 18 pages of text.
`bge-small-en-v1.5` is strong on short-passage retrieval at ~130 MB of ONNX weights.

**Alternatives considered**: `sentence-transformers` (rejected on dependency weight, not quality);
a hosted embedding API (rejected — adds a second network dependency and a second credential, and
breaks offline reproducibility); TF-IDF only (rejected — fails plainly-worded child questions that
share no vocabulary with the text).

**Verified 2026-10-18** — this is no longer an assessment. Installed into `.venv` on Python
3.12.13 and exercised end to end:

| Check | Result |
|---|---|
| `onnxruntime` wheel on Python 3.12 | Installs cleanly, v1.31.0 |
| `fastembed` | v0.9.0, imports |
| PyTorch present? | **No** — confirming the dependency-weight rationale |
| Total venv size | **519 MB** (a `sentence-transformers` env would be roughly 5×) |
| Model download + cold load | ~15 s download, ~18 s total; cached thereafter |
| Embedding throughput | 2 documents in 0.01 s — embedding 40–70 passages is free |
| Output | `(n, 384)` float32, **L2-normalised already** (measured norms = 1.0) |

Two consequences for the design:

- No normalisation step is needed before cosine similarity; it is a plain dot product.
- Python 3.12 is confirmed as the right pin. The machine's default 3.13 was not needed, and the
  `sentence-transformers` fallback is no longer on the critical path.

**Incidental finding**: PyMuPDF's `import fitz` entry point is deprecated and warns on import.
Code MUST use `import pymupdf` instead.

---

## 6. Vector storage — a reversal from the initial sketch

**Measured corpus size**: ~40–70 passages for the chapter.

**Decision**: No vector database. Hold embeddings in a single NumPy array and compute exact cosine
similarity by brute force.

**Rationale**: This reverses the Chroma/FAISS choice sketched before the corpus was measured. At
40–70 vectors of 384 dimensions, brute force is a sub-millisecond matrix multiply and is *exact*,
whereas an ANN index is approximate, adds a dependency, adds a persistence format, and adds
failure modes — in exchange for a speedup on a workload that is already instant. Introducing one
here would be ceremony, and Principle V's governance note rejects complexity that serves no
principle.

**Alternatives considered**: Chroma (rejected — persistence layer and client/server surface for a
corpus that fits in 100 KB of RAM); FAISS (rejected — same, plus platform-specific wheels);
SQLite with a vector extension (rejected — same reasoning, plus setup friction on Windows).

**Honest note**: This decision flips if the system were ever pointed at the whole book
(~250 pages, ~900 passages). Still trivially brute-forceable, in fact — the threshold is tens of
thousands of vectors, which this project will never approach.

---

## 7. Retrieval: hybrid fusion

**Decision**: Dense cosine + BM25 over `text + labels + heading_path`, fused with Reciprocal Rank
Fusion (k=60), returning top-5.

**Rationale**: The two retrievers fail in complementary ways on this corpus. Children ask
plainly ("how do computers remember pictures?") where only semantics match; the chapter is also
dense with exact tokens (`ASCII`, `LSB`, `11000101`, `lossy`) where lexical match is decisive and
embeddings are weak. RRF needs no score normalisation between the two, which matters because
cosine and BM25 scores are not comparable.

**Alternatives considered**: Dense only (rejected — misses exact technical tokens); BM25 only
(rejected — misses child phrasing); weighted score blending (rejected — requires normalising
incomparable score scales and tuning a weight, on no validation data); a cross-encoder reranker
(rejected — adds a model and latency for a 5-document shortlist).

---

## 8. Refusal mechanism

**Decision**: Two independent gates.

1. **Pre-generation score gate** — if the top fused score falls below threshold, refuse without
   calling the model.
2. **Post-generation citation check** — parse the answer for valid `[C#]` passage ids; if none are
   present, discard the answer and return a refusal.

**Rationale**: Principle II requires at least one check that does not depend on the model obeying
instructions, and gate 2 is plain string matching. Gate 1 additionally saves a network call and
makes refusal latency near-zero, which matters on a rate-limited free tier. Prompt-only grounding
fails exactly where it is most tested: weak-but-nonzero retrievals, where the model is tempted to
stretch.

**Alternatives considered**: Prompt instruction only (rejected — violates Principle II); an
LLM-as-judge faithfulness check (rejected — doubles latency and cost on a rate-limited free tier,
and makes the grounding guarantee depend on the same unreliable component).

**Open calibration item**: The score threshold has no principled default. It will be set
empirically against the evaluation set, choosing the lowest value at which all must-refuse
questions refuse, then sanity-checked so no answerable question is lost. This is a tuning task,
not a design unknown.

---

## 9. Generation transport

**Decision**: Call OpenRouter's chat completions endpoint directly over `httpx`, with exponential
backoff on 429/5xx, a request timeout, and a bounded retry count.

**Rationale**: One HTTP call against a documented endpoint needs no SDK. The mandated model is on
a free tier where 429s are routine rather than exceptional, so retry behaviour is product
behaviour (Principle VI), and owning the transport makes it explicit instead of buried in a
client's defaults.

**Alternatives considered**: The `openai` SDK pointed at OpenRouter's base URL (viable, rejected as
an unnecessary dependency for a single endpoint); LangChain or LlamaIndex (rejected — a framework
whose abstractions would obscure exactly the retrieval and grounding decisions this assessment
scores, and whose chunking defaults are wrong for this document).

---

## 10. Tone and audience

**Decision**: Derive tone primarily from retrieved passages, reinforced by a short style directive
and two few-shot pairs written in the book's register. Encode FR-019's precedence rule explicitly
in the system prompt: address the child directly, keep the book's vocabulary.

**Rationale**: The retrieved context already carries the book's voice, and a 70B instruction-tuned
model mirrors register well when the exemplar is in front of it. The precedence rule must be
stated because the source conflicts with the product: the book's title addresses a *parent*
("Help Your Kids…") while the product addresses the *child*. Left implicit, this resolves
differently from one answer to the next and the tone criterion scores inconsistently.

**Alternatives considered**: Fine-tuning (absurd at this scale); a post-hoc readability rewrite
pass (rejected — a second model call per query on a rate-limited tier, risking the grounding
established by the first).

---

## 11. Caching

**Decision**: Key the artifact directory on `hash(pdf_sha256 + chapter_name + pipeline_version)`.
On start, if a manifest with a matching key exists, load it and skip ingest.

**Rationale**: Satisfies FR-028 and SC-010. Including `pipeline_version` means chunker changes
invalidate stale artifacts automatically — without it, a reviewer editing the chunker would get
silently stale output, which is a worse failure than a slow rebuild.

**Alternatives considered**: Timestamp comparison (rejected — misses code changes); no cache
(rejected — violates FR-028); caching individual LLM responses (deferred — useful for demo
stability, but not required and risks masking inconsistency during evaluation).

---

## 12. Licensing note

**Assessed.** PyMuPDF is AGPL-3.0 (or commercial). For an assessment submission this is
unproblematic, but it is a real constraint on any downstream commercial use and should not pass
unmentioned.

**Decision**: Use PyMuPDF, and record the licence in the technical-decisions document.

**Rationale**: Its text-with-coordinates API and page rendering are exactly what the typographic
chunker and page-image renderer need. `pypdfium2` (BSD) renders well but exposes a much weaker
structured-text API, which would mean rebuilding the span/font analysis this design depends on.

**Alternatives considered**: `pypdfium2` (rejected — insufficient text structure API);
`pdfplumber` (rejected — no page rasterisation, slower on this document); `pypdf` (rejected — no
rendering, weak layout data).

---

## Resolved unknowns

| Unknown | Resolution |
|---|---|
| Are figures separately extractable? | No — one full-page bitmap per page; whole-page images chosen |
| What is the right chunk unit? | Spread → section heading, via a derived typographic role table |
| Embeddings local or hosted? | Local; OpenRouter offers no embeddings endpoint |
| Which vector store? | None — NumPy brute force, corpus is 40–70 vectors |
| How is grounding guaranteed? | Two gates, the second deterministic and model-independent |
| Which chapter is the target? | "Data" by title (chapter 5 here), configurable |

## Remaining risks

| Risk | Severity | Mitigation |
|---|---|---|
| ~~`onnxruntime` wheels unavailable~~ | ~~Medium~~ | **Resolved 2026-10-18** — installed and verified on Python 3.12.13 |
| Free-tier rate limiting during demo or evaluation | Medium | Retry with backoff; child-appropriate trouble message; refusal path needs no network |
| Score threshold mis-calibrated, over- or under-refusing | Medium | Calibrate against the evaluation set; both directions are measurable (SC-001, SC-002) |
| Page image shows content beyond the answer's scope | Low | Accepted trade-off of the whole-page decision |
