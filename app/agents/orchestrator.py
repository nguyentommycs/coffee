"""
Orchestrator.

Pure Python control flow — no LLM calls. Sequences the four agents,
handles retries, emits trace logs, and persists each recommendation run.
"""
import logging
from uuid import uuid4

from app.agents import critic, input_parsing, profiler, recommendation
from app.agents.input_parsing import AgentLoopError
from app.db.queries import (
    get_bean_profiles,
    insert_recommendation_run,
    upsert_bean_profile,
    upsert_taste_profile,
)
from app.models.bean_profile import BeanProfile
from app.models.recommendation import RecommendationResponse
from app.observability.trace import TraceLogger

logger = logging.getLogger(__name__)


async def parse_and_persist(
    user_id: str,
    raw_inputs: list[str],
) -> tuple[list[BeanProfile], list[str]]:
    """
    Parse each raw input into a BeanProfile and persist it.
    Returns (parsed_profiles, skipped_inputs).
    AgentLoopError on any single input adds it to skipped rather than aborting.
    """
    parsed: list[BeanProfile] = []
    skipped: list[str] = []

    for raw in raw_inputs:
        try:
            profile = await input_parsing.run(raw, user_id)
            await upsert_bean_profile(profile)
            parsed.append(profile)
        except AgentLoopError as exc:
            logger.warning("AgentLoopError for input %r: %s", raw, exc)
            skipped.append(raw)

    return parsed, skipped


async def run_recommendations(
    user_id: str,
    n_final: int = 5,
) -> RecommendationResponse:
    """
    Run the profiler → recommendation → critic pipeline on existing bean history.
    Raises ValueError if the user has fewer than 2 beans logged.
    Performs exactly one broad-mode retry if the critic approves fewer than 3 candidates.
    """
    all_profiles = await get_bean_profiles(user_id)

    if len(all_profiles) < 3:
        raise ValueError(
            f"User {user_id!r} has {len(all_profiles)} bean(s) logged. "
            "Log at least 3 beans before requesting recommendations."
        )

    trace = TraceLogger(pipeline_id=uuid4(), user_id=user_id)

    with trace.span("profiler"):
        taste_profile = await profiler.run(user_id, all_profiles)
    await upsert_taste_profile(taste_profile)

    with trace.span("recommendation"):
        candidates = await recommendation.run(taste_profile, n_recommendations=10)

    with trace.span("critic"):
        final, notes = await critic.run(candidates, taste_profile, n_final=n_final)

    if len(final) < 3:
        logger.info(
            "Critic approved only %d candidates; retrying in broad mode", len(final)
        )
        with trace.span("recommendation_retry"):
            candidates = await recommendation.run(
                taste_profile, n_recommendations=10, broad_mode=True
            )
        with trace.span("critic_retry"):
            final, notes = await critic.run(candidates, taste_profile, n_final=n_final)

    await insert_recommendation_run(
        user_id=user_id,
        taste_profile=taste_profile,
        recommendations=final,
        critic_notes=notes,
        trace=trace.dump(),
    )

    return RecommendationResponse(
        user_id=user_id,
        taste_profile=taste_profile,
        recommendations=final,
        critic_notes=notes,
    )
