# Ask the book 📘

A document-grounded RAG system that answers a **child's** questions about one
chapter of *Help Your Kids with Computer Science*, using only what that chapter
says — and saying so plainly when the chapter doesn't cover the question.

Answers come back in the book's own vocabulary, written for a 9–12 year old,
with the page they came from shown alongside.

---

## Setup

Requires **Python 3.12** (not 3.13 — `onnxruntime` wheels lag behind) and the
source PDF in the repo root.

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"

cp .env.example .env        # then add your OpenRouter key
```

Get a free key at [openrouter.ai/keys](https://openrouter.ai/keys). Ingestion
and retrieval work **offline** — the key is only needed to generate answers.

Verify the environment:

```bash
python -c "import pymupdf, fastembed, numpy, httpx, fastapi, uvicorn; print('ok')"
```

## Run

```bash
python -m kidsrag ingest                     # process the chapter (~13s)
python -m kidsrag inspect --limit 20         # check the chunking
python -m kidsrag ask "What is binary code?"
python -m kidsrag ui                         # the child-facing interface
```

First run downloads ~130 MB of embedding weights. Later runs are cached and
report `cached, nothing to do`.

## Switching chapters

Change **one value** in `config.yaml` and re-run `ingest`:

```yaml
chapter:
  title: "Programming techniques"
```

No source file changes. Page ranges come from the PDF's own table of contents,
and each chapter gets its own `artifacts/<slug>/` directory, so chapters
coexist without collision.

> **On the chapter number.** The brief asks for "chapter #6 (Data)", but this
> PDF's table of contents puts **Data at chapter 5**; chapter 6 is
> *Programming techniques*. The chapter **title** is treated as authoritative,
> so the default target is Data. If the number was meant instead, change the
> one config value above — both chapters are verified working.

## Commands

| Command | What it does |
|---|---|
| `ingest [--force]` | Extract, chunk, render pages, embed. Idempotent. |
| `inspect [--passage ID] [--page N]` | Show extracted passages — check chunking before trusting it |
| `ask "<question>" [--show-retrieval]` | One question; `--show-retrieval` adds the reviewer panel |
| `eval [--retrieval-only] [--reranker off\|<model>]` | Run the evaluation set; `--retrieval-only` needs no API key and also reports ranking quality (hit@1, MRR) |
| `ui [--port N] [--host H]` | Start the child-facing interface at http://127.0.0.1:7860 |

A refusal exits **0** — "the book doesn't cover this" is correct behaviour, not
a failure. Only missing artifacts or bad config exit 1.

## How it works

```
PDF ──► resolve chapter by title from the TOC
    ──► derive typographic role table  (which font+size means what)
    ──► chunk by spread → section heading
    ──► render each page to PNG
    ──► embed locally (fastembed / bge-small)
                │
question ──► dense cosine + BM25 ──► RRF fusion ──► top 5
                │
            ┌───┴─── max cosine < 0.66 ──► Refusal  (no network call)
            │
            └──► OpenRouter (llama-3.3-70b) ──► citation check
                                                  │
                                    ┌─────────────┼─────────────┐
                                 Answer        Refusal        Trouble
                                                  │
                                            render.py  ──► the child
```

Grounding is enforced **twice**: a score gate before the model is called, and
a deterministic citation check afterwards that works whether or not the model
followed instructions.

Every string a child reads comes from `render.py`, which accepts only
`Answer`, `Refusal`, or `Trouble` — none of which can carry a stack trace,
status code, or provider name. "Did technical text leak?" is answerable by
reading one file.

## Layout

```
src/kidsrag/
  config.py models.py errors.py render.py cli.py app.py evaluate.py
  ingest/   pdf.py roles.py text.py pages.py build.py
  index/    embed.py store.py retrieve.py
  generate/ prompt.py llm.py answer.py
tests/      unit/ contract/ eval/
notebooks/  01_pipeline.ipynb
docs/       technical-decisions.md  ai-development-report.md
specs/      001-data-chapter-rag/   (spec, plan, research, contracts, tasks)
```

## Tests

```bash
pytest                                  # 56 unit + contract tests
python -m kidsrag eval --retrieval-only # 18-question evaluation set
```

`eval` exits non-zero if any must-refuse question gets answered. The
must-refuse questions are drawn mostly from **other chapters of the same
book** — that tests chapter scoping, which is the thing that can actually
break. Nonsense questions prove very little.

## Known limitations

- **Visuals are whole pages, not cropped figures.** Every page in this PDF is
  one full-page bitmap with no separately addressable figures. See
  [docs/technical-decisions.md](docs/technical-decisions.md).
- **The refusal threshold is chapter-specific.** 0.66 is calibrated for Data.
  Another chapter should be re-calibrated with `eval --retrieval-only`.
- **The mandated model's `:free` tier no longer exists.** OpenRouter returns
  404 ("This model is unavailable for free") for
  `meta-llama/llama-3.3-70b-instruct:free`. `config.yaml` uses the paid slug,
  which works; a verified free substitute is commented directly above it. See
  [docs/technical-decisions.md](docs/technical-decisions.md) section 13.
