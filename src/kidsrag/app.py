"""The child-facing interface.

Principle I governs this file and web/: large readable type, generous
spacing, high contrast, and usable without reading instructions (FR-004,
SC-006).

A small FastAPI server and a hand-built page in web/. The page is static;
everything dynamic goes through two JSON endpoints.

All child-facing text comes from render.py. The `retrieval` block in the
/api/ask response is reviewer-facing - the scoped exception recorded in
plan.md Complexity Tracking - and the page keeps it in a separate drawer,
closed by default so a child never opens it by accident.
"""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Config
from .errors import ArtifactsMissing
from .index.retrieve import Retriever
from .models import RetrievalResult
from .render import render

WEB_DIR = Path(__file__).parent / "web"

WELCOME = (
    "Ask me anything about **data** — binary code, secret codes, "
    "pictures, sounds, and databases. Type your question above!"
)

EXAMPLES = [
    "What is binary code?",
    "How does a computer store a letter?",
    "How are pictures stored on a computer?",
    "What is encryption?",
]


class Question(BaseModel):
    question: str = ""


def _panel(result: RetrievalResult, cfg: Config) -> dict:
    """Reviewer-facing retrieval detail. Never shown to the child by default."""
    return {
        "gate": "PASS" if result.passed_gate else "REFUSE",
        "max_cosine": round(result.max_cosine, 4),
        "min_cosine": cfg.retrieval.gate_min_cosine,
        "top_fused": round(result.top_score, 5),
        "rows": [
            {
                "rank": i,
                "fused": round(s, 5),
                "dense": result.dense_ranks.get(p.id),
                "sparse": result.sparse_ranks.get(p.id),
                "heading": p.heading_display,
                "pages": p.pages,
            }
            for i, (p, s) in enumerate(zip(result.passages, result.scores), start=1)
        ],
    }


def build_app(cfg: Config) -> FastAPI:
    retriever = Retriever.load(cfg)
    chapter_dir = Path(cfg.chapter_dir).resolve()

    app = FastAPI(title="Ask the book", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/meta")
    def meta() -> dict:
        return {
            "chapter": cfg.chapter_title,
            "welcome": WELCOME,
            "examples": EXAMPLES,
        }

    # Sync handler on purpose: FastAPI runs it in a worker thread, so the
    # blocking model call never stalls the server.
    @app.post("/api/ask")
    def ask(body: Question) -> dict:
        from .generate.answer import answer_question

        question = body.question.strip()
        if not question:
            return {"kind": "welcome", "text": WELCOME, "images": [], "retrieval": None}

        result = retriever.retrieve(question)
        response = answer_question(cfg, question, result)
        view = render(response)

        images = [
            f"/book/{img}" for img in view.images if (chapter_dir / img).exists()
        ]
        return {
            "kind": view.kind,
            "text": view.text,
            "images": images,
            "retrieval": _panel(result, cfg),
        }

    @app.get("/book/{path:path}", include_in_schema=False)
    def book_page(path: str) -> FileResponse:
        target = (chapter_dir / path).resolve()
        # Only page images from this chapter's artifacts - nothing else on disk.
        if not target.is_relative_to(chapter_dir) or target.suffix != ".png":
            raise HTTPException(status_code=404)
        if not target.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(target)

    return app


def launch(cfg: Config, port: int = 7860, host: str = "127.0.0.1") -> None:
    if not Path(cfg.chapter_dir).exists():
        # Never start in a state where every question would fail.
        raise ArtifactsMissing(str(cfg.chapter_dir))
    print(f"Ask the book: http://{host}:{port}")
    uvicorn.run(build_app(cfg), host=host, port=port, log_level="warning")
