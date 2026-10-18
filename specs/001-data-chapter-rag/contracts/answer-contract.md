# Contract: Answer & Child-Facing Surface

**Modules**: `src/kidsrag/generate/answer.py`, `src/kidsrag/render.py`

This is the contract that makes Principles I and II enforceable rather than aspirational. Every
string a child reads passes through `render.py`, and `render.py` accepts only the three response
types defined in [data-model.md](../data-model.md).

## The rendering boundary

```python
def render(response: Answer | Refusal | Trouble) -> ChildView
```

| Rule | Consequence |
|---|---|
| `render()` accepts only the three response types | No exception, status code, or provider name can reach the screen — none of those types can carry one |
| `Trouble.detail` is never read by `render()` | Technical cause is retained for the reviewer, structurally excluded from the child's view |
| No other module writes to the child-facing UI | "Did technical text leak?" is answerable by reading one file (FR-003, SC-007) |

The reviewer-facing inspection panel is a **separate** component taking `RetrievalResult`, and is
the scoped exception recorded in the plan's Complexity Tracking.

## Prompt contract

The system prompt MUST carry exactly four obligations:

1. **Grounding** — answer only from supplied passages; never supplement from outside knowledge.
2. **Citation** — mark each supported claim with `[C#]` matching a supplied passage.
3. **Refusal** — if passages are insufficient, refuse using the given wording; never guess.
4. **Voice** — address the child directly; use the book's vocabulary; short sentences; introduce no
   technical term the passages do not themselves introduce (FR-001, FR-019).

Context is assembled as, per passage:

```text
[C1] Data › Binary code › Binary to decimal
People usually count using the decimal system...
```

The heading path is included because it carries topical context the prose omits.

Two few-shot exchanges written in the book's register are included — one answerable, one refusal —
so the model has the target voice in front of it rather than only a description of it.

## Citation check

Applied to every generated response, before rendering:

| Step | Rule |
|---|---|
| 1 | Extract `[C#]` markers via regex |
| 2 | Discard markers not matching a supplied passage |
| 3 | If no valid markers remain → return `Refusal(no_citations)` |
| 4 | Otherwise → `Answer`, `cited` = resolved passages only |

This check is plain string matching. It holds **regardless of whether the model followed its
instructions**, which is precisely what Principle II requires (FR-018).

## Image selection

| Rule | Source |
|---|---|
| Collect `page_images` from `cited` passages only | FR-021 |
| Deduplicate by page | FR-021 |
| Cap at 2, ordered by citation order | FR-021 |
| Missing file on disk → drop that image, keep the answer | FR-022 |

Images come from **cited** passages, not all retrieved ones — otherwise a merely-retrieved page
would be presented as a source.

## Response text rules

### Answer

- Addressed to the child, second person.
- Short sentences; no term the chapter does not itself introduce (FR-001, SC-004).
- Citation markers may be rendered as footnote-style references or hidden from display, but the
  underlying `cited` list MUST remain visible to reviewers (FR-024).

### Refusal

- Friendly and encouraging; never blunt (FR-002).
- MUST say what the child *could* ask about instead — e.g. naming chapter topics.
- Consistent wording across questions (FR-002).
- MUST NOT imply malfunction (FR-020).

> *"I couldn't find anything about that in this part of the book. This part is all about data —
> things like binary code, secret codes, and how pictures are stored. Want to ask me about one of
> those?"*

### Trouble

- Says something went wrong and to try again shortly.
- MUST NOT imply the book lacks the answer (FR-020, SC-012).
- MUST NOT contain status codes, exception text, model or provider names (FR-003, SC-007).

> *"Something went wrong on my side, sorry! Please try asking again in a moment."*

## Upstream failure handling

| Condition | Behaviour |
|---|---|
| HTTP 429 or 5xx | Exponential backoff, up to `max_retries` |
| Timeout | Counts as a retryable attempt |
| Retries exhausted | `Trouble` — never `Refusal` (SC-012) |
| Malformed response body | `Trouble` |
| Missing API key | `Trouble` at question time; warned at startup |

## Contract tests

- A model response with no `[C#]` markers yields `Refusal(no_citations)`, not an answer.
- A response citing an id not in the supplied set is treated as uncited.
- A forced 429 exhausting retries yields `Trouble`, never `Refusal`.
- `render()` output for a `Trouble` whose `detail` contains a stack trace contains none of it.
- A cited passage whose page image is absent yields a text-only answer, exit 0 (FR-022).
- Retrieval below threshold yields `Refusal(below_threshold)` with **zero** network calls made.
