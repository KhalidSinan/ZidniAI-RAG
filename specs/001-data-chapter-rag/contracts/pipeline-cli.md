# Contract: Pipeline CLI

**Module**: `src/kidsrag/cli.py` | **Invocation**: `python -m kidsrag.<command>`

Each pipeline stage is a separately invocable command whose output can be inspected without
running the others. This contract **is** the evidence for Principle V and FR-013.

## Commands

### `ingest`

```bash
python -m kidsrag ingest [--config config.yaml] [--force]
```

Runs extract + preprocess + index for the configured chapter.

| Aspect | Contract |
|---|---|
| Reads | `pdf.path`, `chapter.title` |
| Writes | `artifacts/{slug}/` — `manifest.json`, `passages.jsonl`, `embeddings.npy`, `pages/*.png` |
| Idempotent | Yes. Matching `cache_key` → skips and reports "cached"; `--force` rebuilds. |
| Exit 0 | Artifacts present and valid |
| Exit 1 | `ChapterNotFound`, unreadable PDF, or zero passages extracted |
| Stdout | Chapter title, page range, spread count, passage count, image count, elapsed time |

Zero extracted passages is a **failure**, never a silent empty index (spec Edge Cases).

---

### `inspect`

```bash
python -m kidsrag inspect [--passage ID] [--page N] [--limit N]
```

Reviewer-facing dump of ingest output, so chunking can be judged before anything is built on it.

| Aspect | Contract |
|---|---|
| Reads | `artifacts/{slug}/` |
| Writes | Nothing |
| Stdout | Passage ids, heading paths, character counts, page numbers; full text with `--passage` |
| Exit 1 | No artifacts — directs the user to run `ingest` |

---

### `ask`

```bash
python -m kidsrag ask "How does a computer store a letter?" [--show-retrieval]
```

| Aspect | Contract |
|---|---|
| Reads | Artifacts; `OPENROUTER_API_KEY` |
| Writes | Nothing |
| Stdout | The child-facing response text, plus page image paths |
| `--show-retrieval` | Adds the reviewer-facing panel: passage ids, fused scores, per-retriever ranks |
| Exit 0 | Any of `Answer`, `Refusal`, `Trouble` — a refusal is correct behaviour, not failure |
| Exit 1 | Missing artifacts or unreadable config only |

**A refusal exits 0.** Conflating "the book doesn't cover this" with process failure would
reintroduce exactly the confusion FR-020 forbids.

---

### `eval`

```bash
python -m kidsrag eval [--questions tests/eval/questions.yaml]
```

| Aspect | Contract |
|---|---|
| Reads | Artifacts, question set |
| Writes | Nothing (report to stdout) |
| Stdout | Per-question expected vs actual handling; totals for answerable and must-refuse |
| Exit 0 | Every must-refuse question refused |
| Exit 1 | Any must-refuse question answered — a grounding regression (SC-002) |

Answerable questions are reported but do not fail the run: their correctness is a human judgement
(SC-001), while refusal is binary and machine-checkable.

---

### `ui`

```bash
python -m kidsrag ui [--port 7860]
```

Starts the child-facing interface. Exit 1 if artifacts are missing — the UI never starts in a
state where every question would fail.

## Cross-cutting contract

- Every command accepts `--config` and defaults to `./config.yaml`.
- Stdout is operator-facing and may be technical. **The child-facing surface is the UI only**, and
  its text comes exclusively from `render.py` (FR-003).
- No command mutates the source PDF.
- `ingest` is the only command that writes.

## Contract tests

- Each command runs standalone from a clean checkout in the documented order.
- `ask` and `inspect` exit 1 with an actionable message when artifacts are absent.
- `ingest` twice in a row reports "cached" the second time and rewrites nothing (FR-028).
- `eval` exits 1 if a must-refuse question is answered.
- A refusal from `ask` exits 0.
