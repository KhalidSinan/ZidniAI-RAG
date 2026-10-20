# AI-assisted development report

Required by AI-task.md §4: the workflow, the context given to the AI, what was
delegated, and how the output was reviewed and validated.

---

## Workflow

Development used **Claude Code** as the implementing programmer, driven through
[**GitHub Spec Kit**](https://github.com/github/spec-kit) in a spec-driven
sequence. Spec Kit was installed at user level (`~/.claude/skills/`) so its
commands are available in any project, with per-project scaffolding under
`.specify/`.

The sequence, in order:

| Step | Artifact produced |
|---|---|
| Reconnaissance | Direct inspection of the PDF before any spec existed |
| `/speckit-constitution` | `.specify/memory/constitution.md` — six governing principles |
| `/speckit-specify` | `specs/001-data-chapter-rag/spec.md` — 30 requirements, 12 success criteria |
| `/speckit-plan` | `plan.md`, `research.md`, `data-model.md`, 3 contracts, `quickstart.md` |
| `/speckit-tasks` | `tasks.md` — 57 tasks across 6 phases |
| `/speckit-implement` | The implementation |

The ordering mattered more than the tooling. Writing the spec before the code
forced the refusal behaviour, the child-audience rule, and chapter
reproducibility to be stated as testable requirements rather than discovered
late.

A **second iteration** followed once the core worked, run conversationally in
Claude Code rather than through Spec Kit, each change on its own branch:

| Branch | Change |
|---|---|
| `feat/web-ui` | Replaced the default Gradio screen with a FastAPI server and a hand-built page |
| `feat/citations-rerank` | Citations with printed page numbers and quotes; cross-encoder reranking |
| `docs/update` | This report, README and notebook brought in line with the code |

## Context provided to the AI

1. **The brief** (`AI-task.md`), read in full and re-checked against the plan
   in a dedicated coverage pass.
2. **The source PDF**, inspected directly rather than described. Before any
   architecture was proposed, the AI ran extraction code to establish page
   count, TOC structure, text-layer quality, font histograms, and how images
   are actually stored. This is the single highest-value piece of context:
   several plausible designs were eliminated by facts rather than argument.
3. **A constitution** stating non-negotiables — notably that the end user is a
   **child**, which the brief never says. This was supplied by the author, not
   inferred, and it changed the UI, the error messages, and the refusal copy.
4. **Spec Kit's own templates**, which imposed the WHAT/HOW separation.

## What was delegated

Essentially all code production, plus:

- PDF reconnaissance and measurement
- Drafting spec, plan, research, data model, contracts, task breakdown
- Implementation of all 14 modules
- Test authoring (now 70 unit and contract tests)
- Calibration runs and validation scenarios
- In the second iteration: the web interface's design and code, the
  citation and quote pipeline, the reranker, labelling the eval set with
  relevant passages, and the benchmark runs

## What was retained by the author

- **The target audience.** The decision that the reader is a child, not a
  parent — the book's own register addresses a parent — and that this
  outranks fidelity to the book's manner of address.
- **The visuals trade-off.** Presented with a working-but-untuned figure
  cropper and a deadline, the author chose whole-page images. The AI had
  recommended finishing the cropper.
- **Scope discipline.** Repeatedly directing the work to stay proportionate to
  a two-day deadline rather than building speculative features.
- **Spec-driven method.** Choosing SDD over ad-hoc implementation.
- **What the second iteration should contain.** The author asked for a
  professional interface, visible citations, and a reranker, and asked for
  an opinion on HyDE, multi-query retrieval and query contextualisation.
  The AI recommended against the query-rewriting techniques (each adds a
  paid model call, and HyDE would raise the very cosine the refusal gate
  depends on) and recommended adopting the reranker only if a benchmark
  showed gains. The author accepted both recommendations.
- **Branching and publishing.** How the work was split into branches,
  merged, and pushed.

## How generated code was reviewed and validated

Nothing was accepted because it looked plausible. Four mechanisms:

### 1. Run it against the real document, immediately

Every ingestion component was executed against the actual PDF as soon as it
existed, and its output inspected — not merely checked for absence of
exceptions. This caught three substantive bugs that reading the code would
not have:

| Bug | How it surfaced | Fix |
|---|---|---|
| Role table anchored on chapter-opener display type (220pt), collapsing the whole classification | Printed the derived anchors and compared against measured reference | Volume floor on anchor candidates |
| Block-level classification could never see section headings (they share a block with body prose) | Dumped classified blocks for a page already read visually | Classify at line level |
| Size banding promoted diagram numerals (`11000101`) to section headings | Same dump — headings came out as `=`, `of music`, `100 d` | Match derived anchors exactly; everything off-anchor is a label |

### 2. Verify against ground truth, not self-consistency

Chapter resolution was checked against the book's printed TOC (Data → 80–97,
8 spreads). Extracted prose was read against the actual page. The derived role
table was compared against the font histogram measured independently during
research.

A useful cross-check: the role derivation produces **identical anchors**
(body 9.0 / heading 14.0 / title 32.0) on a chapter it was never tuned on,
which is evidence of generalisation rather than fitting.

### 3. Tests that encode the contracts

56 tests at first delivery (70 now), written from the contract documents
rather than from the implementation. The strongest are the ones that would fail if a principle were
quietly violated:

- a below-threshold question makes **zero** network calls (asserted by
  monkeypatching the client to raise if invoked)
- upstream failure yields `Trouble`, never `Refusal`
- a `Trouble` carrying a stack trace, `429`, `openrouter` and `llama` in its
  detail leaks **none** of them into the rendered view
- an uncited answer is downgraded to a refusal

