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
    get_recommendation_feedback,
    insert_recommendation_run,
    upsert_bean_profile,
    upsert_taste_profile,
)
from app.models.bean_profile import BeanProfile
from app.models.recommendation import RecommendationResponse
from app.observability.trace import TraceLogger

logger = logging.getLogger(__name__)

# Below this many critic-approved candidates, run one (and only one) revision round.
REVISION_THRESHOLD = 3


async def parse_and_persist(
    user_id: str,
    raw_inputs: list[str],
    user_score: int | None = None,
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
            profile = await input_parsing.run(raw, user_id, user_score=user_score)
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
    Performs exactly one revision round if the critic approves fewer than
    REVISION_THRESHOLD candidates, feeding the critic's objections back to the
    recommendation agent.
    """
    all_profiles = await get_bean_profiles(user_id)

    if len(all_profiles) < 3:
        raise ValueError(
            f"User {user_id!r} has {len(all_profiles)} bean(s) logged. "
            "Log at least 3 beans before requesting recommendations."
        )

    feedback = await get_recommendation_feedback(user_id)
    downvoted_urls = {fb.product_url for fb in feedback if fb.verdict == "down"}

    trace = TraceLogger(pipeline_id=uuid4(), user_id=user_id)

    with trace.activate():
        with trace.span("profiler", type="agent", n_beans=len(all_profiles)):
            taste_profile = await profiler.run(user_id, all_profiles, feedback=feedback)
        await upsert_taste_profile(taste_profile)

        with trace.span("recommendation", type="agent", broad_mode=False):
            candidates = await recommendation.run(
                taste_profile,
                n_recommendations=10,
                exclude_urls=downvoted_urls or None,
            )

        with trace.span("critic", type="agent", n_candidates=len(candidates)):
            review = await critic.run(candidates, taste_profile, n_final=n_final)
        final, notes = review.approved, review.critic_notes

        # Bounded self-correction: exactly one revision round, triggered when the
        # critic prunes below the threshold. The recommendation agent receives the
        # critic's objections and must avoid candidates with the same flaws.
        if len(final) < REVISION_THRESHOLD:
            logger.info(
                "Critic approved only %d candidates (%d objections); running one revision round",
                len(final), len(review.objections),
            )
            reviewed_urls = {str(c.product_url) for c in candidates}
            with trace.span(
                "recommendation_revision",
                type="agent",
                broad_mode=True,
                n_objections=len(review.objections),
            ):
                revised = await recommendation.run(
                    taste_profile,
                    n_recommendations=10,
                    broad_mode=True,
                    exclude_urls=reviewed_urls | downvoted_urls,
                    objections=review.objections,
                )
            combined = final + [
                c for c in revised if str(c.product_url) not in reviewed_urls
            ]
            with trace.span(
                "critic_review_2", type="agent", n_candidates=len(combined)
            ):
                review = await critic.run(
                    combined, taste_profile, n_final=n_final, span_suffix="_2"
                )
            final, notes = review.approved, review.critic_notes

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
