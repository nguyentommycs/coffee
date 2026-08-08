CREATE TABLE recommendation_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT REFERENCES users(id),
    roaster TEXT NOT NULL,
    name TEXT NOT NULL,
    product_url TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('up', 'down')),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, roaster, name)
);
