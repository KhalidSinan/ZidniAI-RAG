# Technical decisions

Significant choices, the alternatives considered, and what each trade-off
costs. Findings marked **measured** were obtained by running code against the
actual PDF; two of them reversed decisions made earlier on paper.

Fuller detail: [specs/001-data-chapter-rag/research.md](../specs/001-data-chapter-rag/research.md).

---

## 1. Chapter resolved by title from the TOC

**Decision.** Look the chapter up by name in the PDF's own table of contents;
derive its end from the next top-level entry.

**Why.** Hardcoded page numbers make the pipeline a one-off script. Resolving
from the document's structure is what lets `chapter.title` be the only thing
a user changes.

**Measured.** `Data` → pages 80–97, 8 spreads. `Programming techniques` →
98–117, 9 spreads. Both verified end to end.

**Alternatives.** Hardcoded ranges (rejected — no reproducibility); heading
detection by font size (rejected — the TOC is authoritative and already there).

**Note on numbering.** The brief says "chapter #6 (Data)"; the PDF says Data is
chapter 5. The title is treated as authoritative, and the number reading costs
one config value.

---

## 2. Visuals are whole pages, not cropped figures

**Measured, and this is the biggest trade-off in the project.**

- `page.get_images()` returns **one 2008×2400 bitmap per page**, bbox
  `Rect(0, 0, 552.7, 660.5)` — the whole page. Illustrations are baked in.
- `page.get_drawings()` returns ~80 objects per page, but these are **prepress
  registration marks**, mostly at negative coordinates outside the page. Not
  artwork.

An ink-minus-text segmentation prototype (render → threshold → mask text
bboxes → connected components) **did** isolate individual figures and produced
clean crops. But a sweep over the chapter returned 101 candidate figures where
~25–35 are real: it over-segments multi-part diagrams and needs column-aware
merging plus visual validation.

**Decision.** Serve whole page images, rendered once at 150 DPI.

**What this costs.** Precision. A page may show content beyond the answer's
scope. The brief asks for "reasonable effort", and a correct page is a
defensible answer where a wrong crop would be worse than none.

**Alternatives.** Ink-minus-text cropping (deferred — prototype works, needs
tuning time the deadline did not allow); a vision-language model to detect and
caption figures (rejected for ingest — adds a model dependency and
non-determinism); embedded image extraction (impossible here).

---

## 3. Chunking follows the book's typographic grammar

**Measured.** The book uses a strict design system, so `(font, size)` is a
near-perfect role classifier:

| Chars | Style | Role |
|---|---|---|
| 13,316 | MyriadPro-Light 9.0 | body prose |
| 6,504 | MyriadPro-Regular 8.0 | diagram labels + callout bodies |
| 5,427 | MyriadPro-LightSemiCn 9.0 | sidebar body |
| 1,500 | MyriadPro-Semibold 10.5 | spread standfirst |
| 787 | Semibold(Cond) 14.0 | section heading |
| 119 | MyriadPro-Regular 32.0 | spread title |

**Decision.** Derive the role table from each chapter's own histogram at
ingest time; chunk by spread → section heading; keep diagram labels in a
separate field.

**Why not a text splitter.** A fixed-size window scrambles these pages — a
spread interleaves prose, a `SEE ALSO` sidebar, an `IN DEPTH` box and diagram
labels. A window glues unrelated fragments together.

**Two things this got wrong first, and how they were found:**

1. **Block-level classification cannot see headings.** A section heading
   shares its text block with the prose beneath it, so the block's dominant
   role is always "body". Fixed by classifying at **line** level.
2. **Size banding promotes diagram numerals to headings.** Diagram figures are
   set at 18–19.5pt — above body, below the title — so "bigger than body means
   heading" turned `11000101` into a section heading. Fixed by matching the
   derived anchors **exactly** and treating everything off-anchor as a label.

**Result.** 44 passages, mean 704 characters, heading paths matching the
book's real sections (`Data › Binary code › Binary to decimal`). The same
derivation independently yields identical anchors (body 9.0 / heading 14.0 /
title 32.0) on the Programming techniques chapter.

**Cleanups.** Hyphenated line wraps rejoined; folios and letterspaced running
heads stripped; letterspaced sidebar badges (`I N D E P T H`, `R E A L
W O R L D`) removed mid-prose, with a 5-letter minimum so the encryption
spread's genuine cipher alphabet `A B C` survives.

---

## 4. Local embeddings via fastembed, not sentence-transformers

**Decision.** `fastembed` (ONNX Runtime) with `BAAI/bge-small-en-v1.5`.

