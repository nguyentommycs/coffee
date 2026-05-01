"""
Integration tests for app/agents/recommendation.py.

Makes real HTTP requests to roaster websites and real Gemini API calls.
Skipped by default — run with:
    pytest tests/integration/ --integration -v

Requires GOOGLE_API_KEY in .env or environment.
"""
import pytest

from app.agents import recommendation
from app.config import settings
from app.models.recommendation import RecommendationCandidate
from app.models.taste_profile import TasteProfile

_no_gemini = not settings.google_api_key

_PROFILE = TasteProfile(
    user_id="integration-test-user",
    preferred_origins=["Ethiopia", "Colombia"],
    preferred_processes=["Washed", "Natural"],
    preferred_roast_levels=["Light", "Medium-Light"],
    flavor_affinities=["stone fruit", "floral", "citrus"],
    avoided_flavors=["smoke", "earthy"],
    narrative_summary="Prefers light, fruit-forward coffees from East Africa and South America.",
    total_beans_logged=3,
    profile_confidence=0.88,
)


@pytest.mark.integration
@pytest.mark.skipif(_no_gemini, reason="GOOGLE_API_KEY not set")
async def test_recommendation_run_returns_valid_candidates():
    """
    Full run against real roaster sites: scrape catalogs, extract via LLM, score.
    Asserts output structure without relying on specific bean names (sites change).
    """
    candidates = await recommendation.run(_PROFILE, n_recommendations=5)

    assert isinstance(candidates, list)
    print(candidates)
    # Roaster sites are live — we may get 0 if all scrapes fail, but if any succeed,
    # they must be well-formed and sorted.
    for c in candidates:
        assert isinstance(c, RecommendationCandidate)
        assert c.name
        assert c.roaster
        assert str(c.product_url).startswith("http")
        assert 0.0 <= c.match_score <= 1.0
        assert isinstance(c.match_rationale, str)
        assert isinstance(c.tasting_notes, list)

    # Results must be sorted by match_score descending
    scores = [c.match_score for c in candidates]
    assert scores == sorted(scores, reverse=True)

    # Cap respected: at most n_recommendations * 2
    assert len(candidates) <= 10


@pytest.mark.integration
@pytest.mark.skipif(_no_gemini, reason="GOOGLE_API_KEY not set")
async def test_recommendation_broad_mode_reaches_more_roasters():
    """
    broad_mode=True should attempt all 8 roasters; normal mode attempts 4.
    We verify broad mode returns >= as many candidates and does not raise.
    """
    normal_candidates = await recommendation.run(_PROFILE, n_recommendations=5, broad_mode=False)
    broad_candidates = await recommendation.run(_PROFILE, n_recommendations=5, broad_mode=True)

    # Both must return valid lists
    assert isinstance(normal_candidates, list)
    assert isinstance(broad_candidates, list)

    for c in broad_candidates:
        assert isinstance(c, RecommendationCandidate)
        assert 0.0 <= c.match_score <= 1.0

    # Broad mode searches twice as many roasters, so it should surface at least as many
    # candidates (barring all extra roasters being completely unreachable).
    assert len(broad_candidates) >= len(normal_candidates)
