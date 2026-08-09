"""Unit tests for POST /beans with a URL input (agent mocked)."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agents.input_parsing import LowConfidenceError
from app.main import app
from app.models.bean_profile import BeanProfile

ONYX_URL = "https://onyxcoffeelab.com/products/geometry"

_BODY = {"user_id": "u1", "inputs": [ONYX_URL], "user_score": 8}


@pytest.fixture
def client():
    return TestClient(app)


def _profile() -> BeanProfile:
    return BeanProfile(
        user_id="u1",
        name="Geometry",
        roaster="Onyx Coffee Lab",
        source_url=ONYX_URL,
        origin_country="Ethiopia",
        process="Washed",
        roast_level="Light",
        tasting_notes=["jasmine", "peach"],
        user_score=8,
        confidence=0.9,
        missing_fields=[],
        input_raw=ONYX_URL,
        input_type="url",
    )


def test_post_beans_url_happy_path(client):
    mock_parse = AsyncMock(return_value=([_profile()], []))
    with patch("app.main.parse_and_persist", new=mock_parse):
        res = client.post("/beans", json=_BODY)

    assert res.status_code == 200
    body = res.json()
    assert body["skipped"] == []
    (bean,) = body["parsed"]
    assert bean["name"] == "Geometry"
    assert bean["roaster"] == "Onyx Coffee Lab"
    assert bean["input_type"] == "url"
    assert mock_parse.await_args.args == ("u1", [ONYX_URL], 8)


def test_post_beans_low_confidence_is_422_and_persists_nothing(client):
    mock_parse = AsyncMock(
        side_effect=LowConfidenceError(
            "Could not extract a coffee product",
            missing_fields=["name", "roaster"],
            input_raw=ONYX_URL,
        )
    )
    with patch("app.main.parse_and_persist", new=mock_parse):
        res = client.post("/beans", json=_BODY)

    assert res.status_code == 422
    body = res.json()
    assert body["error"] == "low_confidence_parse"
    assert body["fields_missing"] == ["name", "roaster"]
    assert body["input_raw"] == ONYX_URL
    assert "parsed" not in body
