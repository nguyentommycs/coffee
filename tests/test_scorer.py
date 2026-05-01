import pytest
from app.tools.scorer import score_candidate
from app.models.taste_profile import TasteProfile


@pytest.fixture
def profile():
    return TasteProfile(
        user_id="u1",
        preferred_origins=["Ethiopia", "Colombia"],
        preferred_processes=["Washed"],
        preferred_roast_levels=["Light"],
        flavor_affinities=["stone fruit", "citrus", "floral"],
        avoided_flavors=["smoke", "earthy"],
        narrative_summary="Prefers light, floral coffees.",
        total_beans_logged=3,
        profile_confidence=0.88,
    )


def test_perfect_match(profile):
    candidate = {
        "origin_country": "Ethiopia",
        "process": "Washed",
        "roast_level": "Light",
        "tasting_notes": ["stone fruit", "citrus"],
    }
    score, rationale = score_candidate(candidate, profile)
    assert score == pytest.approx(0.9)
    assert "origin match" in rationale
    assert "process match" in rationale
    assert "roast match" in rationale
    assert "flavor overlap" in rationale


def test_no_match(profile):
    candidate = {
        "origin_country": "Brazil",
        "process": "Natural",
        "roast_level": "Dark",
        "tasting_notes": ["dark chocolate"],
    }
    score, rationale = score_candidate(candidate, profile)
    assert score == 0.0
    assert rationale == "no strong attribute match"


def test_avoided_flavor_penalty(profile):
    candidate = {
        "origin_country": "Ethiopia",
        "process": "Washed",
        "roast_level": "Light",
        "tasting_notes": ["smoke"],
    }
    score, rationale = score_candidate(candidate, profile)
    # origin(0.3) + process(0.2) + roast(0.2) - penalty(0.15) = 0.55
    assert score == pytest.approx(0.55)
    assert "avoided flavor present" in rationale


def test_flavor_overlap_capped_at_0_3(profile):
    candidate = {
        "origin_country": "Ethiopia",
        "process": "Washed",
        "roast_level": "Light",
        "tasting_notes": ["stone fruit", "citrus", "floral", "jasmine", "peach"],
    }
    score, rationale = score_candidate(candidate, profile)
    # max flavor bonus is 0.3
    assert score == pytest.approx(1.0)


def test_partial_match_origin_only(profile):
    candidate = {
        "origin_country": "Colombia",
        "process": "Honey",
        "roast_level": "Medium",
        "tasting_notes": [],
    }
    score, rationale = score_candidate(candidate, profile)
    assert score == pytest.approx(0.3)
    assert "origin match" in rationale


def test_missing_fields_treated_as_no_match(profile):
    score, rationale = score_candidate({}, profile)
    assert score == 0.0


def test_score_rounded_to_3_decimals(profile):
    candidate = {
        "origin_country": "Ethiopia",
        "tasting_notes": ["stone fruit"],
    }
    score, _ = score_candidate(candidate, profile)
    assert score == round(score, 3)
