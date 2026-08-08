import json
from typing import Optional

from app.db.connection import get_pool
from app.models.bean_profile import BeanProfile
from app.models.feedback import RecommendationFeedback
from app.models.recommendation import RecommendationCandidate
from app.models.taste_profile import TasteProfile


async def create_user(user_id: str) -> None:
    pool = get_pool()
    await pool.execute(
        "INSERT INTO users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
        user_id,
    )


async def get_taste_profile(user_id: str) -> Optional[TasteProfile]:
    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM taste_profiles WHERE user_id = $1",
        user_id,
    )
    return TasteProfile(**dict(row)) if row else None


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


async def update_bean_profile(bean_id, user_id: str, fields: dict) -> Optional[BeanProfile]:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        UPDATE bean_profiles SET
            name = $3, roaster = $4, origin_country = $5, origin_region = $6,
            farm_or_cooperative = $7, process = $8, variety = $9, roast_level = $10,
            tasting_notes = $11, user_score = $12, user_notes = $13
        WHERE id = $1 AND user_id = $2
        RETURNING *
        """,
        bean_id,
        user_id,
        fields["name"],
        fields["roaster"],
        fields["origin_country"],
        fields["origin_region"],
        fields["farm_or_cooperative"],
        fields["process"],
        fields["variety"],
        fields["roast_level"],
        fields["tasting_notes"],
        fields["user_score"],
        fields["user_notes"],
    )
    return BeanProfile(**dict(row)) if row else None


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


async def get_recommendation_runs(user_id: str) -> list[dict]:
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT id, created_at, critic_notes, recommendations, taste_profile_snapshot
        FROM recommendation_runs
        WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        user_id,
    )
    return [dict(row) for row in rows]


def _row_to_trace(row) -> dict:
    raw = row["pipeline_trace"]
    return {
        "run_id": str(row["id"]),
        "created_at": row["created_at"],
        "trace": json.loads(raw) if isinstance(raw, str) else raw,
    }


async def get_pipeline_traces(user_id: str) -> list[dict]:
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT id, created_at, pipeline_trace
        FROM recommendation_runs
        WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        user_id,
    )
    return [_row_to_trace(row) for row in rows]


async def get_pipeline_trace(run_id, user_id: str) -> Optional[dict]:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, created_at, pipeline_trace
        FROM recommendation_runs
        WHERE id = $1 AND user_id = $2
        """,
        run_id,
        user_id,
    )
    return _row_to_trace(row) if row else None


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


async def upsert_recommendation_feedback(fb: RecommendationFeedback) -> None:
    pool = get_pool()
    await pool.execute(
        """
        INSERT INTO recommendation_feedback
            (user_id, roaster, name, product_url, verdict, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (user_id, roaster, name)
        DO UPDATE SET
            verdict = EXCLUDED.verdict,
            product_url = EXCLUDED.product_url,
            updated_at = EXCLUDED.updated_at
        """,
        fb.user_id,
        fb.roaster,
        fb.name,
        fb.product_url,
        fb.verdict,
        fb.updated_at,
    )


async def get_recommendation_feedback(user_id: str) -> list[RecommendationFeedback]:
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT user_id, roaster, name, product_url, verdict, updated_at
        FROM recommendation_feedback
        WHERE user_id = $1
        ORDER BY updated_at DESC
        """,
        user_id,
    )
    return [RecommendationFeedback(**dict(row)) for row in rows]


async def delete_recommendation_feedback(user_id: str, roaster: str, name: str) -> bool:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        DELETE FROM recommendation_feedback
        WHERE user_id = $1 AND roaster = $2 AND name = $3
        RETURNING id
        """,
        user_id,
        roaster,
        name,
    )
    return row is not None
