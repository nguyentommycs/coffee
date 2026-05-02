"""
Input Parsing Agent.

Accepts a raw user input (URL, bean name, or freeform text) and returns a
validated BeanProfile. Persistence is the orchestrator's responsibility.

Control flow is deterministic Python with one LLM extraction call and a
retry budget (MAX_ITERATIONS). No LLM tool-calling surface is used because
llm_complete returns plain text.
"""
import json
import logging
from urllib.parse import urlparse

import httpx

from app.llm import llm_complete
from app.models.bean_profile import BeanProfile
from app.tools.detect_input import detect_input_type
from app.tools.scraper import scrape_page
from app.tools.search import SearchResult, web_search

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5

_PROCESS_MAP = {
    "washed": "Washed",
    "natural": "Natural",
    "honey": "Honey",
    "anaerobic": "Anaerobic",
}
_ROAST_MAP = {
    "light": "Light",
    "medium-light": "Medium-Light",
    "medium": "Medium",
    "dark": "Dark",
}

_EXTRACT_PROMPT_TEMPLATE = """\
You are a coffee data extraction specialist. Given scraped text from a coffee \
roaster's product page, extract the following fields into a JSON object matching \
this schema:

{{
  "name": string,
  "roaster": string,
  "origin_country": string | null,
  "origin_region": string | null,
  "farm_or_cooperative": string | null,
  "process": "Washed" | "Natural" | "Honey" | "Anaerobic" | null,
  "variety": string | null,
  "roast_level": "Light" | "Medium-Light" | "Medium" | "Dark" | null,
  "tasting_notes": string[],
  "confidence": float (0.0 to 1.0),
  "missing_fields": string[]
}}

Rules:
- Only extract information explicitly present in the text. Do not infer or hallucinate.
- Normalize process names to: Washed, Natural, Honey, or Anaerobic.
- Normalize roast levels to: Light, Medium-Light, Medium, or Dark.
- Tasting notes should be lowercase, individual flavor descriptors \
(e.g., ["peach", "jasmine", "brown sugar"]).
- confidence reflects how complete and unambiguous the extracted data is.
- missing_fields lists the field names (as strings) that could not be extracted.
- Return only valid JSON. No preamble, no markdown fences.

Source URL: {url}
Raw input: {raw_input}

Scraped text:
{text}
"""

_SCHEMA_REMINDER = (
    "\n\nIMPORTANT: Your previous response was not valid JSON. "
    "Return ONLY a valid JSON object matching the schema above. "
    "No preamble, no markdown fences."
)


class AgentLoopError(Exception):
    def __init__(self, msg: str, partial_result: BeanProfile | None = None):
        super().__init__(msg)
        self.partial_result = partial_result


class LowConfidenceError(Exception):
    def __init__(self, msg: str, missing_fields: list[str], input_raw: str):
        super().__init__(msg)
        self.missing_fields = missing_fields
        self.input_raw = input_raw


class LLMOutputError(Exception):
    pass


def _normalize(value: str | None, mapping: dict[str, str]) -> str | None:
    if value is None:
        return None
    return mapping.get(value.lower().strip())


def _best_url(results: list[SearchResult]) -> str | None:
    return results[0].url if results else None


def _url_fallback_query(url: str) -> str:
    path = urlparse(url).path
    segments = [s for s in path.split("/") if s and s not in ("products", "collections", "en", "us")]
    name_hint = " ".join(segments[-2:]) if segments else ""
    return f"{name_hint} coffee bean roaster tasting notes".strip()


async def _resolve_url(raw_input: str, input_type: str) -> tuple[str | None, str]:
    """Return (url, page_text). page_text is '' if scrape fails or url is None."""
    if input_type == "url":
        url = raw_input
        try:
            page_text = await scrape_page(url)
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Scrape failed for %s (%s); falling back to search", url, exc)
            query = _url_fallback_query(url)
            results = await web_search(query)
            url = _best_url(results)
            page_text = await scrape_page(url) if url else ""
        return url, page_text

    # name or freeform
    query = f"{raw_input} coffee bean roaster tasting notes"
    results = await web_search(query)
    url = _best_url(results)
    if url is None:
        return None, ""
    try:
        page_text = await scrape_page(url)
    except (httpx.HTTPError, Exception) as exc:
        logger.warning("Scrape failed for %s (%s)", url, exc)
        page_text = ""
    return url, page_text