**Why.** OpenRouter has no embeddings endpoint, so embedding is local either
way. `sentence-transformers` pulls PyTorch at ~2–2.5 GB, which threatens both
"set up from a clean checkout" and "cold ingest under 5 minutes" — most of the
budget spent downloading a deep-learning framework to embed 18 pages.

**Measured.** 519 MB total environment, **no PyTorch**. Model downloads in
~15 s, cold-loads in ~18 s, embeds 2 documents in 0.01 s. Vectors come back
`(n, 384)` float32 and **already L2-normalised** (norms = 1.0), so cosine is a
plain dot product and no normalisation step is needed.

**Alternatives.** `sentence-transformers` (rejected on weight, not quality);
a hosted embedding API (rejected — second network dependency and credential,
breaks offline reproducibility); TF-IDF only (rejected — fails plainly-worded
questions).

---

## 5. No vector database — reversed after measuring

**Decision.** Hold embeddings in one NumPy array; brute-force dot product.

**This reverses an earlier choice.** Chroma/FAISS was the initial sketch,
made before the corpus was measured. At **44 passages × 384 dimensions**,
brute force is a sub-millisecond matrix multiply and is *exact*, where an ANN
index is approximate and adds a dependency, a persistence format, and failure
modes — in exchange for speeding up something already instant.

**Where this flips.** Tens of thousands of vectors. The whole book is ~900
passages, still trivially brute-forceable.

---

## 6. Hybrid retrieval with RRF

**Decision.** Dense cosine + BM25 over `text + labels + heading_path`, fused
with Reciprocal Rank Fusion (k=60), top 5.

**Why.** The retrievers fail in complementary ways. Children ask plainly
("how do computers remember pictures?") where only semantics match; the
chapter is dense with exact tokens (`ASCII`, `LSB`, `11000101`) where lexical
match is decisive. RRF needs no score normalisation, which matters because
cosine and BM25 scores are not comparable.

**Alternatives.** Dense only (misses exact tokens); BM25 only (misses child
phrasing); weighted blending (needs normalising incomparable scales and tuning
a weight on no validation data); a cross-encoder reranker (a model and latency
for a 5-document shortlist).

---

## 7. The refusal gate uses cosine, not the fused score — corrected after measuring

**This was a design error caught by running it.**

The plan specified gating on the top **fused** score. That cannot work: RRF
scores depend only on *rank*, so the top result scores ~`1/(k+1)` whether it
is relevant or not. Measured:

| Question | Top fused score |
|---|---|
| "How does a computer store a letter?" | 0.0315 |
| "What did I eat for breakfast?" | 0.0296 |

Indistinguishable. Raw cosine is an absolute measure and separates cleanly:

| | max cosine |
|---|---|
| In-scope questions | 0.68 – 0.88 |
| Out-of-scope questions | 0.42 – 0.65 |

BM25 does **not** separate either — "Who won the World Cup?" scored 4.72
against "How are pictures stored?" at 4.04 — which independently confirms
cosine as the right gate signal.

**Decision.** RRF decides the **order**; max cosine decides **whether to
answer at all**.

### Calibration

| | value |
|---|---|
| Lowest answerable | 0.6811 — "How does a computer store a letter?" |
| Highest must-refuse | 0.6508 — "What is a search engine?" |
| **Threshold** | **0.66** |

The margin is narrow because search engines are semantically adjacent to
databases, which this chapter does cover. Result: **18/18** on the evaluation
set, 10/10 answerable passing and 8/8 must-refuse refusing.

**Limitation.** This threshold is calibrated for the Data chapter. Against
Programming techniques, 3 of 4 Data-specific questions correctly refuse, but
"What is binary code?" scores 0.6732 and passes — that chapter genuinely
covers machine code, so this is arguably correct rather than a miss. Any new
chapter should be re-calibrated with `eval --retrieval-only`.

---

## 8. Two grounding gates, the second deterministic

**Decision.**

1. **Pre-generation** — below-threshold cosine refuses without a network call.
2. **Post-generation** — parse `[C#]` markers; discard any outside the
   supplied set; if none remain, replace the answer with a refusal.

**Why.** Prompt-only grounding fails precisely where it is most tested:
weak-but-nonzero retrievals, where the model stretches. Gate 2 is plain string
matching and holds whether or not the model obeyed. Gate 1 also makes refusal
near-instant (measured: 1.1 s, no network) — valuable on a rate-limited tier.

**Alternatives.** Prompt instruction alone (no guarantee); LLM-as-judge
faithfulness check (doubles latency and cost, and makes the grounding
guarantee depend on the same unreliable component).

---

## 9. Three response types and a single rendering boundary

**Decision.** `Answer`, `Refusal`, `Trouble` — mutually exclusive — and one
`render.py` that accepts only those three.

