from app.models.taste_profile import TasteProfile


def score_candidate(candidate: dict, profile: TasteProfile) -> tuple[float, str]:
    """
    Deterministic scoring: returns (match_score 0.0–1.0, rationale string).
    candidate keys: origin_country, process, roast_level, tasting_notes (list[str]).
    """
    score = 0.0
    reasons: list[str] = []

    if candidate.get("origin_country") in profile.preferred_origins:
        score += 0.3
        reasons.append(f"origin match ({candidate['origin_country']})")

    if candidate.get("process") in profile.preferred_processes:
        score += 0.2
        reasons.append(f"process match ({candidate['process']})")

    if candidate.get("roast_level") in profile.preferred_roast_levels:
        score += 0.2
        reasons.append(f"roast match ({candidate['roast_level']})")

    candidate_notes = set(candidate.get("tasting_notes", []))
    affinity_set = set(profile.flavor_affinities)
    overlap = candidate_notes & affinity_set
    if overlap:
        flavor_score = min(0.3, len(overlap) * 0.1)
        score += flavor_score
        reasons.append(f"flavor overlap: {sorted(overlap)}")

    avoided_overlap = candidate_notes & set(profile.avoided_flavors)
    if avoided_overlap:
        score -= 0.15
        reasons.append(f"avoided flavor present: {sorted(avoided_overlap)}")

    rationale = "; ".join(reasons) if reasons else "no strong attribute match"
    return round(score, 3), rationale
