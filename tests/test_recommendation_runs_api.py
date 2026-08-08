"""Unit tests for the GET /recommendation-runs endpoint (DB queries mocked)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.db.queries import _jsonb
from app.main import app

client = TestClient(app)

RUN_ID = "3f1a2b4c-5d6e-4f70-8912-abcdef012345"
CREATED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

RECOMMENDATIONS = [
    {
        "roaster": "Onyx",
        "name": "Geometry",
        "product_url": "https://onyx.test/geometry",
        "match_score": 0.8,
        "reasoning": "fruity",
    }
]

TRACE_WITH_COSTS = {
    "spans": [
        {"name": "profiler", "type": "agent", "attrs": {}},
        {"name": "llm:profiler", "type": "llm", "attrs": {"cost_usd": 0.001}},
        {"name": "llm:critic", "type": "llm", "attrs": {"cost_usd": 0.0025}},
    ]
}

LEGACY_TRACE = {
    "spans": [
        {"name": "profiler", "start": 1.0, "status": "ok"},
        {"name": "critic", "start": 2.0, "status": "ok"},
    ]
}


def _run(**overrides):
    run = {
        "id": RUN_ID,
        "created_at": CREATED_AT,
        "critic_notes": "Dropped two candidates.",
        "recommendations": RECOMMENDATIONS,
        "taste_profile_snapshot": {"preferred_origins": ["Ethiopia"]},
        "pipeline_trace": TRACE_WITH_COSTS,
    }
    run.update(overrides)
    return run


def test_run_with_modern_trace_reports_summed_cost():
    with patch("app.main.get_recommendation_runs", new=AsyncMock(return_value=[_run()])):
        resp = client.get("/recommendation-runs", params={"user_id": "u1"})

    assert resp.status_code == 200
    (item,) = resp.json()
    assert item["id"] == RUN_ID
    assert item["total_cost_usd"] == 0.0035
    assert item["recommendations"] == RECOMMENDATIONS
    assert item["critic_notes"] == "Dropped two candidates."
    assert item["taste_profile_snapshot"] == {"preferred_origins": ["Ethiopia"]}
    # the trace is large and already served by /traces
    assert "pipeline_trace" not in item


def test_run_without_trace_has_null_cost():
    with patch(
        "app.main.get_recommendation_runs", new=AsyncMock(return_value=[_run(pipeline_trace=None)])
    ):
        resp = client.get("/recommendation-runs", params={"user_id": "u1"})

    assert resp.status_code == 200
    assert resp.json()[0]["total_cost_usd"] is None


def test_legacy_trace_without_span_types_has_null_cost():
    with patch(
        "app.main.get_recommendation_runs",
        new=AsyncMock(return_value=[_run(pipeline_trace=LEGACY_TRACE)]),
    ):
        resp = client.get("/recommendation-runs", params={"user_id": "u1"})

    assert resp.status_code == 200
    assert resp.json()[0]["total_cost_usd"] is None


def test_no_runs_returns_empty_list():
    with patch("app.main.get_recommendation_runs", new=AsyncMock(return_value=[])):
        resp = client.get("/recommendation-runs", params={"user_id": "u1"})

    assert resp.status_code == 200
    assert resp.json() == []


def test_jsonb_parses_strings_and_passes_through_parsed_values():
    assert _jsonb('{"a": 1}') == {"a": 1}
    assert _jsonb([{"a": 1}]) == [{"a": 1}]
    assert _jsonb(None) is None
