"""Error types for the pipeline.

These are operator-facing. None of them is ever rendered to a child: the
rendering boundary in render.py accepts only Answer/Refusal/Trouble, and a
Trouble carries its technical cause in a field the renderer never reads.
"""


class PipelineError(Exception):
    """Base class for every error this package raises."""


class ConfigError(PipelineError):
    """Configuration is missing, malformed, or out of range."""


class ChapterNotFound(PipelineError):
    """The configured chapter title matched no entry in the PDF's TOC."""

    def __init__(self, title: str, available: list[str]):
        self.title = title
        self.available = available
        listing = "\n  ".join(available) if available else "(none found)"
        super().__init__(
            f"No chapter titled {title!r} in this PDF.\n"
            f"Available chapters:\n  {listing}"
        )


class AmbiguousChapter(PipelineError):
    """The configured chapter title matched more than one TOC entry."""

    def __init__(self, title: str, matches: list[str]):
        super().__init__(
            f"Chapter title {title!r} is ambiguous; it matches: {', '.join(matches)}"
        )


class ArtifactsMissing(PipelineError):
    """Chapter artifacts have not been built yet."""

    def __init__(self, path: str):
        super().__init__(
            f"No processed chapter found at {path}.\nRun: python -m kidsrag ingest"
        )


class UpstreamError(PipelineError):
    """The answering service failed after all retries were exhausted.

    Always maps to Trouble, never to Refusal (SC-012).
    """
