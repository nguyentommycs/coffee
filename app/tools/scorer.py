from app.models.taste_profile import TasteProfile
from app.tools.flavor_hierarchy import flavor_match_score


def score_candidate(candidate: dict, profile: TasteProfile) -> tuple[float, str]:
    """
    Deterministic scoring: returns (match_score 0.0–1.0, rationale string).
    candidate keys: origin_country, process, roast_level, tasting_notes (list[str]).
    """
    score = 0.0
    reasons: list[str] = []

    if candidate.get("origin_country") in profile.preferred_origins:
        score += 0.4
        reasons.append(f"origin match ({candidate['origin_country']})")

    if candidate.get("process") in profile.preferred_processes:
        score += 0.2
        reasons.append(f"process match ({candidate['process']})")

    if candidate.get("roast_level") in profile.preferred_roast_levels:
        score += 0.3
        reasons.append(f"roast match ({candidate['roast_level']})")

    candidate_notes = candidate.get("tasting_notes", [])
    flavor_total = 0.0
    matched_pairs: list[str] = []

    for affinity in profile.flavor_affinities:
        best = 0.0
        best_note = None
        for note in candidate_notes:
            s = flavor_match_score(affinity, note)
            if s > best:
                best = s
                best_note = note
        if best > 0.0:
            flavor_total += best
            matched_pairs.append(f"{affinity}")

    if flavor_total > 0.0:
        flavor_score = min(0.3, flavor_total)
        score += flavor_score
        reasons.append(f"flavor overlap ({', '.join(matched_pairs)})")

    avoided_overlap = set(candidate_notes) & set(profile.avoided_flavors)
    if avoided_overlap:
        score -= 0.3
        reasons.append(f"avoided flavor present: {sorted(avoided_overlap)}")
    if score >0.95:
        score = 0.95
    elif score < 0.0:
        score = 0.0
    rationale = "; ".join(reasons) if reasons else "no strong attribute match"
    return round(score, 3), rationale