**Why.** It makes the child-first rule structural rather than a matter of
discipline. None of the three can carry an exception, status code, model name
or provider name, so technical detail cannot reach the screen through that
door. `Trouble.detail` keeps the cause for reviewers and is never read by the
renderer. `render()` raises on an unknown type rather than formatting a repr.

It also keeps **"the book doesn't say"** and **"the system broke"** distinct in
the type system, not just in wording — an upstream failure can never be
rendered as a refusal.

---

## 10. Direct HTTP to OpenRouter, no SDK or framework

**Decision.** `httpx` against the chat-completions endpoint, with exponential
backoff on 429/5xx, a timeout, and bounded retries.

**Why.** One documented endpoint needs no SDK. The mandated model is on a free
tier where 429s are routine, so retry behaviour is product behaviour and
belongs in sight rather than in a client's defaults.

**Alternatives.** The `openai` SDK pointed at OpenRouter (viable; an
unnecessary dependency for one endpoint); LangChain / LlamaIndex (rejected —
their abstractions would obscure exactly the retrieval and grounding decisions
this work is judged on, and their chunking defaults are wrong for this
document).

---

## 11. Caching keyed on content plus pipeline version

**Decision.** `cache_key = sha256(pdf_sha256 + chapter_title + pipeline_version)`.

**Why.** Including `pipeline_version` means a chunker change invalidates stale
artifacts automatically. Without it, a reviewer editing the chunker would
silently get old output — a worse failure than a slow rebuild. This was used
twice during development, bumping 1 → 2 → 3 as cleanup rules changed.

**Measured.** Cold ingest 13 s; cached start 0.1 s.

---

## 12. Licensing

**PyMuPDF is AGPL-3.0** (or commercial). Unproblematic for an assessment, a
real constraint on downstream commercial use, and worth stating rather than
leaving for someone to discover.

Its text-with-coordinates API and page rendering are exactly what the
typographic chunker needs. `pypdfium2` (BSD) renders well but exposes a much
weaker structured-text API, which would mean rebuilding the span/font analysis
this design depends on.

---

## Summary of reversals

Two decisions changed once code met the document. Both are recorded here
rather than quietly amended, because the reasoning is the useful part:

| Decision | On paper | After measuring |
|---|---|---|
| Vector store | Chroma / FAISS | NumPy brute force — corpus is 44 vectors |
| Refusal gate | Threshold on fused RRF score | Threshold on max cosine — RRF is rank-based and near-constant |

---

## 13. The mandated model is no longer available free (found during live evaluation)

**Discovered 2026-10-18**, on the first real API call.

`meta-llama/llama-3.3-70b-instruct:free` returns **HTTP 404**:

> This model is unavailable for free. The paid version is available now — use
> this slug instead: `meta-llama/llama-3.3-70b-instruct`

Confirmed against the OpenRouter catalogue: of 16 models currently offering a
`:free` tier, **none** is a Llama 3.3 variant. The supplied key reports
`total_credits: 0`, so the paid slug returns a billing error.

**Decision.** `config.yaml` keeps the **mandated** model as the active value,
because the brief fixes it and the constitution lists it under Mandated
Constraints. A commented one-line substitute is provided directly above it for
anyone running without credits.

**What this costs.** The system cannot generate answers out of the box on a
credit-less account. Resolving it is either adding ~$1 of credit, or changing
one line.

**Evaluation substitute.** To evaluate the pipeline end to end,
`nvidia/nemotron-3-super-120b-a12b:free` was used temporarily. It works, but
it is throttled: roughly half of requests return HTTP 200 with an **empty
body**. That is a property of the free tier, not of the pipeline — and it
exposed a real defect (see below).

### Defect found by live evaluation: empty response was treated as a refusal

`build_response()` collapsed "empty text" and "no citations" into the same
branch, so a provider returning 200-with-empty-content produced a **Refusal** —
telling the child the book does not cover something it does cover. That is
precisely what FR-020 and SC-012 forbid.

Fixed: an empty or whitespace-only response now returns `Trouble`. Two
regression tests cover it. This is the clearest argument for the
three-response-type design — the bug was a single misrouted branch, and once
corrected the failures reported honestly as service problems instead of
polluting the grounding metric.

### Live evaluation result (substitute model)

| | Result |
|---|---|
| Must-refuse questions | **8/8 refused** |
| Answerable questions | 5/10 answered, 5 hit empty-response `trouble` |
| Page images on answers | Correct spread in every answered case |
| Faithfulness (spot-check) | Near-verbatim to source, simplified to direct address |

The 5 failures are upstream throttling, not grounding failures — the runner
reports them separately for exactly this reason.

