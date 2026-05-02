"""
Thin async wrapper around Google Generative AI (Gemini).

All agents call `llm_complete(prompt)` for structured JSON extraction.
The function returns the raw text so callers can json.loads() it themselves,
matching the pattern shown in the PRD.
"""
import asyncio
import logging
import re
import time
from datetime import datetime, timezone

from google import genai
from google.genai import errors, types

from app.config import settings
from app.observability.llm_logger import LLMCallRecord

logger = logging.getLogger(__name__)

_client: genai.Client | None = None
_last_call_at: float = 0.0
_MIN_CALL_INTERVAL_S = 1.0  # light throttle to reduce 429 frequency


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        _client = genai.Client(api_key=settings.google_api_key)
    return _client


def _generate(client: genai.Client, prompt: str) -> genai.types.GenerateContentResponse:
    return client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
        ),
    )


async def llm_complete(prompt: str, span: str = "unknown") -> str:
    """
    Send a prompt to Gemini and return the response text.
    Logs an LLMCallRecord for observability.

    All agents expect plain JSON back — prompts should end with
    'Return only valid JSON. No preamble, no markdown fences.'

    Retries once on HTTP 429 using the delay the API reports.
    A 1s minimum interval between calls reduces 429 frequency.
    """
    global _last_call_at

    elapsed = time.monotonic() - _last_call_at
    if elapsed < _MIN_CALL_INTERVAL_S:
        await asyncio.sleep(_MIN_CALL_INTERVAL_S - elapsed)

    client = _get_client()
    t0 = time.monotonic()
    _last_call_at = time.monotonic()

    try:
        response = _generate(client, prompt)
    except errors.ClientError as exc:
        if exc.code != 429:
            raise
        match = re.search(r"retry in (\d+(?:\.\d+)?)", str(exc), re.IGNORECASE)
        delay = float(match.group(1)) if match else 30.0
        logger.warning("429 rate limit; sleeping %.0fs before retry (span=%s)", delay, span)
        await asyncio.sleep(delay)
        _last_call_at = time.monotonic()
        response = _generate(client, prompt)  # final attempt — raises if still 429

    latency_ms = (time.monotonic() - t0) * 1000
    text = response.text.strip()

    # Strip markdown code fences if Gemini wraps the JSON anyway
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        usage = response.usage_metadata
        record = LLMCallRecord(
            span=span,
            model=settings.gemini_model,
            input_tokens=usage.prompt_token_count,
            output_tokens=usage.candidates_token_count,
            latency_ms=round(latency_ms, 2),
            timestamp=datetime.now(timezone.utc),
        )
        logger.debug("LLM call: %s", record.model_dump())
    except Exception:
        pass  # observability must never break the happy path

    return text
