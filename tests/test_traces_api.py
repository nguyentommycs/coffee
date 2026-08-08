"""Unit tests for the GET /traces and GET /traces/{run_id} endpoints (DB queries mocked)."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

RUN_ID = "3f1a2b4c-5d6e-4f70-8912-abcdef012345"
CREATED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

MODERN_TRACE = {
    "pipeline_id": "p1",
    "user_id": "u1",
    "total_duration_ms": 4200.0,
    "spans": [
        {
            "id": "a1", "parent_id": None, "name": "profiler", "type": "agent",
            "start": 1.0, "duration_ms": 900.0, "status": "ok", "attrs": {"n_beans": 4},
        },
        {
            "id": "b1", "parent_id": "a1", "name": "llm:profiler", "type": "llm",
            "start": 1.1, "duration_ms": 800.0, "status": "ok",
            # cost recorded at call time
            "attrs": {
                "input_tokens": 100, "output_tokens": 20, "cost_usd": 0.000055,
                "model": "gemini-3.1-flash-lite-preview", "prompt": "p", "response": "r",
            },
        },
        {
            "id": "c1", "parent_id": None, "name": "recommendation", "type": "agent",
            "start": 2.0, "duration_ms": 3000.0, "status": "ok", "attrs": {"broad_mode": False},
        },
        {
            "id": "d1", "parent_id": "c1", "name": "llm:recommendation_extract", "type": "llm",
            "start": 2.5, "duration_ms": 1200.0, "status": "ok",
            # written before cost_usd existed — priced from model + tokens
            "attrs": {
                "input_tokens": 5000, "output_tokens": 400,
                "model": "gemini-3.1-flash-lite-preview",
            },
        },
        {
            "id": "e1", "parent_id": "c1", "name": "scrape_page", "type": "tool",
            "start": 2.1, "duration_ms": 200.0, "status": "error", "error": "timeout",
            "attrs": {"url": "https://x.test"},
        },
    ],
}

# Written before the span schema gained id/parent_id/type/attrs.
LEGACY_TRACE = {
    "pipeline_id": "p0",
    "user_id": "u1",
    "total_duration_ms": 1000.0,
    "spans": [
        {"name": "profiler", "start": 1.0, "input": {}, "status": "ok", "duration_ms": 500.0},
        {"name": "critic", "start": 2.0, "input": {}, "status": "ok", "duration_ms": 500.0},
    ],
}


@pytest.fixture
def client():
    return TestClient(app)


def test_traces_list_summary(client):
    runs = [{"run_id": RUN_ID, "created_at": CREATED_AT, "trace": MODERN_TRACE}]
    with patch("app.main.get_pipeline_traces", new=AsyncMock(return_value=runs)):
        res = client.get("/traces", params={"user_id": "u1"})

    assert res.status_code == 200
    (summary,) = res.json()
    assert summary["run_id"] == RUN_ID
    assert summary["total_duration_ms"] == 4200.0
    assert summary["span_count"] == 5
    assert summary["llm_calls"] == 2
    assert summary["total_input_tokens"] == 5100
    assert summary["total_output_tokens"] == 420
    assert summary["status"] == "error"  # the scrape span errored
    # 0.000055 recorded on b1 + 0.00185 derived from d1's model + tokens
    assert summary["total_cost_usd"] == pytest.approx(0.001905)


def test_traces_list_cost_is_none_when_no_span_is_costable(client):
    trace = {
        "total_duration_ms": 100.0,
        "spans": [
            {
                "id": "b1", "name": "llm:profiler", "type": "llm", "start": 1.0,
                "duration_ms": 50.0, "status": "ok",
                # unknown model, no recorded cost
                "attrs": {"input_tokens": 100, "output_tokens": 20, "model": "gemini-mystery"},
            },
        ],
    }
    runs = [{"run_id": RUN_ID, "created_at": CREATED_AT, "trace": trace}]
    with patch("app.main.get_pipeline_traces", new=AsyncMock(return_value=runs)):
        res = client.get("/traces", params={"user_id": "u1"})

    assert res.status_code == 200
    (summary,) = res.json()
    assert summary["llm_calls"] == 1
    assert summary["total_cost_usd"] is None


def test_traces_list_legacy_trace_does_not_crash(client):
    runs = [{"run_id": RUN_ID, "created_at": CREATED_AT, "trace": LEGACY_TRACE}]
    with patch("app.main.get_pipeline_traces", new=AsyncMock(return_value=runs)):
        res = client.get("/traces", params={"user_id": "u1"})

    assert res.status_code == 200
    (summary,) = res.json()
    assert summary["status"] == "ok"
    assert summary["span_count"] == 2
    assert summary["llm_calls"] == 0
    assert summary["total_input_tokens"] == 0
    assert summary["total_output_tokens"] == 0
    assert summary["total_cost_usd"] is None


def test_traces_list_null_trace_does_not_crash(client):
    runs = [{"run_id": RUN_ID, "created_at": CREATED_AT, "trace": None}]
    with patch("app.main.get_pipeline_traces", new=AsyncMock(return_value=runs)):
        res = client.get("/traces", params={"user_id": "u1"})

    assert res.status_code == 200
    (summary,) = res.json()
    assert summary["span_count"] == 0
    assert summary["total_duration_ms"] is None


def test_traces_list_empty(client):
    with patch("app.main.get_pipeline_traces", new=AsyncMock(return_value=[])):
        res = client.get("/traces", params={"user_id": "u1"})

    assert res.status_code == 200
    assert res.json() == []


def test_trace_detail(client):
    run = {"run_id": RUN_ID, "created_at": CREATED_AT, "trace": MODERN_TRACE}
    with patch("app.main.get_pipeline_trace", new=AsyncMock(return_value=run)) as mock_get:
        res = client.get(f"/traces/{RUN_ID}", params={"user_id": "u1"})

    assert res.status_code == 200
    body = res.json()
    assert body["run_id"] == RUN_ID
    assert body["trace"]["spans"][0]["name"] == "profiler"
    assert mock_get.await_args.args[1] == "u1"


def test_trace_detail_404_for_other_user(client):
    with patch("app.main.get_pipeline_trace", new=AsyncMock(return_value=None)):
        res = client.get(f"/traces/{RUN_ID}", params={"user_id": "someone-else"})

    assert res.status_code == 404
