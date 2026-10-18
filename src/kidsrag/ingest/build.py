"""Ingest orchestrator: PDF -> passages -> page images -> embeddings -> disk.

Idempotent. A matching cache key means the work is skipped entirely
(FR-028); --force rebuilds.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ..config import Config
from ..errors import PipelineError
from ..index import embed, store
from ..models import Chapter, Passage
from .pages import page_image_map, render_pages
from .pdf import file_sha256, open_document, resolve_chapter, spread_starts
from .roles import derive_role_table
from .text import build_passages


@dataclass
class IngestReport:
    chapter: Chapter
    passage_count: int
    image_count: int
    elapsed_seconds: float
    cached: bool

    def render(self) -> str:
        if self.cached:
            return (
                f"Chapter: {self.chapter.title} "
                f"(pages {self.chapter.start_page}-{self.chapter.end_page}) "
                f"- cached, nothing to do ({self.elapsed_seconds:.1f}s)"
            )
        return (
            f"Chapter: {self.chapter.title} "
            f"(pages {self.chapter.start_page}-{self.chapter.end_page}, "
            f"{self.chapter.spread_count} spreads)\n"
            f"Passages: {self.passage_count}     "
            f"Page images: {self.image_count}\n"
            f"Elapsed: {self.elapsed_seconds:.1f}s"
        )


def ingest(cfg: Config, force: bool = False) -> IngestReport:
    started = time.time()

    doc = open_document(cfg.pdf_path)
    chapter = resolve_chapter(doc, cfg.chapter_title)

    pdf_hash = file_sha256(cfg.pdf_path)
    cache_key = store.compute_cache_key(
        pdf_hash, chapter.title, cfg.ingest.pipeline_version
    )

    if not force and store.is_cached(cfg, cache_key):
        manifest = store.load_manifest(cfg)
        return IngestReport(
            chapter=chapter,
            passage_count=manifest.passage_count if manifest else 0,
            image_count=len(list(store.pages_dir(cfg).glob("*.png"))),
            elapsed_seconds=time.time() - started,
            cached=True,
        )

    images = render_pages(
        doc, chapter, store.pages_dir(cfg), dpi=cfg.ingest.dpi
    )
    image_for = page_image_map(images, cfg.chapter_dir)

    spreads = spread_starts(doc, chapter)
    table = derive_role_table(
        doc, spreads[0][1] if spreads else chapter.start_page, chapter.end_page
    )
    passages: list[Passage] = build_passages(doc, chapter, image_for, table)

    if not passages:
        # Never a silent empty index (contracts/pipeline-cli.md).
        raise PipelineError(
            f"Extracted 0 passages from chapter {chapter.title!r} "
            f"(pages {chapter.start_page}-{chapter.end_page}). "
            "The chunker could not find any section headings - inspect the "
            "typographic role table before proceeding."
        )

    vectors = embed.embed_documents([p.embed_text() for p in passages])

    manifest = store.build_manifest(
        cfg,
        pdf_sha256=pdf_hash,
        cache_key=cache_key,
        page_range=(chapter.start_page, chapter.end_page),
        passage_count=len(passages),
    )
    store.save(cfg, passages, vectors, manifest)

    return IngestReport(
        chapter=chapter,
        passage_count=len(passages),
        image_count=len(images),
        elapsed_seconds=time.time() - started,
        cached=False,
    )
