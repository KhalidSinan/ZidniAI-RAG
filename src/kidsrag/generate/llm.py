"""OpenRouter transport.

One HTTP call against a documented endpoint needs no SDK. The mandated model
runs on a free tier where 429s are routine rather than exceptional, so retry
behaviour is product behaviour (Principle VI), and owning the transport makes
it explicit instead of buried in a client's defaults.
"""

from __future__ import annotations

import logging
import random
import time

import httpx

from ..config import Config
from ..errors import UpstreamError

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


def _sleep_for(attempt: int) -> float:
    """Exponential backoff with jitter: ~1s, ~2s, ~4s."""
    return min(2.0**attempt, 8.0) * (0.5 + random.random() / 2)


def complete(cfg: Config, messages: list[dict]) -> str:
    """Return the model's text, or raise UpstreamError.

    UpstreamError always becomes a Trouble, never a Refusal (SC-012):
    a service failure must never be presented as "the book doesn't say".
    """
    if not cfg.api_key:
        raise UpstreamError("OPENROUTER_API_KEY is not set")

    url = f"{cfg.generation.base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": cfg.generation.model,
        "messages": messages,
        "temperature": cfg.generation.temperature,
        "max_tokens": cfg.generation.max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
        "X-Title": "kidsrag",
    }

    last: str = "unknown error"
    for attempt in range(cfg.generation.max_retries + 1):
        try:
            with httpx.Client(timeout=cfg.generation.timeout_seconds) as client:
                response = client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                try:
                    data = response.json()
                    return data["choices"][0]["message"]["content"] or ""
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    raise UpstreamError(f"Malformed response body: {exc}") from exc

            last = f"HTTP {response.status_code}: {response.text[:200]}"
            if response.status_code not in RETRYABLE_STATUS:
                raise UpstreamError(last)

        except httpx.TimeoutException as exc:
            last = f"Timed out after {cfg.generation.timeout_seconds}s"
            log.warning("Attempt %s timed out: %s", attempt + 1, exc)
        except httpx.HTTPError as exc:
            last = f"Network error: {exc}"
            log.warning("Attempt %s failed: %s", attempt + 1, exc)

        if attempt < cfg.generation.max_retries:
            delay = _sleep_for(attempt)
            log.info("Retrying in %.1fs (attempt %s)", delay, attempt + 2)
            time.sleep(delay)

    raise UpstreamError(f"Giving up after {cfg.generation.max_retries + 1} attempts. {last}")
