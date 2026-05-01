"""
Unit tests for app/agents/recommendation.py.

All external I/O is mocked: scrape_roaster_catalog, scrape_page, llm_complete.
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.recommendation import ROASTERS, run
from app.models.taste_profile import TasteProfile

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def taste_profile():
    return TasteProfile(
        user_id="u1",
        preferred_origins=["Ethiopia", "Colombia"],
        preferred_processes=["Washed"],
        preferred_roast_levels=["Light"],
        flavor_affinities=["stone fruit", "floral", "citrus"],
        avoided_flavors=["smoke", "earthy"],
        narrative_summary="Prefers light, floral East African coffees.",
        total_beans_logged=3,
        profile_confidence=0.9,
    )


_CATALOG_ONYX = [
    {"name": "Geometry", "url": "https://onyxcoffeelab.com/products/geometry", "price_usd": 22.0},
    {"name": "Monarch", "url": "https://onyxcoffeelab.com/products/monarch", "price_usd": 18.0},
]

_EXTRACT_MATCH = json.dumps({
    "origin_country": "Ethiopia",
    "origin_region": "Yirgacheffe",
    "process": "Washed",
    "roast_level": "Light",
    "tasting_notes": ["jasmine", "stone fruit", "citrus"],
    "in_stock": True,
})

_EXTRACT_NO_MATCH = json.dumps({
    "origin_country": "Brazil",
    "origin_region": None,
    "process": "Natural",
    "roast_level": "Dark",
    "tasting_notes": ["dark chocolate", "smoke"],
    "in_stock": True,
})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_returns_scored_candidates(taste_profile):
    with (
        patch("app.agents.recommendation.scrape_roaster_catalog", new_callable=AsyncMock) as mock_catalog,
        patch("app.agents.recommendation.scrape_page", new_callable=AsyncMock) as mock_scrape,
        patch("app.agents.recommendation.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_catalog.side_effect = [_CATALOG_ONYX, [], [], []]
        mock_scrape.return_value = "some product page text"
        mock_llm.return_value = _EXTRACT_MATCH

        candidates = await run(taste_profile, n_recommendations=5)

    assert len(candidates) > 0
    assert all(c.match_score >= 0 for c in candidates)
    assert all(c.match_rationale != "" for c in candidates)


@pytest.mark.asyncio
async def test_candidates_sorted_by_match_score(taste_profile):
    with (
        patch("app.agents.recommendation.scrape_roaster_catalog", new_callable=AsyncMock) as mock_catalog,
        patch("app.agents.recommendation.scrape_page", new_callable=AsyncMock),
        patch("app.agents.recommendation.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_catalog.side_effect = [_CATALOG_ONYX, [], [], []]
        # Geometry → high match, Monarch → no match
        mock_llm.side_effect = [_EXTRACT_MATCH, _EXTRACT_NO_MATCH]

        candidates = await run(taste_profile, n_recommendations=5)

    assert len(candidates) == 2
    assert candidates[0].match_score >= candidates[1].match_score
    assert candidates[0].name == "Geometry"


@pytest.mark.asyncio
async def test_empty_all_catalogs_returns_empty(taste_profile):
    with patch("app.agents.recommendation.scrape_roaster_catalog", new_callable=AsyncMock) as mock_catalog:
        mock_catalog.return_value = []

        candidates = await run(taste_profile)

    assert candidates == []


@pytest.mark.asyncio
async def test_normal_mode_scrapes_only_first_4_roasters(taste_profile):
    with (
        patch("app.agents.recommendation.scrape_roaster_catalog", new_callable=AsyncMock) as mock_catalog,
        patch("app.agents.recommendation.scrape_page", new_callable=AsyncMock),
        patch("app.agents.recommendation.llm_complete", new_callable=AsyncMock),
    ):
        mock_catalog.return_value = []

        await run(taste_profile, broad_mode=False)

    assert mock_catalog.call_count == 4
    called_urls = {call.args[0] for call in mock_catalog.call_args_list}
    expected_urls = {url for _, url in ROASTERS[:4]}
    assert called_urls == expected_urls


@pytest.mark.asyncio
async def test_broad_mode_scrapes_all_8_roasters(taste_profile):
    with (
        patch("app.agents.recommendation.scrape_roaster_catalog", new_callable=AsyncMock) as mock_catalog,
        patch("app.agents.recommendation.scrape_page", new_callable=AsyncMock),
        patch("app.agents.recommendation.llm_complete", new_callable=AsyncMock),
    ):
        mock_catalog.return_value = []

        await run(taste_profile, broad_mode=True)

    assert mock_catalog.call_count == 8


@pytest.mark.asyncio
async def test_returns_at_most_n_times_2(taste_profile):
    many_items = [
        {"name": f"Bean {i}", "url": f"https://onyxcoffeelab.com/products/bean-{i}", "price_usd": 20.0}
        for i in range(20)
    ]
    with (
        patch("app.agents.recommendation.scrape_roaster_catalog", new_callable=AsyncMock) as mock_catalog,
        patch("app.agents.recommendation.scrape_page", new_callable=AsyncMock),
        patch("app.agents.recommendation.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_catalog.side_effect = [many_items, [], [], []]
        mock_llm.return_value = _EXTRACT_MATCH

        candidates = await run(taste_profile, n_recommendations=5)

    assert len(candidates) <= 10  # 5 * 2


@pytest.mark.asyncio
async def test_candidates_per_roaster_cap_applied(taste_profile):
    """Verifies that at most CANDIDATES_PER_ROASTER items are scraped per roaster."""
    from app.agents.recommendation import CANDIDATES_PER_ROASTER

    many_items = [
        {"name": f"Bean {i}", "url": f"https://onyxcoffeelab.com/products/bean-{i}", "price_usd": 20.0}
        for i in range(CANDIDATES_PER_ROASTER + 5)
    ]
    with (
        patch("app.agents.recommendation.scrape_roaster_catalog", new_callable=AsyncMock) as mock_catalog,
        patch("app.agents.recommendation.scrape_page", new_callable=AsyncMock) as mock_scrape,
        patch("app.agents.recommendation.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_catalog.side_effect = [many_items, [], [], []]
        mock_llm.return_value = _EXTRACT_MATCH

        await run(taste_profile, n_recommendations=20)

    assert mock_scrape.call_count <= CANDIDATES_PER_ROASTER


@pytest.mark.asyncio
async def test_invalid_url_items_skipped(taste_profile):
    with (
        patch("app.agents.recommendation.scrape_roaster_catalog", new_callable=AsyncMock) as mock_catalog,
        patch("app.agents.recommendation.scrape_page", new_callable=AsyncMock),
        patch("app.agents.recommendation.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_catalog.side_effect = [
            [
                {"name": "", "url": "https://onyxcoffeelab.com/products/geometry", "price_usd": 20.0},
                {"name": "Geometry", "url": "", "price_usd": 20.0},
                {"name": "Monarch", "url": "https://onyxcoffeelab.com/products/monarch", "price_usd": 18.0},
            ],
            [], [], [],
        ]
        mock_llm.return_value = _EXTRACT_MATCH

        candidates = await run(taste_profile)

    assert len(candidates) == 1
    assert candidates[0].name == "Monarch"


@pytest.mark.asyncio
async def test_llm_extraction_failure_yields_unscored_candidate(taste_profile):
    """Both JSON attempts fail → candidate still included with score=0 and no attributes."""
    with (
        patch("app.agents.recommendation.scrape_roaster_catalog", new_callable=AsyncMock) as mock_catalog,
        patch("app.agents.recommendation.scrape_page", new_callable=AsyncMock),
        patch("app.agents.recommendation.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_catalog.side_effect = [
            [{"name": "Geometry", "url": "https://onyxcoffeelab.com/products/geometry", "price_usd": 22.0}],
            [], [], [],
        ]
        mock_llm.side_effect = ["bad json #1", "bad json #2"]

        candidates = await run(taste_profile)

    assert len(candidates) == 1
    assert candidates[0].match_score == 0.0
    assert candidates[0].origin_country is None
    assert candidates[0].tasting_notes == []


@pytest.mark.asyncio
async def test_match_score_and_rationale_populated(taste_profile):
    with (
        patch("app.agents.recommendation.scrape_roaster_catalog", new_callable=AsyncMock) as mock_catalog,
        patch("app.agents.recommendation.scrape_page", new_callable=AsyncMock),
        patch("app.agents.recommendation.llm_complete", new_callable=AsyncMock) as mock_llm,
    ):
        mock_catalog.side_effect = [
            [{"name": "Geometry", "url": "https://onyxcoffeelab.com/products/geometry", "price_usd": 22.0}],
            [], [], [],
        ]
        mock_llm.return_value = _EXTRACT_MATCH

        candidates = await run(taste_profile)

    assert len(candidates) == 1
    assert candidates[0].match_score > 0
    assert "origin match" in candidates[0].match_rationale
    assert candidates[0].origin_country == "Ethiopia"
    assert candidates[0].process == "Washed"
