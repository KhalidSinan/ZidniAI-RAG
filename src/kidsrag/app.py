"""The child-facing interface.

Principle I governs this file: large readable type, generous spacing, high
contrast, and usable without reading instructions (FR-004, SC-006).

All child-facing text comes from render.py. The retrieval panel below is
reviewer-facing - the scoped exception recorded in plan.md Complexity
Tracking - and is kept visually and structurally separate, collapsed by
default so a child never opens it by accident.
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from .config import Config
from .errors import ArtifactsMissing
from .index.retrieve import Retriever
from .models import RetrievalResult
from .render import render

CSS = """
.kid-answer {
    font-size: 1.35rem !important;
    line-height: 1.85 !important;
    padding: 1.4rem 1.6rem;
    border-radius: 18px;
    border: 3px solid #1565c0;
    background: #f3f8ff;
    color: #10243a;
}
.kid-answer.refusal { border-color: #ef8c00; background: #fff8ec; }
.kid-answer.trouble { border-color: #b03030; background: #fff1f1; }
.kid-question textarea {
    font-size: 1.3rem !important;
    line-height: 1.6 !important;
    padding: 0.9rem !important;
    border-radius: 14px !important;
}
.kid-title { font-size: 2.1rem; font-weight: 800; margin-bottom: .2rem; }
.kid-sub { font-size: 1.1rem; opacity: .85; margin-bottom: 1.1rem; }
.reviewer { font-size: .85rem; font-family: ui-monospace, monospace; }
"""

WELCOME = (
    "Ask me anything about **data** — binary code, secret codes, "
    "pictures, sounds, and databases. Type your question below!"
)

EXAMPLES = [
    "What is binary code?",
    "How does a computer store a letter?",
    "How are pictures stored on a computer?",
    "What is encryption?",
]


def _panel(result: RetrievalResult, cfg: Config) -> str:
    """Reviewer-facing retrieval detail. Never shown to the child by default."""
    gate = "PASS" if result.passed_gate else "REFUSE"
    lines = [
        f"gate={gate}  max_cosine={result.max_cosine:.4f} "
        f"(min {cfg.retrieval.gate_min_cosine})  "
        f"top_fused={result.top_score:.5f}",
        "",
        "rank  fused     dense  sparse  passage",
    ]
    for i, (p, s) in enumerate(zip(result.passages, result.scores), start=1):
        lines.append(
            f"{i:>4}  {s:.5f}  "
            f"{str(result.dense_ranks.get(p.id, '-')):>5}  "
            f"{str(result.sparse_ranks.get(p.id, '-')):>6}  {p.heading_display}"
        )
    return "```\n" + "\n".join(lines) + "\n```"


def build_ui(cfg: Config) -> gr.Blocks:
    retriever = Retriever.load(cfg)

    def ask(question: str):
        from .generate.answer import answer_question

        question = (question or "").strip()
        if not question:
            return (
                gr.update(value=WELCOME, elem_classes=["kid-answer"]),
                gr.update(value=None, visible=False),
                gr.update(value=""),
            )

        result = retriever.retrieve(question)
        response = answer_question(cfg, question, result)
        view = render(response)

        images = [
            str(cfg.chapter_dir / img)
            for img in view.images
            if (cfg.chapter_dir / img).exists()
        ]

        return (
            gr.update(
                value=view.text,
                elem_classes=["kid-answer", view.kind],
            ),
            gr.update(value=images or None, visible=bool(images)),
            gr.update(value=_panel(result, cfg)),
        )

    with gr.Blocks(css=CSS, title="Ask the Computer Science Book") as demo:
        gr.Markdown(
            f"<div class='kid-title'>Ask the book! 📘</div>"
            f"<div class='kid-sub'>Chapter: {cfg.chapter_title}</div>"
        )

        question = gr.Textbox(
            label="Your question",
            placeholder="Type your question here, then press Ask",
            lines=2,
            elem_classes=["kid-question"],
        )
        ask_btn = gr.Button("Ask", variant="primary", size="lg")

        answer = gr.Markdown(WELCOME, elem_classes=["kid-answer"])
        pages = gr.Gallery(
            label="Pages from the book",
            visible=False,
            columns=2,
            height="auto",
        )

        gr.Examples(examples=EXAMPLES, inputs=question, label="Try one of these")

        with gr.Accordion("Retrieval detail (for reviewers)", open=False):
            panel = gr.Markdown("", elem_classes=["reviewer"])

        ask_btn.click(ask, inputs=question, outputs=[answer, pages, panel])
        question.submit(ask, inputs=question, outputs=[answer, pages, panel])

    return demo


def launch(cfg: Config, port: int = 7860, share: bool = False) -> None:
    if not Path(cfg.chapter_dir).exists():
        # Never start in a state where every question would fail.
        raise ArtifactsMissing(str(cfg.chapter_dir))
    build_ui(cfg).launch(server_port=port, share=share)
