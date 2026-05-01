"""
Unit tests for app/agents/input_parsing.py.

All external I/O is mocked: llm_complete, web_search, scrape_page.
"""
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.agents.input_parsing import AgentLoopError, LLMOutputError, run
from app.tools.search import SearchResult

ONYX_URL = "https://onyxcoffeelab.com/products/geometry"

_FULL_LLM_RESPONSE = json.dumps({
    "name": "Geometry",
    "roaster": "Onyx Coffee Lab",
    "origin_country": "Ethiopia",
    "origin_region": "Yirgacheffe",
    "farm_or_cooperative": "Dumerso Cooperative",
    "process": "Washed",
    "variety": "Heirloom",
    "roast_level": "Light",
    "tasting_notes": ["jasmine", "peach", "meyer lemon"],
    "confidence": 0.9,
    "missing_fields": [],
})

_SEARCH_RESULT = SearchResult(
    title="Geometry | Onyx Coffee Lab",
    url=ONYX_URL,
    snippet="Ethiopian light roast",
)


@pytest.mark.asyncio
async def test_url_happy_path():
    with (
        patch("app.agents.input_parsing.scrape_page", new_callable=AsyncMock) as mock_scrape,
        patch("app.agents.input_parsing.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_scrape.return_value = "Some product page text"
        mock_llm.return_value = _FULL_LLM_RESPONSE

        profile = await run(ONYX_URL, "user1")

    assert profile.name == "Geometry"
    assert profile.roaster == "Onyx Coffee Lab"
    assert profile.origin_country == "Ethiopia"
    assert profile.process == "Washed"
    assert profile.roast_level == "Light"
    assert profile.confidence >= 0.8
    assert profile.input_type == "url"
    assert profile.input_raw == ONYX_URL
    assert str(profile.source_url).rstrip("/") == ONYX_URL.rstrip("/")


@pytest.mark.asyncio
async def test_name_search_scrape():
    with (
        patch("app.agents.input_parsing.web_search", new_callable=AsyncMock) as mock_search,
        patch("app.agents.input_parsing.scrape_page", new_callable=AsyncMock) as mock_scrape,
        patch("app.agents.input_parsing.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_search.return_value = [_SEARCH_RESULT]
        mock_scrape.return_value = "Geometry page text"
        mock_llm.return_value = _FULL_LLM_RESPONSE

        profile = await run("Onyx Geometry", "user1")

    assert profile.input_type == "name"
    assert profile.name == "Geometry"
    mock_search.assert_called_once()


@pytest.mark.asyncio
async def test_freeform_input():
    with (
        patch("app.agents.input_parsing.web_search", new_callable=AsyncMock) as mock_search,
        patch("app.agents.input_parsing.scrape_page", new_callable=AsyncMock) as mock_scrape,
        patch("app.agents.input_parsing.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_search.return_value = [_SEARCH_RESULT]
        mock_scrape.return_value = "Some text"
        mock_llm.return_value = _FULL_LLM_RESPONSE

        profile = await run("I had a really nice Ethiopian last week", "user1")

    assert profile.input_type == "freeform"


@pytest.mark.asyncio
async def test_low_confidence_triggers_retry():
    low_conf = json.dumps({
        "name": "Unknown Bean",
        "roaster": "Unknown",
        "origin_country": None,
        "origin_region": None,
        "farm_or_cooperative": None,
        "process": None,
        "variety": None,
        "roast_level": None,
        "tasting_notes": [],
        "confidence": 0.4,
        "missing_fields": ["origin_country", "origin_region", "process", "roast_level", "variety"],
    })

    with (
        patch("app.agents.input_parsing.web_search", new_callable=AsyncMock) as mock_search,
        patch("app.agents.input_parsing.scrape_page", new_callable=AsyncMock) as mock_scrape,
        patch("app.agents.input_parsing.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_search.return_value = [_SEARCH_RESULT]
        mock_scrape.return_value = "Some text"
        # First call: low confidence; second call (broader retry): full result
        mock_llm.side_effect = [low_conf, _FULL_LLM_RESPONSE]

        profile = await run("Onyx Geometry", "user1")

    assert mock_llm.call_count == 2
    assert profile.confidence == 0.9


@pytest.mark.asyncio
async def test_invalid_json_then_valid():
    with (
        patch("app.agents.input_parsing.scrape_page", new_callable=AsyncMock) as mock_scrape,
        patch("app.agents.input_parsing.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_scrape.return_value = "page text"
        mock_llm.side_effect = ["not valid json {{", _FULL_LLM_RESPONSE]

        profile = await run(ONYX_URL, "user1")

    assert profile.name == "Geometry"
    assert mock_llm.call_count == 2


@pytest.mark.asyncio
async def test_invalid_json_both_attempts_raises():
    with (
        patch("app.agents.input_parsing.scrape_page", new_callable=AsyncMock) as mock_scrape,
        patch("app.agents.input_parsing.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_scrape.return_value = "page text"
        mock_llm.return_value = "not json at all"

        with pytest.raises(LLMOutputError):
            await run(ONYX_URL, "user1")


@pytest.mark.asyncio
async def test_url_scrape_404_falls_back_to_search():
    with (
        patch("app.agents.input_parsing.web_search", new_callable=AsyncMock) as mock_search,
        patch("app.agents.input_parsing.scrape_page", new_callable=AsyncMock) as mock_scrape,
        patch("app.agents.input_parsing.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        # First scrape (URL) raises; second scrape (after search fallback) succeeds
        mock_scrape.side_effect = [
            httpx.HTTPStatusError("404", request=None, response=None),
            "page text after fallback",
        ]
        mock_search.return_value = [_SEARCH_RESULT]
        mock_llm.return_value = _FULL_LLM_RESPONSE

        profile = await run(ONYX_URL, "user1")

    assert profile.name == "Geometry"
    assert mock_search.call_count == 1


@pytest.mark.asyncio
async def test_empty_scrape_low_confidence():
    with (
        patch("app.agents.input_parsing.scrape_page", new_callable=AsyncMock) as mock_scrape,
        patch("app.agents.input_parsing.llm_complete", new_callable=AsyncMock) as mock_llm,
        patch("app.agents.input_parsing.web_search", new_callable=AsyncMock) as mock_search,
    ):
        mock_scrape.return_value = ""
        mock_search.return_value = [_SEARCH_RESULT]
        # Even if LLM claims high confidence, empty page caps it at 0.1
        mock_llm.return_value = json.dumps({
            "name": "Geometry",
            "roaster": "Onyx Coffee Lab",
            "origin_country": None,
            "origin_region": None,
            "farm_or_cooperative": None,
            "process": None,
            "variety": None,
            "roast_level": None,
            "tasting_notes": [],
            "confidence": 0.9,
            "missing_fields": [],
        })

        profile = await run(ONYX_URL, "user1")

    assert profile.confidence <= 0.1
    assert "origin_country" in profile.missing_fields


@pytest.mark.asyncio
async def test_no_search_results_partial_profile():
    with (
        patch("app.agents.input_parsing.web_search", new_callable=AsyncMock) as mock_search,
        patch("app.agents.input_parsing.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_search.return_value = []
        mock_llm.return_value = json.dumps({
            "name": "Onyx Geometry",
            "roaster": "Unknown",
            "origin_country": None,
            "origin_region": None,
            "farm_or_cooperative": None,
            "process": None,
            "variety": None,
            "roast_level": None,
            "tasting_notes": [],
            "confidence": 0.3,
            "missing_fields": ["origin_country", "origin_region", "process", "roast_level", "variety"],
        })

        profile = await run("Onyx Geometry", "user1")

    # Empty page_text (no URL resolved) caps confidence to 0.1
    assert profile.confidence <= 0.1
    assert profile.source_url is None


@pytest.mark.asyncio
async def test_process_normalization_lowercase():
    llm_response = json.dumps({
        "name": "Geometry",
        "roaster": "Onyx Coffee Lab",
        "origin_country": "Ethiopia",
        "origin_region": None,
        "farm_or_cooperative": None,
        "process": "washed",
        "variety": None,
        "roast_level": "light",
        "tasting_notes": ["jasmine"],
        "confidence": 0.85,
        "missing_fields": [],
    })

    with (
        patch("app.agents.input_parsing.scrape_page", new_callable=AsyncMock) as mock_scrape,
        patch("app.agents.input_parsing.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_scrape.return_value = "page text"
        mock_llm.return_value = llm_response

        profile = await run(ONYX_URL, "user1")

    assert profile.process == "Washed"
    assert profile.roast_level == "Light"
    assert "process" not in profile.missing_fields
