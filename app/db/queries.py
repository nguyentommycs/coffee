import json

from app.db.connection import get_pool
from app.models.bean_profile import BeanProfile
from app.models.recommendation import RecommendationCandidate
from app.models.taste_profile import TasteProfile


async def upsert_bean_profile(profile: BeanProfile) -> None:
    pool = get_pool()
    await pool.execute(
        """
        INSERT INTO bean_profiles (
            id, user_id, name, roaster, source_url,
            origin_country, origin_region, farm_or_cooperative,
            process, variety, roast_level, tasting_notes,
            user_score, user_notes, confidence, missing_fields,
            input_raw, input_type, created_at
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8,
            $9, $10, $11, $12,
            $13, $14, $15, $16,
            $17, $18, $19
        )
        ON CONFLICT (user_id, roaster, name)
        DO UPDATE SET
            tasting_notes = EXCLUDED.tasting_notes,
            user_score = EXCLUDED.user_score,
            user_notes = EXCLUDED.user_notes,
            confidence = EXCLUDED.confidence,
            source_url = COALESCE(EXCLUDED.source_url, bean_profiles.source_url)
        """,
        profile.id,
        profile.user_id,
        profile.name,
        profile.roaster,
        str(profile.source_url) if profile.source_url else None,
        profile.origin_country,
        profile.origin_region,
        profile.farm_or_cooperative,
        profile.process,
        profile.variety,
        profile.roast_level,
        profile.tasting_notes,
        profile.user_score,
        profile.user_notes,
        profile.confidence,
        profile.missing_fields,
        profile.input_raw,
        profile.input_type,
        profile.created_at,
    )


async def get_bean_profiles(user_id: str) -> list[BeanProfile]:
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT * FROM bean_profiles
        WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        user_id,
    )
    return [BeanProfile(**dict(row)) for row in rows]


async def upsert_taste_profile(profile: TasteProfile) -> None:
    pool = get_pool()
    await pool.execute(
        """
        INSERT INTO taste_profiles (
            user_id, preferred_origins, preferred_processes,
            preferred_roast_levels, flavor_affinities, avoided_flavors,
            narrative_summary, total_beans_logged, profile_confidence,
            updated_at
        ) VALUES (
            $1, $2, $3,
            $4, $5, $6,
            $7, $8, $9,
            $10
        )
        ON CONFLICT (user_id)
        DO UPDATE SET
            preferred_origins = EXCLUDED.preferred_origins,
            preferred_processes = EXCLUDED.preferred_processes,
            preferred_roast_levels = EXCLUDED.preferred_roast_levels,
            flavor_affinities = EXCLUDED.flavor_affinities,
            avoided_flavors = EXCLUDED.avoided_flavors,
            narrative_summary = EXCLUDED.narrative_summary,
            total_beans_logged = EXCLUDED.total_beans_logged,
            profile_confidence = EXCLUDED.profile_confidence,
            updated_at = EXCLUDED.updated_at
        """,
        profile.user_id,
        profile.preferred_origins,
        profile.preferred_processes,
        profile.preferred_roast_levels,
        profile.flavor_affinities,
        profile.avoided_flavors,
        profile.narrative_summary,
        profile.total_beans_logged,
        profile.profile_confidence,
        profile.updated_at,
    )


async def insert_recommendation_run(
    user_id: str,
    taste_profile: TasteProfile,
    recommendations: list[RecommendationCandidate],
    critic_notes: str,
    trace: dict,
) -> None:
    pool = get_pool()
    await pool.execute(
        """
        INSERT INTO recommendation_runs
            (user_id, taste_profile_snapshot, recommendations, critic_notes, pipeline_trace)
        VALUES ($1, $2::jsonb, $3::jsonb, $4, $5::jsonb)
        """,
        user_id,
        json.dumps(taste_profile.model_dump(mode="json")),
        json.dumps([r.model_dump(mode="json") for r in recommendations]),
        critic_notes,
        json.dumps(trace),
    )
