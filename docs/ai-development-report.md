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
- Test authoring (56 unit and contract tests)
- Calibration runs and validation scenarios

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

56 tests, written from the contract documents rather than from the
implementation. The strongest are the ones that would fail if a principle were
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

## Honest status

- **Answer generation is now verified end to end** against the mandated
  model: 18/18 on the evaluation set (10/10 answered, 8/8 refused), citations
  emitted on 5/5 sampled calls, 4.2 s typical latency.
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
