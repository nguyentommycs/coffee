import pytest
from uuid import uuid4

from app.db.connection import close_pool, get_pool, init_pool
from app.db.queries import create_user


@pytest.fixture
async def db_pool():
    await init_pool()
    yield
    await close_pool()


@pytest.fixture
async def test_user(db_pool):
    user_id = f"e2e-test-{uuid4().hex[:8]}"
    await create_user(user_id)
    yield user_id
    pool = get_pool()
    # FK deletion order: child tables before users
    await pool.execute("DELETE FROM recommendation_runs WHERE user_id = $1", user_id)
    await pool.execute("DELETE FROM taste_profiles WHERE user_id = $1", user_id)
    await pool.execute("DELETE FROM bean_profiles WHERE user_id = $1", user_id)
    await pool.execute("DELETE FROM users WHERE id = $1", user_id)
