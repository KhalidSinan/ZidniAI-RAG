# Feature Specification: Document-Grounded RAG for the "Data" Chapter

**Feature Branch**: `001-data-chapter-rag`

**Created**: 2026-10-18

**Last Amended**: 2026-10-18 — aligned to Constitution v1.0.0

**Status**: Draft

**Governing principles**: [.specify/memory/constitution.md](../../.specify/memory/constitution.md) v1.0.0

**Input**: User description: "Document-grounded RAG system over chapter 'Data' of the children's book 'Help Your Kids with Computer Science' (PDF). Answers must come exclusively from that chapter, with whole-page images shown alongside answers, in the book's own voice. Scope is the agreed five-stage pipeline: extract, preprocess, index, retrieve, generate. Deliverables: Gradio interface, runnable Jupyter notebook, eval set including must-refuse questions drawn from other chapters, setup docs. Chapter selection must be a single config value so other chapters work without pipeline changes. Keep the spec lean and proportionate to a 2-day deadline - no speculative features."

## User Scenarios & Testing *(mandatory)*

**Primary user**: a child reading the book, asking questions in their own words. A reviewer or
engineer is a *secondary* user who inspects and evaluates the system, never the audience its
output is written for.

### User Story 1 - A child asks a question and understands the answer (Priority: P1)

A child opens the question box and types a question about something in the book's "Data" chapter —
for example, how a computer turns a letter into ones and zeroes. They get back a short answer in
words they already know, written as though the book were speaking to them directly. Next to it
they see the page of the book the answer came from, so they can look at the pictures and read more.

**Why this priority**: This is the product. It alone demonstrates grounding, child-appropriate
tone, retrieval, and visual presentation together.

**Independent Test**: Ask five questions whose answers appear in the chapter. Each answer must be
factually supported by the displayed passages, use no term the chapter does not itself introduce,
and show at least one correct page image.

**Acceptance Scenarios**:

1. **Given** the chapter has been processed, **When** a child asks "How does a computer store a letter?", **Then** the system returns an answer drawn only from chapter content, in plain words, and displays the page image it came from.
2. **Given** an answer has been produced, **When** a reviewer inspects the supporting evidence, **Then** every factual claim can be traced to one of the retrieved passages.
3. **Given** an answer has been produced, **When** it is read, **Then** it contains no technical term that the chapter does not itself introduce and explain.
4. **Given** a question matches content spanning two facing pages, **When** the answer is returned, **Then** the page images for the pages actually used are shown, and unrelated pages are not.
5. **Given** a child with no instructions, **When** they open the interface, **Then** they can tell where to type a question and can read the answer without adult help.

---

### User Story 2 - A child asks something the book doesn't cover, and is told kindly (Priority: P2)

A child asks about something the chapter doesn't talk about — maybe games consoles, maybe
dinosaurs. Instead of making something up, the system tells them plainly and warmly that this
isn't in this part of the book, and points them at the kinds of things it *can* help with.

**Why this priority**: Explicitly named in the assessment and separately scored. A system that
invents answers fails even when retrieval is good — and a child has no way to know it is being
misled.

**Independent Test**: Submit a fixed set of out-of-scope questions — several from other chapters of
the same book, several unrelated to the book — and confirm each produces a refusal that is both
honest and kind, with no fabricated content.

**Acceptance Scenarios**:

1. **Given** a question about a topic covered in a different chapter (e.g. gaming consoles), **When** it is submitted, **Then** the system says it cannot answer from this part of the book and offers no speculative answer.
2. **Given** any refusal, **When** it is read, **Then** it is friendly and encouraging rather than blunt, and suggests what the child could ask about instead.
3. **Given** a question unrelated to the book entirely, **When** it is submitted, **Then** the system refuses in the same kind and consistent manner.
4. **Given** a question that retrieves weakly related but insufficient passages, **When** it is submitted, **Then** the system refuses rather than stretching those passages into an answer.

---

### User Story 3 - Point the pipeline at a different chapter (Priority: P3)

An engineer changes one configuration value naming a different chapter, re-runs processing, and
gets a working question-answering system over that chapter — with no edits to processing,
retrieval, or answering logic.

**Why this priority**: Directly scored as "chapter-level reproducibility", and the main evidence
that this is a pipeline rather than a one-off script. Lower priority only because it is worthless
before the first two stories work.

**Independent Test**: Change the configured chapter to another chapter of the same book, re-run
processing, and ask three questions about the new chapter. All must be answered; questions about
the previously configured chapter must now be refused.

**Acceptance Scenarios**:

1. **Given** the configured chapter is changed and processing is re-run, **When** a question about the newly configured chapter is asked, **Then** it is answered from that chapter's content.
2. **Given** the configured chapter has changed, **When** a question about the previously configured chapter is asked, **Then** it is refused as out of scope.
3. **Given** a chapter change, **When** an engineer reviews the work, **Then** no source file outside configuration required modification.
4. **Given** any single pipeline stage, **When** an engineer runs it alone, **Then** it executes and its output can be inspected without running the others.

