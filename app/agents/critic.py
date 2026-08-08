"""
Critic Agent.

Reviews a list of RecommendationCandidates and prunes/reranks them via a
single structured LLM call. No tool use, no loop.
"""
import json
import logging

from app.llm import llm_complete
from app.models.recommendation import (
    CriticObjection,
    CriticReview,
    RecommendationCandidate,
)
from app.models.taste_profile import TasteProfile

logger = logging.getLogger(__name__)

_CRITIC_PROMPT_TEMPLATE = """\
You are a quality evaluator for a coffee recommendation system. The user's taste profile is:

"{narrative_summary}"
Avoided flavors: {avoided_flavors}

Below are {n_candidates} recommendation candidates (0-indexed), each with their \
match score, rationale, and tasting notes:

{candidates_json}

Your job:
1. Remove any candidates that clearly do not match the user's taste profile.
2. Flag candidates with match_score < 0.3 as low quality and exclude them unless \
there are no better options.
3. Ensure diversity — include no more than 2 candidates from the same roaster.
4. Return the final list of up to {n_final} candidates in your preferred rank order.
5. Write a brief critic_notes string (1–2 sentences) describing the recommendation set \
which will be displayed to the user.
6. For each candidate you exclude, provide a one-sentence objection explaining why it \
does not fit the profile (e.g. 'too dark-roasted for this profile').

Return a JSON object:
{{
  "approved_indices": [int, ...],
  "rejections": [{{"index": int, "reason": string}}, ...],
  "critic_notes": string
}}

Return only valid JSON. No preamble, no markdown fences.\
"""

_SCHEMA_REMINDER = (
    "\n\nIMPORTANT: Your previous response was not valid JSON. "
    "Return ONLY a valid JSON object matching the schema above. "
    "No preamble, no markdown fences."
)

_NO_CANDIDATES_NOTES = "No candidates to review."


class CriticError(Exception):
    pass


async def run(
    candidates: list[RecommendationCandidate],
    taste_profile: TasteProfile,
    n_final: int = 5,
    span_suffix: str = "",
) -> CriticReview:
    """
    Prune and rerank candidates, returning a CriticReview with the approved
    candidates and structured objections for the ones excluded.

    span_suffix is appended to the llm_complete span names so a second review
    pass is distinguishable in the trace (e.g. "_2" → span "critic_2").
    Raises CriticError if LLM returns invalid JSON after retry.
    """
    if not candidates:
        return CriticReview(approved=[], objections=[], critic_notes=_NO_CANDIDATES_NOTES)

    candidate_summaries = [
        {
            "index": i,
            "name": c.name,
            "roaster": c.roaster,
            "match_score": c.match_score,
            "match_rationale": c.match_rationale,
            "tasting_notes": c.tasting_notes,
        }
        for i, c in enumerate(candidates)
    ]

    prompt = _CRITIC_PROMPT_TEMPLATE.format(
        narrative_summary=taste_profile.narrative_summary,
        avoided_flavors=taste_profile.avoided_flavors,
        n_candidates=len(candidates),
        candidates_json=json.dumps(candidate_summaries, indent=2),
        n_final=n_final,
    )

    raw = await llm_complete(prompt, span=f"critic{span_suffix}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raw2 = await llm_complete(
            prompt + _SCHEMA_REMINDER, span=f"critic{span_suffix}_retry"
        )
        try:
            data = json.loads(raw2)
        except json.JSONDecodeError as exc:
            raise CriticError(
                f"LLM returned invalid JSON after retry: {raw2!r}"
            ) from exc

    approved_indices: list[int] = data.get("approved_indices") or []
    critic_notes: str = data.get("critic_notes") or ""

    final: list[RecommendationCandidate] = []
    for idx in approved_indices:
        if isinstance(idx, int) and 0 <= idx < len(candidates):
            final.append(candidates[idx])

    final = final[:n_final]

    approved_set = {
        idx for idx in approved_indices
        if isinstance(idx, int) and 0 <= idx < len(candidates)
    }
    objections: list[CriticObjection] = []
    for entry in data.get("rejections") or []:
        if not isinstance(entry, dict):
            continue
        idx = entry.get("index")
        if not isinstance(idx, int) or isinstance(idx, bool):
            continue
        if not (0 <= idx < len(candidates)) or idx in approved_set:
            continue
        c = candidates[idx]
        objections.append(
            CriticObjection(
                candidate_name=c.name,
                roaster=c.roaster,
                product_url=c.product_url,
                reason=entry.get("reason") or "",
            )
        )

    logger.info(
        "Critic approved %d/%d candidates (n_final=%d, %d objections)",
        len(final),
        len(candidates),
        n_final,
        len(objections),
    )
    return CriticReview(approved=final, objections=objections, critic_notes=critic_notes)
