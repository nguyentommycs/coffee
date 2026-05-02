"""
Integration tests for the Input Parsing → Profiler pipeline.

These tests make real API calls to Gemini and Brave Search.
Skipped by default — run with:
    pytest tests/integration/ --integration -v

Requires GOOGLE_API_KEY and BRAVE_API_KEY in .env or environment.
"""
import pytest

from app.agents import input_parsing, profiler
from app.config import settings
from app.models.bean_profile import BeanProfile
from app.models.taste_profile import TasteProfile

_no_gemini = not settings.google_api_key
_no_brave = not settings.brave_api_key
_no_apis = _no_gemini or _no_brave



@pytest.mark.integration
@pytest.mark.skipif(_no_apis, reason="GOOGLE_API_KEY or BRAVE_API_KEY not set")
async def test_input_parsing_url_returns_bean_profile():
    """Input parsing resolves a bean name via search and returns a valid BeanProfile."""
    profile = await input_parsing.run(
        raw_input="https://www.vervecoffee.com/products/gichathaini",
        user_id="test-user",
        user_score=8,
    )

    assert isinstance(profile, BeanProfile)
    assert profile.user_id == "test-user"
    assert profile.user_score == 8
    assert profile.input_type == "name"
    assert profile.name  # non-empty
    assert profile.roaster  # non-empty
    assert isinstance(profile.tasting_notes, list)
    assert 0.0 <= profile.confidence <= 1.0



@pytest.mark.integration
@pytest.mark.skipif(_no_apis, reason="GOOGLE_API_KEY or BRAVE_API_KEY not set")
async def test_input_parsing_name_returns_bean_profile():
    """Input parsing resolves a bean name via search and returns a valid BeanProfile."""
    profile = await input_parsing.run(
        raw_input="Onyx Coffee Lab Geometry",
        user_id="test-user",
        user_score=8,
    )

    assert isinstance(profile, BeanProfile)
    assert profile.user_id == "test-user"
    assert profile.user_score == 8
    assert profile.input_type == "name"
    assert profile.name  # non-empty
    assert profile.roaster  # non-empty
    assert isinstance(profile.tasting_notes, list)
    assert 0.0 <= profile.confidence <= 1.0


@pytest.mark.integration
@pytest.mark.skipif(_no_apis, reason="GOOGLE_API_KEY or BRAVE_API_KEY not set")
async def test_input_parsing_freeform_returns_bean_profile():
    """Input parsing handles a freeform description and returns a valid BeanProfile."""
    profile = await input_parsing.run(
        raw_input="Ethiopian Yirgacheffe washed light roast with jasmine and citrus notes",
        user_id="test-user",
        user_score=9,
    )

    assert isinstance(profile, BeanProfile)
    assert profile.input_type == "freeform"
    assert profile.user_score == 9
    assert isinstance(profile.tasting_notes, list)
    assert 0.0 <= profile.confidence <= 1.0


@pytest.mark.integration
@pytest.mark.skipif(_no_gemini, reason="GOOGLE_API_KEY not set")
async def test_profiler_with_hand_crafted_beans():
    """Profiler produces a coherent TasteProfile from hand-crafted BeanProfiles."""
    beans = [
        BeanProfile(
            user_id="test-user",
            name="Yirgacheffe Natural",
            roaster="Test Roaster A",
            origin_country="Ethiopia",
            process="Natural",
            roast_level="Light",
            tasting_notes=["blueberry", "jasmine", "lemon"],
            user_score=9,
            confidence=0.9,
            input_raw="Yirgacheffe Natural",
            input_type="name",
        ),
        BeanProfile(
            user_id="test-user",
            name="Colombia Huila Washed",
            roaster="Test Roaster B",
            origin_country="Colombia",
            process="Washed",
            roast_level="Medium-Light",
            tasting_notes=["caramel", "orange", "hazelnut"],
            user_score=7,
            confidence=0.85,
            input_raw="Colombia Huila Washed",
            input_type="name",
        ),
        BeanProfile(
            user_id="test-user",
            name="Sumatra Mandheling Dark",
            roaster="Test Roaster C",
            origin_country="Indonesia",
            process="Natural",
            roast_level="Dark",
            tasting_notes=["tobacco", "earthy", "cedar"],
            user_score=2,
            confidence=0.8,
            input_raw="Sumatra Mandheling Dark",
            input_type="name",
        ),
    ]

    taste = await profiler.run(user_id="test-user", bean_profiles=beans)

    assert isinstance(taste, TasteProfile)
    assert taste.user_id == "test-user"
    assert taste.total_beans_logged == 3
    assert taste.profile_confidence == round((0.9 + 0.85 + 0.8) / 3, 4)
    assert isinstance(taste.narrative_summary, str) and len(taste.narrative_summary) > 20
    assert isinstance(taste.preferred_origins, list) and taste.preferred_origins
    assert isinstance(taste.flavor_affinities, list)
    assert isinstance(taste.avoided_flavors, list)
    assert isinstance(taste.preferred_processes, list)
    assert isinstance(taste.preferred_roast_levels, list)
    assert 0.0 <= taste.profile_confidence <= 1.0


@pytest.mark.integration
@pytest.mark.skipif(_no_apis, reason="GOOGLE_API_KEY or BRAVE_API_KEY not set")
async def test_full_pipeline_input_parsing_to_profiler():
    """End-to-end: parse two coffee inputs via live APIs, then generate a TasteProfile."""
    user_id = "integration-test-user"

    bean1 = await input_parsing.run(
        raw_input="Onyx Coffee Lab Geometry",
        user_id=user_id,
        user_score=9,
    )
    bean2 = await input_parsing.run(
        raw_input="Ethiopian natural process light roast berry and chocolate notes",
        user_id=user_id,
        user_score=7,
    )

    taste = await profiler.run(user_id=user_id, bean_profiles=[bean1, bean2])

    assert isinstance(taste, TasteProfile)
    assert taste.user_id == user_id
    assert taste.total_beans_logged == 2
    assert taste.profile_confidence == round((bean1.confidence + bean2.confidence) / 2, 4)
    assert isinstance(taste.narrative_summary, str) and taste.narrative_summary
    assert isinstance(taste.flavor_affinities, list)
    assert isinstance(taste.preferred_origins, list)
    assert isinstance(taste.preferred_processes, list)
    assert isinstance(taste.preferred_roast_levels, list)
    assert isinstance(taste.avoided_flavors, list)
    assert 0.0 <= taste.profile_confidence <= 1.0