---

### Edge Cases

- **Processing cannot locate the configured chapter** (misspelled name, chapter absent): processing fails loudly with a message naming the available chapters, rather than silently producing an empty index. This is an engineer-facing failure and may use technical language.
- **The answering service is unavailable, rate-limited, or times out**: the child sees a short, friendly message saying the system is having trouble and to try again — never a status code, provider name, or exception text, and never anything implying the book lacks the answer.
- **A child misspells words or types in fragments** ("wat is binry"): the system still attempts retrieval and either answers or refuses kindly; it must not error or correct the child pedantically.
- **A question is ambiguous or very short** ("binary?"): the system either answers from the best-supported passages or refuses — it must not error.
- **A question is answerable but the relevant page image is missing or unreadable**: the text answer is still returned, with the image omitted rather than the whole response failing.
- **The same question is asked twice**: the second response is consistent with the first and is no slower.
- **A question in a language other than English**: out of scope for this version; the system responds kindly in English rather than failing.

## Requirements *(mandatory)*

### Functional Requirements

**Child-first experience** *(Constitution I)*

- **FR-001**: Answers MUST use plain vocabulary and short sentences, and MUST NOT contain any technical term that the configured chapter does not itself introduce and explain.
- **FR-002**: Refusals MUST be friendly and encouraging rather than blunt, MUST use consistent wording across questions, and MUST tell the child what kinds of questions the system can help with.
- **FR-003**: Every message shown to the child — answers, refusals, and failure notices — MUST be written for a child. Stack traces, status codes, exception text, model names, and provider names MUST NOT appear on screen.
- **FR-004**: The interface MUST use large readable type, generous spacing, and high contrast, and MUST be usable without reading dense instructions.

**Chapter processing** *(Constitution V)*

- **FR-005**: System MUST locate the target chapter in the source PDF by its title, using the document's own table of contents, rather than hardcoded page numbers.
- **FR-006**: System MUST derive the chapter's page range automatically and process only pages within it.
- **FR-007**: System MUST divide chapter content into retrievable passages that follow the book's own structure (topic spreads and their headings), so that a passage corresponds to a coherent idea rather than an arbitrary slice of text.
- **FR-008**: System MUST record, for every passage, the heading path it sits under and the page(s) it came from.
- **FR-009**: System MUST remove page furniture (page numbers, repeated running heads) and repair text artifacts (words split across line breaks) so that passages read as clean prose.
- **FR-010**: System MUST keep diagram labels and cross-reference sidebars distinguishable from body prose, so they can be searched without polluting the prose used for answering.
- **FR-011**: System MUST produce one readable image per chapter page, usable for display alongside answers.
- **FR-012**: System MUST treat the chapter selection as a single configuration value; selecting another chapter MUST NOT require changes to processing, retrieval, or answering logic.
- **FR-013**: Each pipeline stage MUST be independently runnable, and its output independently inspectable, without executing the other stages.

**Retrieval and grounding** *(Constitution II)*

- **FR-014**: System MUST retrieve passages using both meaning-based and keyword-based matching, combined into a single ranking, so that both plainly-worded questions and exact technical terms are matched.
- **FR-015**: System MUST decide that a question is unanswerable, and refuse, before incurring the cost of generating an answer, when no retrieved passage is sufficiently relevant.
- **FR-016**: System MUST restrict every answer to the content of the configured chapter, with no use of outside knowledge to supplement, complete, or smooth over a partial answer.
- **FR-017**: System MUST associate each answer with the specific passages used and the page image(s) those passages appear on.

**Answering** *(Constitution II, III)*

- **FR-018**: System MUST produce answers that cite the passages supporting them, and MUST reject and replace with a refusal any answer that cites nothing. At least one grounding check MUST operate independently of whether the generating model followed its instructions.
- **FR-019**: Answers MUST address the child directly, while using the book's own vocabulary for the concepts it covers. Where the book's manner of address (an adult explaining to a child) conflicts with speaking to the child directly, direct address takes precedence and the book's word choices are retained.
- **FR-020**: System MUST distinguish, in its user-facing messaging, between "this cannot be answered from the book" and "the system could not respond", and MUST NOT present either as the other.

**Visual presentation** *(Constitution IV)*

- **FR-021**: When an answer is produced, the system MUST display the page image(s) corresponding to the passages actually used, and MUST NOT display pages unrelated to the answer.
- **FR-022**: A missing or unreadable page image MUST result in a text-only answer, never a failed response.

**Interface and inspection**

- **FR-023**: Users MUST be able to submit a question and view the answer, the passages it drew on, and the associated page image(s) in one place.
- **FR-024**: Reviewers MUST be able to inspect retrieved passages and their relevance ranking, so that retrieval quality can be judged independently of answer quality. This inspection view is reviewer-facing and MAY use technical language, provided it is separated from the child-facing output.
- **FR-025**: System MUST provide a runnable notebook that walks through every processing stage in order and shows each stage's output.