async def _extract_bean_schema(
    text: str,
    url: str | None,
    raw_input: str,
    extra_suffix: str = "",
) -> dict:
    prompt = _EXTRACT_PROMPT_TEMPLATE.format(
        url=url or "unknown",
        raw_input=raw_input,
        text=text or "(no content retrieved)",
    ) + extra_suffix

    raw = await llm_complete(prompt, span="input_parsing")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # One retry with explicit schema reminder
        raw2 = await llm_complete(prompt + _SCHEMA_REMINDER, span="input_parsing_retry")
        try:
            return json.loads(raw2)
        except json.JSONDecodeError as exc:
            raise LLMOutputError(f"LLM did not return valid JSON after retry: {raw2!r}") from exc


def _build_profile(
    data: dict,
    user_id: str,
    raw_input: str,
    input_type: str,
    url: str | None,
    page_text: str,
    user_score: int | None = None,
) -> BeanProfile:
    missing: list[str] = list(data.get("missing_fields") or [])

    process = _normalize(data.get("process"), _PROCESS_MAP)
    if data.get("process") and process is None:
        missing.append("process")

    roast_level = _normalize(data.get("roast_level"), _ROAST_MAP)
    if data.get("roast_level") and roast_level is None:
        missing.append("roast_level")

    confidence = float(data.get("confidence", 0.0))
    if not page_text:
        confidence = min(confidence, 0.1)
        for f in ("origin_country", "origin_region", "farm_or_cooperative", "process", "variety", "roast_level"):
            if f not in missing:
                missing.append(f)

    return BeanProfile(
        user_id=user_id,
        name=data.get("name") or raw_input,
        roaster=data.get("roaster") or "Unknown",
        source_url=url or None,
        origin_country=data.get("origin_country"),
        origin_region=data.get("origin_region"),
        farm_or_cooperative=data.get("farm_or_cooperative"),
        process=process,
        variety=data.get("variety"),
        roast_level=roast_level,
        tasting_notes=data.get("tasting_notes") or [],
        user_score=user_score,
        confidence=confidence,
        missing_fields=missing,
        input_raw=raw_input,
        input_type=input_type,
    )


async def run(raw_input: str, user_id: str, user_score: int | None = None) -> BeanProfile:
    """
    Parse a single raw input string into a BeanProfile.
    Does not persist to DB — that is the orchestrator's job.
    user_score is provided externally (e.g. a UI selector) and passed through unchanged.
    """
    input_type = detect_input_type(raw_input)
    last_profile: BeanProfile | None = None

    for iteration in range(MAX_ITERATIONS):
        if iteration == 0:
            url, page_text = await _resolve_url(raw_input, input_type)
            broader = False
        else:
            # Broader retry: relax to generic query
            query = f"{raw_input} specialty coffee"
            results = await web_search(query)
            url = _best_url(results)
            page_text = await scrape_page(url) if url else ""
            broader = True

        try:
            data = await _extract_bean_schema(page_text, url, raw_input)
        except LLMOutputError:
            if last_profile is not None:
                return last_profile
            raise

        profile = _build_profile(data, user_id, raw_input, input_type, url, page_text, user_score)
        last_profile = profile

        needs_retry = profile.confidence < 0.6 or len(profile.missing_fields) > 3
        if not needs_retry or broader:
            return profile

        logger.info(
            "Input parsing: low confidence (%.2f) or many missing fields (%d); retrying (iter %d)",
            profile.confidence,
            len(profile.missing_fields),
            iteration + 1,
        )

    raise AgentLoopError(
        f"Input parsing exceeded {MAX_ITERATIONS} iterations for input: {raw_input!r}",
        partial_result=last_profile,
    )
