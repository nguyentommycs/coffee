"""
Integration tests — hit real APIs using keys from .env.

Skipped by default. Run with:
    pytest tests/test_integration.py --integration -v

Both GOOGLE_API_KEY and BRAVE_API_KEY must be set (via .env or environment).
Tests for each service are also skipped if the corresponding key is absent.
"""
import json
import pytest

from app.config import settings
from app.llm import llm_complete
from app.tools.search import web_search

_no_gemini = not settings.google_api_key
_no_brave = not settings.brave_api_key


# ---------------------------------------------------------------------------
# Gemini / Google Generative AI
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(_no_gemini, reason="GOOGLE_API_KEY not set")
async def test_gemini_returns_valid_json():
    prompt = (
        "Extract coffee tasting notes from this text: "
        "'A bright Ethiopian with jasmine florals, peach sweetness, and Meyer lemon acidity.' "
        "Return JSON with a single key 'tasting_notes' containing a list of strings. "
        "Return only valid JSON. No preamble, no markdown fences."
    )
    result = await llm_complete(prompt, span="test_integration")
    parsed = json.loads(result)
    assert "tasting_notes" in parsed
    assert isinstance(parsed["tasting_notes"], list)
    assert len(parsed["tasting_notes"]) > 0
    combined = " ".join(parsed["tasting_notes"]).lower()
    assert any(note in combined for note in ("jasmine", "peach", "lemon"))


@pytest.mark.integration
@pytest.mark.skipif(_no_gemini, reason="GOOGLE_API_KEY not set")
async def test_gemini_classifies_roast_level():
    prompt = (
        "Given: 'Dark roasted Colombia Huila with notes of dark chocolate and brown sugar.' "
        'Return JSON: {"roast_level": "<light|medium|medium-dark|dark>"} '
        "Return only valid JSON. No preamble, no markdown fences."
    )
    result = await llm_complete(prompt, span="test_integration")
    parsed = json.loads(result)
    assert "roast_level" in parsed
    assert parsed["roast_level"] in {"light", "medium", "medium-dark", "dark"}


@pytest.mark.integration
@pytest.mark.skipif(_no_gemini, reason="GOOGLE_API_KEY not set")
async def test_gemini_extracts_origin():
    prompt = (
        "Extract coffee origin info from: "
        "'Yirgacheffe, Ethiopia — grown at 1900m, washed process, variety: heirloom.' "
        "Return JSON with keys: origin_country, origin_region, process. "
        "Return only valid JSON. No preamble, no markdown fences."
    )
    result = await llm_complete(prompt, span="test_integration")
    parsed = json.loads(result)
    assert parsed.get("origin_country", "").lower() in {"ethiopia", "ethiopian"}
    assert "yirgacheffe" in parsed.get("origin_region", "").lower()
    assert "washed" in parsed.get("process", "").lower()


# ---------------------------------------------------------------------------
# Brave Search API
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(_no_brave, reason="BRAVE_API_KEY not set")
async def test_brave_returns_results():
    results = await web_search("Onyx Coffee Lab single origin Ethiopian", n_results=3)
    assert len(results) > 0
    for r in results:
        assert r.title
        assert r.url.startswith("http")


@pytest.mark.integration
@pytest.mark.skipif(_no_brave, reason="BRAVE_API_KEY not set")
async def test_brave_result_has_all_fields():
    results = await web_search("light roast washed process coffee", n_results=2)
    assert len(results) > 0
    for r in results:
        assert isinstance(r.title, str)
        assert isinstance(r.url, str)
        assert isinstance(r.snippet, str)


@pytest.mark.integration
@pytest.mark.skipif(_no_brave, reason="BRAVE_API_KEY not set")
async def test_brave_filters_blocked_domains():
    results = await web_search("buy Ethiopian coffee amazon reddit review", n_results=5)
    blocked = {"amazon.com", "beanconqueror.com", "reddit.com", "coffeereview.com"}
    for r in results:
        assert not any(domain in r.url for domain in blocked), (
            f"Blocked domain found in result: {r.url}"
        )


@pytest.mark.integration
@pytest.mark.skipif(_no_brave, reason="BRAVE_API_KEY not set")
async def test_brave_prefers_known_roasters():
    preferred = {
        "onyxcoffeelab.com",
        "bluebottlecoffee.com",
        "counterculturecoffee.com",
        "sweetbloomcoffee.com",
        "intelligentsia.com",
        "stumptown.com",
        "heartroasters.com",
    }
    results = await web_search("buy specialty coffee beans", n_results=5)
    preferred_indices = [
        i for i, r in enumerate(results) if any(d in r.url for d in preferred)
    ]
    other_indices = [
        i for i, r in enumerate(results) if not any(d in r.url for d in preferred)
    ]
    if preferred_indices and other_indices:
        assert min(preferred_indices) < max(other_indices), (
            "Expected preferred roasters to appear before non-preferred results"
        )
