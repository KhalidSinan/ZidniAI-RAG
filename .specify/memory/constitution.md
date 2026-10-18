<!--
SYNC IMPACT REPORT (scratch — remove before committing the amended constitution)

Version change: none → 1.0.0 (initial ratification)

Modified principles: none (first adoption; template placeholders replaced)

Added sections:
  - Core Principles I–VI
  - Mandated Constraints
  - Development Workflow
  - Governance

Removed sections: none

Notes:
  - Template ships 5 principle slots; 6 are defined here. Principle I (child-first) is the
    addition requested beyond AI-task.md; II–VI derive from the brief.
  - Principle I and Principle III overlap deliberately and can conflict; the precedence rule
    is stated inside Principle III rather than left implicit.

Follow-up TODOs: none — no placeholders deferred.
-->

# Zidni Document-Grounded RAG Constitution

## Core Principles

### I. Child-First Experience (NON-NEGOTIABLE)

The reader is a child, not an adult engineer and not a parent. Every word the system emits and
every pixel it renders MUST be built for that reader.

- Answers MUST use plain vocabulary and short sentences. Any technical term the chapter does not
  itself introduce MUST NOT appear in an answer.
- Refusals MUST be kind and encouraging, never blunt or scolding. A refusal MUST tell the child
  what the system *can* help with, not merely that it failed.
- Error messages MUST be written for a child. Stack traces, status codes, model names, provider
  names, and exception text MUST NOT reach the screen.
- The interface MUST use large readable type, generous spacing, and high contrast, and MUST remain
  usable without reading dense instructions.

**Rationale**: The brief fixes the audience of the *content* but never the audience of the
*product*. Without this principle, defaults drift toward developer-facing output — raw errors,
jargon, dense layout — which fails the real user even when retrieval and grounding are perfect.

### II. Grounded or Silent (NON-NEGOTIABLE)

The system answers from the configured chapter or it does not answer.

- Every factual claim MUST trace to retrieved chapter content. Model world-knowledge MUST NOT
  supplement, complete, or smooth over a partial answer.
- When retrieved content is insufficient, the system MUST say so plainly rather than infer,
  generalize, or hedge its way to an answer.
- Grounding MUST be enforced by at least one check that does not depend on the model obeying its
  instructions.

**Rationale**: Faithfulness and refusal handling are two of the seven scored criteria. A
confidently wrong answer to a child is worse than no answer, because a child has no basis to
doubt it.

### III. The Book's Voice

Responses MUST read as though they came from the book: its register, its vocabulary, its way of
explaining things to a beginner.

- Retrieved passages are the reference for tone, not a generic "simple English" style.
- Where the book's register (an adult helping a child) conflicts with Principle I (addressing the
  child directly), **Principle I wins on address and Principle III wins on vocabulary** — speak to
  the child directly, using the book's words for things.

**Rationale**: Named explicitly in the brief and separately scored. The precedence rule is stated
because the book's title is *Help Your Kids with Computer Science* — it addresses the parent, while
this product addresses the child, and that conflict will otherwise be resolved inconsistently from
one answer to the next.

### IV. Show the Page

Visual content is part of the answer, not a bonus.

- When an answer draws on chapter content, the system MUST make a reasonable effort to display the
  corresponding page image alongside it.
- Images MUST correspond to the passages actually used. Unrelated pages MUST NOT be shown.
- A missing or unreadable image MUST degrade to a text-only answer, never to a failed response.

**Rationale**: The source is a visual book whose diagrams carry meaning the prose omits, and for a
child reader a picture often *is* the explanation.

### V. Chapter-Agnostic Pipeline

The pipeline processes a configured chapter; it is never written against one chapter's quirks.

- Chapter selection MUST be a single configuration value.
- Targeting a different chapter MUST NOT require edits to extraction, preprocessing, indexing,
  retrieval, or generation logic.
- Page ranges MUST be derived from the document's own structure, never hardcoded.
- Each stage MUST be independently runnable and inspectable.

**Rationale**: Required by the brief and separately scored. It is also the difference between a
pipeline and a script that happened to work once.

### VI. Fail Gently, Fail Clearly

Failures are expected, and the system's conduct during them is part of the product.

- "I could not find this in the book" and "something went wrong" MUST be distinguishable to the
  user, and MUST NOT be conflated in either direction.
- Transient upstream failures MUST be retried before surfacing; exhausted retries MUST produce a
  child-appropriate message per Principle I.
- No failure path may produce an empty screen, a silent hang, or an unhandled crash.

**Rationale**: The mandated model runs on a rate-limited free tier, so upstream failure is a normal
operating condition. A child who cannot tell "the book doesn't say" from "it's broken" learns the
wrong thing from the product.

## Mandated Constraints

Fixed by the assessment brief and not open to redesign:

- **Generation model**: `meta-llama/llama-3.3-70b-instruct:free` via OpenRouter MUST be the model
  used for answer generation. Other models MAY be used for preprocessing only.
- **Source**: the supplied PDF is the sole knowledge source. No external corpus, no web retrieval.
- **Consistency**: the same question MUST receive factually consistent answers across runs, and
  grounding rules MUST apply uniformly to every query.
- **Performance**: queries MUST be responsive, and the PDF MUST NOT be reprocessed on every run or
  every question. Processed output MUST be reused.
- **Reproducibility**: dependencies and setup steps MUST be documented well enough for a reviewer
  to reproduce the system from a clean checkout.

## Development Workflow

- **Engineering ownership**: AI assistants may write code; responsibility for it is not delegable.
  Generated code MUST be reviewed and validated before it is relied upon, and claims about what
  works MUST be backed by having run it.
- **Documented rationale**: significant technical choices MUST be recorded with the alternatives
  considered and the trade-off accepted. A choice whose reasoning is not written down is not
  finished.
- **Honest history**: git history MUST reflect how the work actually proceeded — meaningful commits
  at real checkpoints, branches per stage. History MUST NOT be reconstructed after the fact to look
  orderly.
- **Scope discipline**: core requirements are completed before enhancements. A feature not required
  by the brief MUST NOT be built while any required one is incomplete.
- **Verification before claiming**: processing and retrieval output MUST be inspected against the
  source book, not assumed correct because the code ran without error.

## Governance

This constitution supersedes other practices and defaults for this project. Where a tool's
convention, a framework's default, or an AI assistant's habit conflicts with a principle here, the
principle wins.

- **Compliance**: every change MUST be checkable against these principles. Principles I and II are
  non-negotiable: a change that weakens either is rejected regardless of what it improves.
- **Conflicts**: Principle I takes precedence over all others where they conflict, except
  Principle II, which it may never override — the system may not soften a refusal into a guess to
  please a child.
- **Complexity**: added complexity MUST be justified against a principle it serves. "It might be
  useful later" is not a justification.
- **Amendments**: amendments MUST be recorded in this file with a version bump and the reasoning
  for the change. MAJOR for removing or redefining a principle, MINOR for adding or materially
  expanding one, PATCH for clarifications.

**Version**: 1.0.0 | **Ratified**: 2026-10-18 | **Last Amended**: 2026-10-18
