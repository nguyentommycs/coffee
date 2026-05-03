"""
End-to-end integration test: full pipeline with real API calls and DB persistence.

Exercises: Input Parsing → Profiler → Recommendation → Critic (via Orchestrator)
with real Gemini API, Brave Search API, live roaster web scraping, and PostgreSQL.

Prerequisites:
  GOOGLE_API_KEY, BRAVE_API_KEY, DATABASE_URL must all be set (via .env or environment).

Run with:
    pytest tests/integration/test_e2e.py --integration -v -s

Expected runtime: ~30–90s for test_full_pipeline_e2e (15–25 Gemini calls + web scraping).
"""
import datetime

import pytest

from app.agents.orchestrator import parse_and_persist, run_recommendations
from app.config import settings
from app.db.connection import get_pool
from app.db.queries import get_recommendation_runs, get_taste_profile, insert_recommendation_run
from app.models.bean_profile import BeanProfile
from app.models.recommendation import RecommendationCandidate, RecommendationResponse
from app.models.taste_profile import TasteProfile

_no_gemini = not settings.google_api_key
_no_brave = not settings.brave_api_key
_no_apis = _no_gemini or _no_brave

# Three inputs covering all three input_type branches (url, freeform, freeform)
_BEAN_INPUTS = [
    "https://onyxcoffeelab.com/products/geometry",
    "Ethiopian Yirgacheffe washed light roast jasmine stone fruit",
    "Colombia Huila natural process medium light roast",
]


@pytest.mark.integration
@pytest.mark.skipif(_no_apis, reason="GOOGLE_API_KEY or BRAVE_API_KEY not set")
async def test_full_pipeline_e2e(test_user: str):
    """
    Full end-to-end pipeline: parse 3 real bean inputs, generate recommendations,
    verify output structure and DB persistence.
    """
    # ── Step 1: Parse and persist ──────────────────────────────────────────
    parsed, skipped = await parse_and_persist(test_user, _BEAN_INPUTS, 10)

    assert isinstance(parsed, list)
    assert isinstance(skipped, list)
    assert len(parsed) >= 2, (
        f"Expected at least 2 beans to parse successfully, got {len(parsed)}. "
        f"Skipped: {skipped}"
    )

    for profile in parsed:
        assert isinstance(profile, BeanProfile)
        assert profile.user_id == test_user
        assert profile.name, "BeanProfile must have a non-empty name"
        assert profile.roaster, "BeanProfile must have a non-empty roaster"
        assert 0.0 <= profile.confidence <= 1.0
        assert profile.input_raw

    # ── Step 2: Run full recommendations pipeline ──────────────────────────
    response = await run_recommendations(test_user, n_final=3)

    assert isinstance(response, RecommendationResponse)
    assert response.user_id == test_user

    # ── Step 3: Validate taste profile ────────────────────────────────────
    tp = response.taste_profile
    assert isinstance(tp.preferred_origins, list) and len(tp.preferred_origins) >= 1
    assert isinstance(tp.flavor_affinities, list)
    assert isinstance(tp.narrative_summary, str) and len(tp.narrative_summary) > 20
    assert tp.total_beans_logged >= 2

    # ── Step 4: Validate recommendations ──────────────────────────────────
    assert isinstance(response.recommendations, list)
    assert len(response.recommendations) >= 1, (
        "Expected at least 1 recommendation from the critic"
    )

    for c in response.recommendations:
        assert isinstance(c, RecommendationCandidate)
        assert c.name, "Candidate must have a non-empty name"
        assert c.roaster, "Candidate must have a non-empty roaster"
        assert str(c.product_url).startswith("http")
        assert 0.0 <= c.match_score <= 1.0
        assert isinstance(c.match_rationale, str) and len(c.match_rationale) > 0
        assert isinstance(c.tasting_notes, list)

    # Scores must be sorted descending (critic may re-rank)
    scores = [c.match_score for c in response.recommendations]
    assert scores == sorted(scores, reverse=True), "Recommendations must be sorted by score"

    assert isinstance(response.critic_notes, str) and len(response.critic_notes) > 10

    # ── Step 5: Verify DB persistence ─────────────────────────────────────
    stored_taste = await get_taste_profile(test_user)
    assert stored_taste is not None, "TasteProfile must be persisted to DB"
    assert stored_taste.user_id == test_user
    assert stored_taste.total_beans_logged >= 2

    pool = get_pool()
    run_count = await pool.fetchval(
        "SELECT COUNT(*) FROM recommendation_runs WHERE user_id = $1",
        test_user,
    )
    assert run_count == 1, "Exactly one recommendation run must be persisted to DB"


@pytest.mark.integration
async def test_get_recommendation_runs(test_user: str):
    """
    get_recommendation_runs returns persisted runs with the documented shape.
    """
    taste_profile = TasteProfile(
        user_id=test_user,
        preferred_origins=["Ethiopia"],
        preferred_processes=["Washed"],
        preferred_roast_levels=["Light"],
        flavor_affinities=["floral"],
        avoided_flavors=[],
        narrative_summary="Test profile summary",
        total_beans_logged=3,
        profile_confidence=0.8,
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    candidate = RecommendationCandidate(
        name="Test Bean",
        roaster="Test Roaster",
        product_url="https://example.com/bean",
        origin_country="Ethiopia",
        origin_region=None,
        farm_or_cooperative=None,
        process="Washed",
        variety=None,
        roast_level="Light",
        tasting_notes=["floral", "jasmine"],
        price_usd=18.0,
        in_stock=True,
        match_score=0.9,
        match_rationale="Great match",
    )
    await insert_recommendation_run(
        user_id=test_user,
        taste_profile=taste_profile,
        recommendations=[candidate],
        critic_notes="Solid picks.",
        trace={},
    )

    runs = await get_recommendation_runs(test_user)

    assert len(runs) == 1
    run = runs[0]
    assert "id" in run
    assert "created_at" in run
    assert run["critic_notes"] == "Solid picks."
    assert isinstance(run["recommendations"], list)
    assert len(run["recommendations"]) == 1
    assert run["recommendations"][0]["name"] == "Test Bean"
    assert isinstance(run["taste_profile_snapshot"], dict)
    assert run["taste_profile_snapshot"]["narrative_summary"] == "Test profile summary"


@pytest.mark.integration
@pytest.mark.skipif(_no_apis, reason="GOOGLE_API_KEY or BRAVE_API_KEY not set")
async def test_insufficient_beans_guard(test_user: str):
    """
    run_recommendations raises ValueError when user has fewer than 2 beans logged.
    The test_user fixture creates the user row but logs no beans.
    """
    with pytest.raises(ValueError, match="at least 3 beans"):
        await run_recommendations(test_user, n_final=3)
