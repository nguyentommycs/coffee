"""
Profiler Agent.

Analyzes a user's BeanProfile history and produces a TasteProfile
via a single structured LLM call. No tool use, no loop.
"""
import json
import logging

from app.llm import llm_complete
from app.models.bean_profile import BeanProfile
from app.models.taste_profile import TasteProfile

logger = logging.getLogger(__name__)

_PROFILER_PROMPT_TEMPLATE = """\
You are a coffee taste profiler. Analyze the following list of coffee beans a user has enjoyed \
and produce a structured taste profile.

Bean history (JSON):
{profiles_json}

Produce a JSON object with this schema:
{{
  "preferred_origins": string[],
  "preferred_processes": string[],
  "preferred_roast_levels": string[],
  "flavor_affinities": string[],
  "avoided_flavors": string[],
  "narrative_summary": string
}}

Rules:
- Only include origins/processes/roast levels that appear in at least one bean.
- Weight all preference rankings by user_score — beans scored 8–10 should have stronger \
influence on preferred_origins, preferred_processes, flavor_affinities, etc. than beans \
scored 1–4. Beans with no score (null) are treated as neutral (score = 5).
- avoided_flavors should be inferred from flavor notes on beans the user scored 1–4, \
or from explicit language in user_notes (e.g., "too bitter", "too acidic").
- flavor_affinities should be high-level themes (e.g., "stone fruit", "citrus", "chocolate") \
not exhaustive note lists.
- narrative_summary should read naturally, like a barista describing a customer's preferences. \
If score variance is high (some 9s and some 2s), acknowledge that in the summary.
- Return only valid JSON. No preamble, no markdown fences.\
"""

_SCHEMA_REMINDER = (
    "\n\nIMPORTANT: Your previous response was not valid JSON. "
    "Return ONLY a valid JSON object matching the schema above. "
    "No preamble, no markdown fences."
)

_EMPTY_PROFILE_SUMMARY = "No beans logged yet."


class ProfilerError(Exception):
    pass


async def run(user_id: str, bean_profiles: list[BeanProfile]) -> TasteProfile:
    """
    Analyze bean history and return a TasteProfile.
    Returns a zeroed profile for empty input. Raises ProfilerError on LLM JSON failure.
    """
    if not bean_profiles:
        return TasteProfile(
            user_id=user_id,
            preferred_origins=[],
            preferred_processes=[],
            preferred_roast_levels=[],
            flavor_affinities=[],
            avoided_flavors=[],
            narrative_summary=_EMPTY_PROFILE_SUMMARY,
            total_beans_logged=0,
            profile_confidence=0.0,
        )

    profiles_json = json.dumps(
        [p.model_dump(mode="json") for p in bean_profiles],
        indent=2,
    )
    prompt = _PROFILER_PROMPT_TEMPLATE.format(profiles_json=profiles_json)

    raw = await llm_complete(prompt, span="profiler")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raw2 = await llm_complete(prompt + _SCHEMA_REMINDER, span="profiler_retry")
        try:
            data = json.loads(raw2)
        except json.JSONDecodeError as exc:
            raise ProfilerError(
                f"LLM returned invalid JSON after retry: {raw2!r}"
            ) from exc

    total = len(bean_profiles)
    avg_confidence = sum(p.confidence for p in bean_profiles) / total

    return TasteProfile(
        user_id=user_id,
        preferred_origins=data.get("preferred_origins") or [],
        preferred_processes=data.get("preferred_processes") or [],
        preferred_roast_levels=data.get("preferred_roast_levels") or [],
        flavor_affinities=data.get("flavor_affinities") or [],
        avoided_flavors=data.get("avoided_flavors") or [],
        narrative_summary=data.get("narrative_summary") or "",
        total_beans_logged=total,
        profile_confidence=round(avg_confidence, 4),
    )
