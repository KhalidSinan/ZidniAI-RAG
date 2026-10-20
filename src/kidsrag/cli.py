"""Stage-by-stage command line.

Contract: specs/001-data-chapter-rag/contracts/pipeline-cli.md

Each stage runs standalone and its output is inspectable without the others
(FR-013). Stdout here is operator-facing and may be technical; the only
child-facing surface is the UI, whose text comes from render.py.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import load_config
from .errors import PipelineError

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", default="config.yaml", help="path to config.yaml")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kidsrag", description="Document-grounded RAG over one book chapter"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="process the configured chapter")
    _add_common(p_ingest)
    p_ingest.add_argument(
        "--force", action="store_true", help="rebuild even if cached"
    )

    p_inspect = sub.add_parser("inspect", help="show extracted passages")
    _add_common(p_inspect)
    p_inspect.add_argument("--passage", help="show one passage in full, by id")
    p_inspect.add_argument("--page", type=int, help="only passages from this page")
    p_inspect.add_argument("--limit", type=int, default=50)

    p_ask = sub.add_parser("ask", help="ask a question")
    _add_common(p_ask)
    p_ask.add_argument("question")
    p_ask.add_argument(
        "--show-retrieval", action="store_true", help="reviewer-facing panel"
    )

    p_eval = sub.add_parser("eval", help="run the evaluation set")
    _add_common(p_eval)
    p_eval.add_argument("--questions", default="tests/eval/questions.yaml")
    p_eval.add_argument(
        "--retrieval-only",
        action="store_true",
        help="test the refusal gate without calling the model",
    )

    p_ui = sub.add_parser("ui", help="start the child-facing interface")
    _add_common(p_ui)
    p_ui.add_argument("--port", type=int, default=7860)
    p_ui.add_argument(
        "--host", default="127.0.0.1", help="use 0.0.0.0 to reach it from other devices"
    )

    return parser


def cmd_ingest(args) -> int:
    from .ingest.build import ingest

    cfg = load_config(args.config)
    report = ingest(cfg, force=args.force)
    print(report.render())
    print(f"→ {cfg.chapter_dir}")
    return 0


def cmd_inspect(args) -> int:
    from .index import store

    cfg = load_config(args.config)
    passages = store.load_passages(cfg)

    if args.passage:
        match = [p for p in passages if p.id == args.passage]
        if not match:
            print(f"No passage with id {args.passage!r}", file=sys.stderr)
            return 1
        p = match[0]
        print(f"id:      {p.id}")
        print(f"heading: {p.heading_display}")
        print(f"pages:   {p.pages}")
        print(f"images:  {p.page_images}")
        print(f"\n--- text ({len(p.text)} chars) ---\n{p.text}")
        if p.labels:
            print(f"\n--- labels ({len(p.labels)} chars) ---\n{p.labels}")
        if p.see_also:
            print(f"\n--- see also ---\n" + "\n".join(p.see_also))
        return 0

    shown = [p for p in passages if not args.page or args.page in p.pages]
    print(f"{len(shown)} passages in {cfg.chapter_dir}\n")
    for p in shown[: args.limit]:
        print(
            f"  {p.id[:44]:44s} p{str(p.pages):10s} "
            f"{len(p.text):5d}ch  labels={len(p.labels):4d}"
        )
        print(f"      {p.heading_display}")
    return 0


def cmd_ask(args) -> int:
    from .generate.answer import answer_question
    from .index.retrieve import Retriever
    from .render import render

    cfg = load_config(args.config)
    retriever = Retriever.load(cfg)
    result = retriever.retrieve(args.question)
    response = answer_question(cfg, args.question, result)
    view = render(response)

    print(view.text)
    if view.images:
        print("\nPages from the book:")
        for img in view.images:
            print(f"  {cfg.chapter_dir / img}")

    if args.show_retrieval:
        print("\n--- retrieval (reviewer view) ---")
        print(f"gate: {'PASS' if result.passed_gate else 'REFUSE'} "
              f"(max cosine {result.max_cosine:.4f}, "
              f"min {cfg.retrieval.gate_min_cosine})  "
              f"top fused {result.top_score:.5f}")
        for p, s in zip(result.passages, result.scores):
            print(
                f"  {s:.5f}  dense={result.dense_ranks.get(p.id, '-'):>3} "
                f"sparse={result.sparse_ranks.get(p.id, '-'):>3}  {p.id}"
            )
    # A refusal is correct behaviour, not failure (contracts/pipeline-cli.md).
    return 0


def cmd_eval(args) -> int:
    from .evaluate import run_eval

    cfg = load_config(args.config)
    return run_eval(cfg, Path(args.questions), retrieval_only=args.retrieval_only)


def cmd_ui(args) -> int:
    from .app import launch

    cfg = load_config(args.config)
    launch(cfg, port=args.port, host=args.host)
    return 0


COMMANDS = {
    "ingest": cmd_ingest,
    "inspect": cmd_inspect,
    "ask": cmd_ask,
    "eval": cmd_eval,
    "ui": cmd_ui,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except PipelineError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