One test caught a live bug: `"D ATA"` — how PyMuPDF renders the kerned running
head — did not match the furniture pattern, so running heads were not actually
being stripped in production.

### 4. Measure claims before stating them

The two design reversals in
[technical-decisions.md](technical-decisions.md) both came from measurement
contradicting a plausible plan:

- **Vector database → NumPy.** The plan specified Chroma/FAISS. Measuring the
  corpus at 44 passages made that ceremony.
- **Fused-score gate → cosine gate.** The plan specified gating on the top RRF
  score. Running it showed 0.0315 for a real question against 0.0296 for
  "What did I eat for breakfast?" — RRF is rank-based, so the top score is
  near-constant and cannot gate anything. Raw cosine separates 0.68–0.88 from
  0.42–0.65. This was a genuine design error that only running the code
  exposed.
- **Reranker: adopted only after a benchmark.** The eval set had no notion of
  *which* passage should answer a question, so ranking quality could not be
  measured. Each answerable question was labelled with its relevant passages
  and 8 harder paraphrased questions were added. Four rerankers were then
  compared on one run: the chosen 80 MB model lifted hit@1 from 13/18 to
  17/18; a 120 MB model tied it, so the smaller one won. Latency was measured
  too (~1.2 s per answered question), which led to skipping the reranker
  whenever the gate refuses.
- **The harder questions exposed a limit, which was recorded, not hidden.**
  Two in-chapter questions now fall below the cosine gate, overlapping with
  the highest must-refuse question. The cross-encoder score was tested as an
  alternative gate and overlaps too. The gate was left unchanged and the
  finding documented (technical-decisions.md §14), rather than tuning a
  threshold to 26 questions.

### 5. Look at the output, not just the tests

The interface was checked with headless-browser screenshots at desktop and
narrow widths, in light and dark themes, for the welcome, answer and refusal
states. One screenshot caught a real bug: a thumbnail captioned "Page 82"
showed the printed number **80**. The PDF's page index runs two ahead of the
book's printed numbering, so every page reference — and the citations about
to be built on them — would have sent a child to the wrong page. Passages now
store the PDF's own page labels.

## Where AI output needed correction

Being specific, since this is the substance of the question:

- **Confident wrong claims about the PDF.** An early analysis asserted that
  figures were extractable as vector drawings. Dumping the geometry showed
  those ~80 "drawings" are prepress registration marks outside the page
  boundary. Corrected in the record rather than silently.
- **Architecture proposed before evidence.** The first plan sketch named
  Chroma and a fused-score gate — reasonable defaults, both wrong for this
  problem, both corrected only because the code was run.
- **Incomplete coverage of the brief.** The first plan omitted three required
  deliverables (this report, the technical-decisions document, and the
  README). A deliberate line-by-line pass over AI-task.md found them.
- **Spec drift.** The spec was written before the constitution was ratified
  and contradicted it in two places. A six-principle audit caught both plus
  four further gaps.
- **A bug the AI introduced itself.** The first version of the new interface
  derived page captions from image file names (`p082.png` → "Page 82"), which
  is the PDF's numbering, not the book's. Found by the screenshot check
  above, not by any test.
- **A misleading measurement.** The first reranker latency reading was taken
  while a 1 GB model benchmark was still running in the background. It was
  re-measured on an idle machine before any figure was written down.
- **Scripted edits that corrupted code.** Two bulk edits made through
  generated Python scripts mangled regex backreferences (`\1` became a
  control character) and silently skipped a replacement. The first was
  caught by reading the result back, the second by an assertion in the edit
  script. Both were redone with exact-match edits.
- **Encoding assumptions.** Two console messages used `→`, which crashed the
  CLI on a Windows `cp1252` console. Both were replaced with ASCII.

## Honest status

- **Answer generation is verified end to end** against the mandated model.
  At first delivery: 18/18 on the original evaluation set (10/10 answered,
  8/8 refused), 4.2 s typical latency. After the eval set grew to 26
  questions (8 harder answerable ones): **24/26** — 16/18 answerable
  answered with citations, 8/8 must-refuse refused, zero upstream failures.
  The two misses are both the cosine-gate overlap described below, not
  model errors.
- **Retrieval ranking**, with the reranker: hit@1 17/18, hit@5 18/18,
  MRR 0.972 (RRF alone: 13/18, 17/18, 0.815). The relevance labels were
  written by the AI from the passage texts and have not been independently
  reviewed; with 18 questions this is a clear direction rather than a
  statistically strong result.
- **The cosine gate refuses two harder in-chapter questions** (0.626 and
  0.651, against a highest must-refuse of 0.651). Recorded, deliberately not
  tuned away; a larger labelled set is the real fix.
- **The mandated model's free tier has been retired** by OpenRouter; the paid
  slug works. The first live call is what surfaced this, and it also exposed
  a real defect: an empty provider response was being rendered as a refusal
  rather than a service failure. Fixed, with regression tests.
- **The refusal threshold is chapter-specific** and should be re-calibrated
  per chapter.
- **Figure-level visual retrieval is not implemented** — a deliberate,
  recorded trade-off, not an oversight.

## Reflection

The pattern that produced the most value was refusing to let the AI design
from assumptions. Every time the document was measured instead of described,
a plausible design collapsed: figures were not extractable, blocks could not
carry headings, size banding could not separate roles, RRF could not gate.
None of those were reasoning failures — each default was sensible — and none
survived contact with the file.

Spec-driven development earned its overhead mainly by making the audience
decision explicit early. Once "the reader is a child" was written as a
non-negotiable principle, it propagated into requirements, into the type
system (three response types), into a single rendering boundary, and into
tests that fail if technical text leaks. Had it stayed an unstated intention,
it would have been implemented as a tone preference and quietly eroded.
