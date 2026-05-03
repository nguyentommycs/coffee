"""
Critic Agent.

Reviews a list of RecommendationCandidates and prunes/reranks them via a
single structured LLM call. No tool use, no loop.
"""
import json
import logging

from app.llm import llm_complete
from app.models.recommendation import RecommendationCandidate
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

Return a JSON object:
{{
  "approved_indices": [int, ...],
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
) -> tuple[list[RecommendationCandidate], str]:
    """
    Prune and rerank candidates. Returns (final_candidates, critic_notes).
    Returns ([], _NO_CANDIDATES_NOTES) immediately for empty input.
    Raises CriticError if LLM returns invalid JSON after retry.
    """
    if not candidates:
        return [], _NO_CANDIDATES_NOTES

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

    raw = await llm_complete(prompt, span="critic")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raw2 = await llm_complete(prompt + _SCHEMA_REMINDER, span="critic_retry")
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

    logger.info(
        "Critic approved %d/%d candidates (n_final=%d)",
        len(final),
        len(candidates),
        n_final,
    )
    return final, critic_notes
