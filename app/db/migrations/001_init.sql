CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE bean_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT REFERENCES users(id),
    name TEXT NOT NULL,
    roaster TEXT NOT NULL,
    source_url TEXT,
    origin_country TEXT,
    origin_region TEXT,
    farm_or_cooperative TEXT,
    process TEXT,
    variety TEXT,
    roast_level TEXT,
    tasting_notes TEXT[],
    user_score SMALLINT CHECK (user_score >= 1 AND user_score <= 10),
    user_notes TEXT,
    confidence FLOAT,
    missing_fields TEXT[],
    input_raw TEXT,
    input_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, roaster, name)
);

CREATE TABLE taste_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    preferred_origins TEXT[],
    preferred_processes TEXT[],
    preferred_roast_levels TEXT[],
    flavor_affinities TEXT[],
    avoided_flavors TEXT[],
    narrative_summary TEXT,
    total_beans_logged INT,
    profile_confidence FLOAT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE recommendation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT REFERENCES users(id),
    taste_profile_snapshot JSONB,
    recommendations JSONB,
    critic_notes TEXT,
    pipeline_trace JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
