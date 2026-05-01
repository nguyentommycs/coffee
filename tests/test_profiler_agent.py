"""
Unit tests for app/agents/profiler.py.

All external I/O is mocked: llm_complete is patched with AsyncMock.
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.profiler import ProfilerError, _EMPTY_PROFILE_SUMMARY, run
from app.models.bean_profile import BeanProfile

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_HIGH_SCORE_BEAN = BeanProfile(
    user_id="user1",
    name="Geometry",
    roaster="Onyx Coffee Lab",
    origin_country="Ethiopia",
    origin_region="Yirgacheffe",
    process="Washed",
    roast_level="Light",
    tasting_notes=["jasmine", "peach", "meyer lemon"],
    user_score=9,
    confidence=0.95,
    input_raw="Onyx Geometry",
    input_type="name",
)

_MID_SCORE_BEAN = BeanProfile(
    user_id="user1",
    name="Hologram",
    roaster="Onyx Coffee Lab",
    origin_country="Colombia",
    origin_region="Huila",
    process="Natural",
    roast_level="Light",
    tasting_notes=["blueberry", "dark cherry", "brown sugar"],
    user_score=8,
    confidence=0.9,
    input_raw="Onyx Hologram",
    input_type="name",
)

_LOW_SCORE_BEAN = BeanProfile(
    user_id="user1",
    name="Toscano Dark",
    roaster="Blue Bottle",
    origin_country="Brazil",
    process="Natural",
    roast_level="Dark",
    tasting_notes=["smoke", "dark chocolate", "earthy"],
    user_score=3,
    confidence=0.8,
    input_raw="Blue Bottle Toscano Dark",
    input_type="name",
)

_NULL_SCORE_BEAN = BeanProfile(
    user_id="user1",
    name="Mystery Blend",
    roaster="Some Roaster",
    origin_country="Guatemala",
    process="Honey",
    roast_level="Medium",
    tasting_notes=["caramel", "hazelnut"],
    user_score=None,
    confidence=0.7,
    input_raw="Mystery Blend",
    input_type="name",
)

_FULL_LLM_RESPONSE = json.dumps({
    "preferred_origins": ["Ethiopia", "Colombia"],
    "preferred_processes": ["Washed", "Natural"],
    "preferred_roast_levels": ["Light"],
    "flavor_affinities": ["stone fruit", "floral", "citrus"],
    "avoided_flavors": ["smoke", "earthy"],
    "narrative_summary": (
        "This user gravitates toward light, fruit-forward coffees from East Africa and South "
        "America. They clearly love floral and stone fruit notes but tend to avoid heavy, "
        "smoky roasts."
    ),
})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_three_beans():
    with patch("app.agents.profiler.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _FULL_LLM_RESPONSE
        profile = await run("user1", [_HIGH_SCORE_BEAN, _MID_SCORE_BEAN, _LOW_SCORE_BEAN])

    assert profile.user_id == "user1"
    assert "Ethiopia" in profile.preferred_origins
    assert "Colombia" in profile.preferred_origins
    assert "smoke" in profile.avoided_flavors or "earthy" in profile.avoided_flavors
    assert profile.total_beans_logged == 3
    assert profile.narrative_summary != ""
    mock_llm.assert_called_once()


@pytest.mark.asyncio
async def test_empty_bean_list_returns_zeroed_profile():
    with patch("app.agents.profiler.llm_complete", new_callable=AsyncMock) as mock_llm:
        profile = await run("user1", [])

    assert profile.user_id == "user1"
    assert profile.preferred_origins == []
    assert profile.preferred_processes == []
    assert profile.preferred_roast_levels == []
    assert profile.flavor_affinities == []
    assert profile.avoided_flavors == []
    assert profile.total_beans_logged == 0
    assert profile.profile_confidence == 0.0
    assert profile.narrative_summary == _EMPTY_PROFILE_SUMMARY
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_single_bean():
    single_bean_response = json.dumps({
        "preferred_origins": ["Ethiopia"],
        "preferred_processes": ["Washed"],
        "preferred_roast_levels": ["Light"],
        "flavor_affinities": ["floral", "stone fruit"],
        "avoided_flavors": [],
        "narrative_summary": "This user enjoys light, floral Ethiopian washed coffees.",
    })
    with patch("app.agents.profiler.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = single_bean_response
        profile = await run("user1", [_HIGH_SCORE_BEAN])

    assert profile.total_beans_logged == 1
    assert profile.profile_confidence == round(_HIGH_SCORE_BEAN.confidence, 4)
    assert profile.preferred_origins == ["Ethiopia"]


@pytest.mark.asyncio
async def test_invalid_json_retry_succeeds():
    with patch("app.agents.profiler.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = ["not valid json at all", _FULL_LLM_RESPONSE]
        profile = await run("user1", [_HIGH_SCORE_BEAN, _MID_SCORE_BEAN])

    assert mock_llm.call_count == 2
    assert mock_llm.call_args_list[1].kwargs.get("span") == "profiler_retry"
    assert profile.total_beans_logged == 2
    assert "Ethiopia" in profile.preferred_origins


@pytest.mark.asyncio
async def test_invalid_json_retry_also_fails_raises_error():
    with patch("app.agents.profiler.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = ["bad json #1", "bad json #2"]
        with pytest.raises(ProfilerError, match="invalid JSON after retry"):
            await run("user1", [_HIGH_SCORE_BEAN])

    assert mock_llm.call_count == 2


@pytest.mark.asyncio
async def test_null_user_score_bean_included():
    null_score_response = json.dumps({
        "preferred_origins": ["Guatemala"],
        "preferred_processes": ["Honey"],
        "preferred_roast_levels": ["Medium"],
        "flavor_affinities": ["caramel", "nutty"],
        "avoided_flavors": [],
        "narrative_summary": "This user enjoys balanced, medium-roast coffees.",
    })
    with patch("app.agents.profiler.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = null_score_response
        profile = await run("user1", [_NULL_SCORE_BEAN])

    assert profile.total_beans_logged == 1
    assert "Guatemala" in profile.preferred_origins


@pytest.mark.asyncio
async def test_profile_confidence_is_average_of_bean_confidences():
    with patch("app.agents.profiler.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _FULL_LLM_RESPONSE
        profile = await run("user1", [_HIGH_SCORE_BEAN, _MID_SCORE_BEAN, _LOW_SCORE_BEAN])

    expected = round((0.95 + 0.9 + 0.8) / 3, 4)
    assert profile.profile_confidence == expected


@pytest.mark.asyncio
async def test_missing_llm_fields_default_to_empty_lists():
    sparse_response = json.dumps({
        "preferred_origins": ["Ethiopia"],
        "preferred_processes": [],
        "preferred_roast_levels": [],
        "flavor_affinities": [],
        "avoided_flavors": [],
        "narrative_summary": "Minimal profile.",
    })
    with patch("app.agents.profiler.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = sparse_response
        profile = await run("user1", [_HIGH_SCORE_BEAN])

    assert profile.preferred_processes == []
    assert profile.avoided_flavors == []
    assert profile.narrative_summary == "Minimal profile."
