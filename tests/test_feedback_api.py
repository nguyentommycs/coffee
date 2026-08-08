"""Unit tests for the /feedback endpoints (DB queries mocked)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.feedback import RecommendationFeedback

UPDATED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

_BODY = {
    "user_id": "u1",
    "roaster": "Onyx Coffee Lab",
    "name": "Geometry",
    "product_url": "https://onyxcoffeelab.com/products/geometry",
    "verdict": "up",
}


@pytest.fixture
def client():
    return TestClient(app)


def test_post_feedback_happy_path(client):
    with patch("app.main.upsert_recommendation_feedback", new=AsyncMock()) as mock_upsert:
        res = client.post("/feedback", json=_BODY)

    assert res.status_code == 200
    body = res.json()
    assert body["roaster"] == "Onyx Coffee Lab"
    assert body["name"] == "Geometry"
    assert body["verdict"] == "up"
    assert body["product_url"] == _BODY["product_url"]

    (saved,) = mock_upsert.await_args.args
    assert isinstance(saved, RecommendationFeedback)
    assert saved.user_id == "u1"
    assert saved.roaster == "Onyx Coffee Lab"
    assert saved.name == "Geometry"
    assert saved.product_url == _BODY["product_url"]
    assert saved.verdict == "up"


def test_post_feedback_invalid_verdict_is_422(client):
    with patch("app.main.upsert_recommendation_feedback", new=AsyncMock()) as mock_upsert:
        res = client.post("/feedback", json={**_BODY, "verdict": "sideways"})

    assert res.status_code == 422
    mock_upsert.assert_not_awaited()


def test_post_feedback_unknown_user_is_404(client):
    mock_upsert = AsyncMock(side_effect=asyncpg.ForeignKeyViolationError("no user"))
    with patch("app.main.upsert_recommendation_feedback", new=mock_upsert):
        res = client.post("/feedback", json={**_BODY, "user_id": "ghost"})

    assert res.status_code == 404
    assert res.json()["detail"] == "user not found"


def test_get_feedback_returns_list(client):
    stored = [
        RecommendationFeedback(**_BODY, updated_at=UPDATED_AT),
        RecommendationFeedback(
            user_id="u1",
            roaster="Blue Bottle",
            name="Toscano Dark",
            product_url="https://bluebottlecoffee.com/products/toscano",
            verdict="down",
            updated_at=UPDATED_AT,
        ),
    ]
    with patch(
        "app.main.get_recommendation_feedback", new=AsyncMock(return_value=stored)
    ) as mock_get:
        res = client.get("/feedback", params={"user_id": "u1"})

    assert res.status_code == 200
    body = res.json()
    assert [fb["name"] for fb in body] == ["Geometry", "Toscano Dark"]
    assert [fb["verdict"] for fb in body] == ["up", "down"]
    assert mock_get.await_args.args[0] == "u1"


def test_delete_feedback_happy_path(client):
    with patch(
        "app.main.delete_recommendation_feedback", new=AsyncMock(return_value=True)
    ) as mock_delete:
        res = client.delete(
            "/feedback",
            params={"user_id": "u1", "roaster": "Onyx Coffee Lab", "name": "Geometry"},
        )

    assert res.status_code == 200
    assert res.json() == {"deleted": True}
    assert mock_delete.await_args.args == ("u1", "Onyx Coffee Lab", "Geometry")


def test_delete_feedback_not_found_is_404(client):
    with patch("app.main.delete_recommendation_feedback", new=AsyncMock(return_value=False)):
        res = client.delete(
            "/feedback",
            params={"user_id": "u1", "roaster": "Onyx Coffee Lab", "name": "Nope"},
        )

    assert res.status_code == 404
    assert res.json()["detail"] == "feedback not found"
