"""
Integration tests for app/agents/critic.py.

Makes real Gemini API calls. Skipped by default — run with:
    pytest tests/integration/ --integration -v

Requires GOOGLE_API_KEY in .env or environment.
"""
import pytest

from app.agents import critic
from app.config import settings
from app.models.recommendation import RecommendationCandidate
from app.models.taste_profile import TasteProfile

_no_gemini = not settings.google_api_key

_PROFILE = TasteProfile(
    user_id="integration-test-user",
    preferred_origins=["Ethiopia", "Colombia"],
    preferred_processes=["Washed"],
    preferred_roast_levels=["Light", "Medium-Light"],
    flavor_affinities=["stone fruit", "floral", "citrus"],
    avoided_flavors=["smoke", "earthy"],
    narrative_summary="Prefers light, floral coffees from East Africa with stone fruit and citrus notes.",
    total_beans_logged=4,
    profile_confidence=0.88,
)

# Mix of strong matches, weak matches, same-roaster duplicates, and avoided-flavor hits
_CANDIDATES = [
    RecommendationCandidate(
        name="Geometry",
        roaster="Onyx Coffee Lab",
        product_url="https://onyxcoffeelab.com/products/geometry",
        origin_country="Ethiopia",
        process="Washed",
        roast_level="Light",
        tasting_notes=["jasmine", "stone fruit", "citrus"],
        price_usd=22.0,
        in_stock=True,
        match_score=0.9,
        match_rationale="origin match (Ethiopia); process match (Washed); roast match (Light); flavor overlap: ['stone fruit', 'citrus', 'jasmine']",
    ),
    RecommendationCandidate(
        name="Monarch",
        roaster="Onyx Coffee Lab",
        product_url="https://onyxcoffeelab.com/products/monarch",
        origin_country="Colombia",
        process="Washed",
        roast_level="Medium-Light",
        tasting_notes=["caramel", "orange", "hazelnut"],
        price_usd=18.0,
        in_stock=True,
        match_score=0.7,
        match_rationale="origin match (Colombia); process match (Washed); roast match (Medium-Light)",
    ),
    RecommendationCandidate(
        name="Hologram",
        roaster="Onyx Coffee Lab",
        product_url="https://onyxcoffeelab.com/products/hologram",
        origin_country="Colombia",
        process="Natural",
        roast_level="Light",
        tasting_notes=["blueberry", "dark cherry", "brown sugar"],
        price_usd=20.0,
        in_stock=True,
        match_score=0.5,
        match_rationale="origin match (Colombia); roast match (Light)",
    ),
    RecommendationCandidate(
        name="Kenya Kirinyaga",
        roaster="Counter Culture Coffee",
        product_url="https://counterculturecoffee.com/products/kenya-kirinyaga",
        origin_country="Kenya",
        process="Washed",
        roast_level="Light",
        tasting_notes=["black currant", "citrus", "floral"],
        price_usd=19.0,
        in_stock=True,
        match_score=0.6,
        match_rationale="process match (Washed); roast match (Light); flavor overlap: ['citrus', 'floral']",
    ),
    RecommendationCandidate(
        name="Toscano Dark",
        roaster="Blue Bottle Coffee",
        product_url="https://bluebottlecoffee.com/products/toscano-dark",
        origin_country="Brazil",
        process="Natural",
        roast_level="Dark",
        tasting_notes=["smoke", "dark chocolate", "earthy"],
        price_usd=16.0,
        in_stock=True,
        match_score=0.1,
        match_rationale="avoided flavor present: ['smoke', 'earthy']",
    ),
    RecommendationCandidate(
        name="Ethiopia Yirgacheffe",
        roaster="Intelligentsia",
        product_url="https://www.intelligentsia.com/products/ethiopia-yirgacheffe",
        origin_country="Ethiopia",
        process="Washed",
        roast_level="Light",
        tasting_notes=["peach", "stone fruit", "lemon"],
        price_usd=21.0,
        in_stock=True,
        match_score=0.85,
        match_rationale="origin match (Ethiopia); process match (Washed); roast match (Light); flavor overlap: ['stone fruit', 'peach']",
    ),
]


@pytest.mark.integration
@pytest.mark.skipif(_no_gemini, reason="GOOGLE_API_KEY not set")
async def test_critic_run_returns_valid_output():
    """
    Real LLM call: critic prunes 6 candidates to at most n_final=4.
    Asserts output structure without relying on specific selections.
    """
    final, notes = await critic.run(_CANDIDATES, _PROFILE, n_final=4)

    assert isinstance(final, list)
    assert len(final) <= 4
    assert isinstance(notes, str) and len(notes) > 10

    for c in final:
        assert isinstance(c, RecommendationCandidate)
        assert c.name
        assert c.roaster
        assert str(c.product_url).startswith("http")
        assert 0.0 <= c.match_score <= 1.0


@pytest.mark.integration
@pytest.mark.skipif(_no_gemini, reason="GOOGLE_API_KEY not set")
async def test_critic_excludes_low_quality_candidates():
    """
    The obviously bad candidate (smoke/earthy, score=0.1) should not appear in results.
    """
    final, notes = await critic.run(_CANDIDATES, _PROFILE, n_final=4)

    final_names = [c.name for c in final]
    assert "Toscano Dark" not in final_names


@pytest.mark.integration
@pytest.mark.skipif(_no_gemini, reason="GOOGLE_API_KEY not set")
async def test_critic_enforces_roaster_diversity():
    """
    Three Onyx candidates are in the input; at most 2 should appear in the final list.
    """
    final, _ = await critic.run(_CANDIDATES, _PROFILE, n_final=4)

    onyx_count = sum(1 for c in final if c.roaster == "Onyx Coffee Lab")
    assert onyx_count <= 2


@pytest.mark.integration
@pytest.mark.skipif(_no_gemini, reason="GOOGLE_API_KEY not set")
async def test_critic_empty_input_returns_immediately():
    """Empty candidate list returns ([], note) without an LLM call."""
    final, notes = await critic.run([], _PROFILE)

    assert final == []
    assert notes == critic._NO_CANDIDATES_NOTES
