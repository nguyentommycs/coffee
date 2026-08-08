"""
Unit tests for the orchestrator's critic-driven revision control flow.

All agents and DB calls are patched; only the control flow is under test.
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.agents import orchestrator
from app.models.bean_profile import BeanProfile
from app.models.recommendation import (
    CriticObjection,
    CriticReview,
    RecommendationCandidate,
)
from app.models.taste_profile import TasteProfile

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _bean(name: str) -> BeanProfile:
    return BeanProfile(
        user_id="u1",
        name=name,
        roaster="Onyx Coffee Lab",
        input_raw=name,
        input_type="name",
    )


_BEANS = [_bean("Geometry"), _bean("Monarch"), _bean("Hologram")]

_TASTE_PROFILE = TasteProfile(
    user_id="u1",
    preferred_origins=["Ethiopia"],
    preferred_processes=["Washed"],
    preferred_roast_levels=["Light"],
    flavor_affinities=["floral"],
    avoided_flavors=["smoke"],
    narrative_summary="Prefers light, floral East African coffees.",
    total_beans_logged=3,
    profile_confidence=0.9,
)


def _candidate(slug: str, roaster: str = "Onyx Coffee Lab") -> RecommendationCandidate:
    return RecommendationCandidate(
        name=slug,
        roaster=roaster,
        product_url=f"https://example.com/products/{slug}",
        match_score=0.7,
        match_rationale="origin match (Ethiopia)",
    )


def _objection(slug: str) -> CriticObjection:
    return CriticObjection(
        candidate_name=slug,
        roaster="Onyx Coffee Lab",
        product_url=f"https://example.com/products/{slug}",
        reason="too dark-roasted for this profile",
    )


@pytest.fixture
def mocks():
    with (
        patch("app.agents.orchestrator.get_bean_profiles", new_callable=AsyncMock) as beans,
        patch("app.agents.orchestrator.upsert_taste_profile", new_callable=AsyncMock),
        patch("app.agents.orchestrator.insert_recommendation_run", new_callable=AsyncMock) as insert,
        patch("app.agents.orchestrator.profiler.run", new_callable=AsyncMock) as prof,
        patch("app.agents.orchestrator.recommendation.run", new_callable=AsyncMock) as rec,
        patch("app.agents.orchestrator.critic.run", new_callable=AsyncMock) as crit,
    ):
        beans.return_value = _BEANS
        prof.return_value = _TASTE_PROFILE
        yield {"insert": insert, "recommendation": rec, "critic": crit}


def _span_names(insert_mock) -> list[str]:
    trace = insert_mock.call_args.kwargs["trace"]
    return [span["name"] for span in trace["spans"]]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_revision_when_critic_approves_enough(mocks):
    approved = [_candidate("a"), _candidate("b"), _candidate("c")]
    mocks["recommendation"].return_value = approved
    mocks["critic"].return_value = CriticReview(
        approved=approved, objections=[], critic_notes="Good set."
    )

    response = await orchestrator.run_recommendations("u1")

    assert mocks["recommendation"].call_count == 1
    assert mocks["critic"].call_count == 1
    assert "recommendation_revision" not in _span_names(mocks["insert"])
    assert [c.name for c in response.recommendations] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_one_revision_round_when_pruned_below_threshold(mocks):
    round1 = [_candidate("a"), _candidate("b"), _candidate("c")]
    revised = [_candidate("x"), _candidate("y"), _candidate("z"), _candidate("w")]
    objections = [_objection("b"), _objection("c")]

    mocks["recommendation"].side_effect = [round1, revised]
    mocks["critic"].side_effect = [
        CriticReview(approved=[round1[0]], objections=objections, critic_notes="Pruned hard."),
        CriticReview(approved=revised, objections=[], critic_notes="Better set."),
    ]

    response = await orchestrator.run_recommendations("u1")

    assert mocks["recommendation"].call_count == 2
    second_rec_kwargs = mocks["recommendation"].call_args_list[1].kwargs
    assert second_rec_kwargs["broad_mode"] is True
    assert second_rec_kwargs["objections"] == objections
    assert second_rec_kwargs["exclude_urls"] == {str(c.product_url) for c in round1}

    assert mocks["critic"].call_count == 2
    assert mocks["critic"].call_args_list[1].kwargs["span_suffix"] == "_2"

    names = _span_names(mocks["insert"])
    assert "recommendation_revision" in names
    assert "critic_review_2" in names

    assert [c.name for c in response.recommendations] == ["x", "y", "z", "w"]


@pytest.mark.asyncio
async def test_revision_runs_at_most_once(mocks):
    mocks["recommendation"].side_effect = [[_candidate("a")], [_candidate("x")]]
    mocks["critic"].side_effect = [
        CriticReview(approved=[], objections=[_objection("a")], critic_notes="Nothing fits."),
        CriticReview(approved=[], objections=[], critic_notes="Still nothing fits."),
    ]

    response = await orchestrator.run_recommendations("u1")

    assert mocks["recommendation"].call_count == 2
    assert mocks["critic"].call_count == 2
    assert response.recommendations == []


@pytest.mark.asyncio
async def test_round1_approved_carried_into_second_review(mocks):
    round1 = [_candidate("a"), _candidate("b")]
    # revised includes a repeat of a round-1 URL, which must be de-duplicated
    revised = [_candidate("x"), _candidate("a")]

    mocks["recommendation"].side_effect = [round1, revised]
    mocks["critic"].side_effect = [
        CriticReview(approved=[round1[0]], objections=[_objection("b")], critic_notes="One kept."),
        CriticReview(approved=[round1[0]], objections=[], critic_notes="Final."),
    ]

    await orchestrator.run_recommendations("u1")

    combined = mocks["critic"].call_args_list[1].args[0]
    assert [c.name for c in combined] == ["a", "x"]