**Reliability, performance, reproducibility** *(Constitution VI)*

- **FR-026**: System MUST retry transient answering-service failures and, when retries are exhausted, surface a child-appropriate message per FR-003.
- **FR-027**: No failure path may produce an empty screen, a silent hang, or an unhandled crash reaching the child.
- **FR-028**: System MUST reuse previously processed chapter output rather than reprocessing the PDF on every run or every question.
- **FR-029**: System MUST document dependencies and setup steps sufficiently for a reviewer to reproduce processing and answering from a clean checkout.
- **FR-030**: System MUST include a fixed set of evaluation questions, covering both answerable and must-refuse cases, that can be re-run to check behaviour.

### Key Entities

- **Chapter**: The unit of processing. Identified by title, resolved to a page range. The single configurable input to the pipeline.
- **Passage**: A coherent, retrievable piece of chapter content. Carries its text, its heading path, its source page(s), and its associated labels and cross-references.
- **Page image**: A readable picture of one chapter page, linked to every passage appearing on it; the vehicle for presenting visual content alongside answers.
- **Answer**: A response to a question, carrying either grounded text plus the passages and page images supporting it, or a refusal.
- **Evaluation question**: A fixed question paired with its expected handling (answerable, or must-refuse), used to verify behaviour across changes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 10 questions whose answers appear in the configured chapter, at least 9 answers are factually supported by the passages shown with them, with no claims that do not appear in the chapter.
- **SC-002**: For 100% of a fixed set of out-of-scope questions — including questions drawn from other chapters of the same book — the system refuses instead of answering.
- **SC-003**: At least 8 of 10 answerable questions display at least one page image that a reader agrees is relevant to the answer.
- **SC-004**: Across 10 answers, no answer contains a technical term that the configured chapter does not itself introduce, and average sentence length does not exceed that of the chapter's own prose.
- **SC-005**: 100% of refusals in the evaluation set are judged friendly and encouraging, and each tells the child what they could ask about instead.
- **SC-006**: A child aged roughly 9–12 can open the interface, ask a question, and read the answer without adult help or written instructions.
- **SC-007**: Across the full evaluation set, including deliberately forced service failures, no stack trace, status code, exception text, model name, or provider name ever appears on the child-facing screen.
- **SC-008**: A reviewer can switch the system to a different chapter and get correct answers from it by changing one configuration value and re-running processing, with no other file edited.
- **SC-009**: A typical question returns a complete response in under 15 seconds, and a repeated question is no slower.
- **SC-010**: Initial chapter processing completes in under 5 minutes; subsequent runs reuse existing output and are ready to answer in under 30 seconds.
- **SC-011**: A reviewer can set up and run the system from a clean checkout using only the written setup instructions.
- **SC-012**: No failure of the external answering service is ever presented to the user as "not answerable from the book".

## Assumptions

**Audience**

- The end user is a **child**, not a parent and not an engineer. The book's title (*Help Your Kids with Computer Science*) addresses a parent, so the book's manner of address and this product's differ; FR-019 resolves that conflict in favour of speaking to the child directly while keeping the book's vocabulary.
- Target reading age is roughly 9–12, matching the book's own level. No reading-age configuration is in scope.
- Reviewer-facing surfaces (the retrieval inspection view, the notebook, processing logs) are exempt from child-appropriate language, provided they remain separate from what the child sees.

**Scope and content**

- The assessment names "chapter number #6 (Data)", but in this PDF "Data" is chapter 5 — chapter 6 is "Programming techniques". The chapter **title** is treated as authoritative, so "Data" is the target. Because chapter selection is a single configuration value (FR-012), the other chapter can be served without code changes if the numbering was intended instead.
- Visual content is presented as **whole page images**, not individually cropped figures. The source PDF stores each page as a single full-page bitmap with no separately addressable figures, so isolating individual diagrams would require image segmentation that is not justified within the deadline. The assessment asks for "reasonable effort", and a correctly chosen page satisfies it.
- English-language questions only.
- The book's text layer is machine-readable throughout the chapter; no optical character recognition is required.

**Environment and dependencies**

- Answer generation uses `meta-llama/llama-3.3-70b-instruct:free` via OpenRouter, as mandated by the assessment and fixed by the constitution; a working API credential is supplied by the person running the system. Other models may be used for preprocessing only.
- That model is accessed on a free tier subject to rate limiting and intermittent unavailability, so transient failures are expected behaviour to be handled, not exceptional cases (FR-026, SC-012).
- Passage matching runs locally and requires no external service, so processing and retrieval remain reproducible offline.
- The source PDF is supplied locally rather than downloaded at run time.

**Delivery**

- Single-user local use; no authentication, multi-user access, deployment, or conversation history.
- Each question is answered independently; follow-up questions that depend on earlier turns are out of scope.
- Correctness, tone, and child-appropriateness are judged by human review against the book, supported by the fixed evaluation set (FR-030); no automated scoring model is in scope.