---

## 14. Cross-encoder reranking — adopted after measuring

**Problem.** RRF fuses two rankings, but neither retriever reads the question
and the passage *together*. "How does a computer store a letter?" retrieved no
relevant passage in the top 5: the answer is spread across "Binary code ›
Language of computers" and "Bits and digitization › 0 or 1", which RRF ranked
5th and 6th behind passages that merely share words.

**Decision.** After RRF, every candidate (the union of the dense and BM25 top
10, ~15–20 passages) is rescored by a cross-encoder and the best `top_k` kept.
RRF still chooses the *candidates*; the cross-encoder chooses the *order*.
It runs on fastembed's ONNX runtime like the embedder — no PyTorch, no extra
network call. Switch: `retrieval.reranker` in `config.yaml` (`""` disables);
`kidsrag eval --retrieval-only --reranker off|<model>` compares on one run.

**Measurement.** The eval set gained `relevant:` passage labels for every
answerable question, plus 8 harder paraphrased or narrow ones ("How can two
people share secret messages without meeting?"), giving 18 ranked questions:

| Reranker | hit@1 | hit@5 | MRR |
|---|---|---|---|
| none (RRF only) | 13/18 | 17/18 | 0.815 |
| `Xenova/ms-marco-MiniLM-L-6-v2` (80 MB) — **chosen** | **17/18** | **18/18** | **0.972** |
| `Xenova/ms-marco-MiniLM-L-12-v2` (120 MB) | 17/18 | 18/18 | 0.972 |
| `jinaai/jina-reranker-v1-turbo-en` (150 MB) | 16/18 | 18/18 | 0.921 |

L-12 ties L-6 at 1.5× the size, so the smaller model wins. `bge-reranker-base`
(1 GB) was not completed: nothing was left to gain over a 18/18 hit rate.

**Cost.** ~1.2 s per answered question on CPU (~70 ms per candidate; long
passages run to the 512-token limit). Against a ~9 s model call that is
acceptable. The reranker is **skipped when the gate refuses**, because a
refusal never uses the order — refusals stay instant.

**Caveat.** 18 questions, labelled by the developer. Four extra first-place
hits is a clear direction, not a statistically strong result.

### Not adopted: HyDE and multi-query retrieval

Both rewrite the question with the LLM before retrieval. With 44 passages,
recall was not the problem (17/18 already in the top 5). Both add a paid,
multi-second model call per question, and HyDE actively undermines the refusal
gate: the model writes a plausible paragraph even for out-of-chapter
questions, and that paragraph *does* resemble the chapter, raising the cosine
the gate depends on.

### Finding: the cosine gate overlaps on harder questions

The 8 new answerable questions exposed a limit of section 7's calibration.
Two in-chapter questions now fall *below* the threshold and are refused:

| Question | max cosine |
|---|---|
| How many pictures does a film show every second? | 0.6259 |
| What makes a song sound better or worse on a computer? | 0.6511 |
| *highest must-refuse: What is a search engine?* | *0.6508* |

The bands overlap, so no single cosine threshold separates them. The
cross-encoder score was tested as an alternative gate and **does not separate
either** — "How can two people share secret messages without meeting?"
(answerable) scores −6.52 while "What is a compiler?" (must-refuse) scores
−3.27. The gate is left unchanged: it still refuses 8/8 must-refuse questions,
and wrongly refusing is the safer failure for a child (a kind "not in this
part of the book" versus an invented answer). Tuning a combined rule on 26
questions would be fitting noise; a larger labelled set is the real fix.

---

## 15. Citations with printed page numbers and supporting quotes

**Decision.** Answers show footnotes `[1] [2]` that link to a "Where I found
this" list: section name, page, and one verbatim sentence from the cited
passage. The answer contract already allowed "footnote-style references".

- **Numbering** follows reading order, not retrieval rank: the first source
  the child meets is [1]. Markers that failed the grounding gate are dropped
  before numbering (`render.number_citations`).
- **The quote** is the sentence of the cited passage most similar (local
  embedder) to the answer sentences that cite it (`generate/evidence.py`). It
  is the book's own text, so it cannot add anything the book does not say. If
  embedding fails the first sentence is used — a weaker quote, never a lost
  answer.
- **Printed page numbers.** The PDF's page index runs two ahead of the
  printed numbers (PDF page 82 is printed "80"). Citing the PDF index would
  send a child holding the book to the wrong page. Passages now store the
  PDF's own page labels (`page_labels`, `image_labels`), captured at ingest
  from `page.get_label()`; `pipeline_version` went to 4 so cached chapters
  rebuild. The reviewer panel keeps PDF indices, labelled as such.
