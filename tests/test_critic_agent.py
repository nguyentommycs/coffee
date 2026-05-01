"""
Unit tests for app/agents/critic.py.

All external I/O is mocked: llm_complete is patched with AsyncMock.
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.critic import CriticError, _NO_CANDIDATES_NOTES, run
from app.models.recommendation import RecommendationCandidate
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


def _make_candidate(
    name: str,
    roaster: str = "Onyx Coffee Lab",
    match_score: float = 0.7,
    tasting_notes: list[str] | None = None,
) -> RecommendationCandidate:
    return RecommendationCandidate(
        name=name,
        roaster=roaster,
        product_url=f"https://example.com/products/{name.lower().replace(' ', '-')}",
        origin_country="Ethiopia",
        process="Washed",
        roast_level="Light",
        tasting_notes=tasting_notes or ["jasmine", "stone fruit"],
        match_score=match_score,
        match_rationale="origin match (Ethiopia); process match (Washed)",
    )


_CANDIDATES = [
    _make_candidate("Geometry", match_score=0.8),
    _make_candidate("Monarch", match_score=0.6),
    _make_candidate("Hologram", roaster="Blue Bottle Coffee", match_score=0.5),
]

_APPROVE_ALL = json.dumps({
    "approved_indices": [0, 1, 2],
    "critic_notes": "Strong set of floral, light roast options from quality roasters.",
})

_APPROVE_FIRST_TWO = json.dumps({
    "approved_indices": [0, 2],
    "critic_notes": "Two well-matched candidates selected for diversity.",
})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path(taste_profile):
    with patch("app.agents.critic.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _APPROVE_ALL
        final, notes = await run(_CANDIDATES, taste_profile, n_final=5)

    assert len(final) == 3
    assert final[0].name == "Geometry"
    assert final[1].name == "Monarch"
    assert final[2].name == "Hologram"
    assert notes != ""
    mock_llm.assert_called_once()


@pytest.mark.asyncio
async def test_empty_candidates_no_llm_call(taste_profile):
    with patch("app.agents.critic.llm_complete", new_callable=AsyncMock) as mock_llm:
        final, notes = await run([], taste_profile)

    assert final == []
    assert notes == _NO_CANDIDATES_NOTES
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_approved_indices_order_respected(taste_profile):
    """LLM returns indices in reverse order; final list should reflect that order."""
    response = json.dumps({
        "approved_indices": [2, 0, 1],
        "critic_notes": "Reranked for diversity.",
    })
    with patch("app.agents.critic.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = response
        final, _ = await run(_CANDIDATES, taste_profile, n_final=5)

    assert final[0].name == "Hologram"
    assert final[1].name == "Geometry"
    assert final[2].name == "Monarch"


@pytest.mark.asyncio
async def test_out_of_range_index_skipped(taste_profile):
    response = json.dumps({
        "approved_indices": [0, 99, 1],
        "critic_notes": "Two valid, one invalid index.",
    })
    with patch("app.agents.critic.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = response
        final, _ = await run(_CANDIDATES, taste_profile, n_final=5)

    assert len(final) == 2
    assert final[0].name == "Geometry"
    assert final[1].name == "Monarch"


@pytest.mark.asyncio
async def test_invalid_json_retry_succeeds(taste_profile):
    with patch("app.agents.critic.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = ["not valid json", _APPROVE_FIRST_TWO]
        final, notes = await run(_CANDIDATES, taste_profile, n_final=5)

    assert mock_llm.call_count == 2
    assert mock_llm.call_args_list[1].kwargs.get("span") == "critic_retry"
    assert len(final) == 2
    assert notes != ""


@pytest.mark.asyncio
async def test_invalid_json_retry_also_fails_raises_error(taste_profile):
    with patch("app.agents.critic.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = ["bad json #1", "bad json #2"]
        with pytest.raises(CriticError, match="invalid JSON after retry"):
            await run(_CANDIDATES, taste_profile)

    assert mock_llm.call_count == 2


@pytest.mark.asyncio
async def test_n_final_respected(taste_profile):
    """LLM returns more indices than n_final; output must be capped."""
    response = json.dumps({
        "approved_indices": [0, 1, 2],
        "critic_notes": "All three approved.",
    })
    with patch("app.agents.critic.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = response
        final, _ = await run(_CANDIDATES, taste_profile, n_final=2)

    assert len(final) == 2
    assert final[0].name == "Geometry"
    assert final[1].name == "Monarch"


@pytest.mark.asyncio
async def test_single_candidate(taste_profile):
    single = [_make_candidate("Geometry")]
    response = json.dumps({
        "approved_indices": [0],
        "critic_notes": "Only one candidate; it matches well.",
    })
    with patch("app.agents.critic.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = response
        final, notes = await run(single, taste_profile)

    assert len(final) == 1
    assert final[0].name == "Geometry"
    assert notes != ""


@pytest.mark.asyncio
async def test_empty_approved_indices_returns_empty(taste_profile):
    response = json.dumps({
        "approved_indices": [],
        "critic_notes": "None of the candidates met quality standards.",
    })
    with patch("app.agents.critic.llm_complete", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = response
        final, notes = await run(_CANDIDATES, taste_profile)

    assert final == []
    assert "quality" in notes
