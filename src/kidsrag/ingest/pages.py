"""Render chapter pages to PNG.

Whole pages are the visual unit. This PDF stores each page as a single
full-page bitmap with no separately addressable figures, so cropping
individual diagrams would mean image segmentation - deferred as a
deadline trade-off (research.md section 3).

A page that fails to render is logged and skipped: a missing picture must
degrade to a text-only answer, never fail the whole ingest (FR-022).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pymupdf

from ..models import Chapter, PageImage

log = logging.getLogger(__name__)


def render_pages(
    doc: pymupdf.Document, chapter: Chapter, out_dir: Path, dpi: int = 150
) -> list[PageImage]:
    out_dir.mkdir(parents=True, exist_ok=True)
    images: list[PageImage] = []

    for pno in range(chapter.start_page, chapter.end_page + 1):
        target = out_dir / f"p{pno:03d}.png"
        try:
            pixmap = doc[pno - 1].get_pixmap(dpi=dpi)
            pixmap.save(str(target))
        except Exception as exc:  # noqa: BLE001 - one bad page must not abort
            log.warning("Could not render page %s: %s", pno, exc)
            continue
        images.append(PageImage(page=pno, path=str(target), dpi=dpi))

    return images


def page_image_map(images: list[PageImage], root: Path) -> dict[int, str]:
    """Page number -> path relative to the chapter artifacts directory."""
    out: dict[int, str] = {}
    for img in images:
        try:
            out[img.page] = str(Path(img.path).relative_to(root).as_posix())
        except ValueError:
            out[img.page] = img.path
    return out
