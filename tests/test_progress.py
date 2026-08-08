"""Unit tests for the in-process progress registry and the GET /progress/{id} endpoint."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability import progress


@pytest.fixture(autouse=True)
def clean_registry():
    progress._registry.clear()
    yield
    progress._registry.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _start(name: str) -> dict:
    return {"phase": "start", "name": name, "type": "agent"}


def _end(name: str, status: str = "ok", duration_ms: float = 120.0) -> dict:
    return {
        "phase": "end", "name": name, "type": "agent",
        "status": status, "duration_ms": duration_ms,
    }


# ---------------------------------------------------------------------------
# ProgressTracker
# ---------------------------------------------------------------------------

def test_start_event_marks_stage_running():
    tracker = progress.ProgressTracker()
    tracker.on_span_event(_start("profiler"))

    snap = tracker.snapshot()
    assert snap["finished"] is False
    assert snap["status"] == "running"
    (stage,) = snap["stages"]
    assert stage["key"] == "profiler"
    assert stage["status"] == "running"
    assert stage["elapsed_ms"] >= 0


def test_end_event_marks_stage_done_with_duration():
    tracker = progress.ProgressTracker()
    tracker.on_span_event(_start("profiler"))
    tracker.on_span_event(_end("profiler", duration_ms=900.0))

    (stage,) = tracker.snapshot()["stages"]
    assert stage["status"] == "done"
    assert stage["elapsed_ms"] == 900.0


def test_end_event_with_error_status_marks_stage_error():
    tracker = progress.ProgressTracker()
    tracker.on_span_event(_start("critic"))
    tracker.on_span_event(_end("critic", status="error"))

    (stage,) = tracker.snapshot()["stages"]
    assert stage["status"] == "error"


def test_non_agent_events_are_ignored():
    tracker = progress.ProgressTracker()
    tracker.on_span_event({"phase": "start", "name": "llm:profiler", "type": "llm"})
    tracker.on_span_event({"phase": "start", "name": "scrape_page", "type": "tool"})

    assert tracker.snapshot()["stages"] == []


def test_stages_keep_emission_order():
    tracker = progress.ProgressTracker()
    for name in ("profiler", "recommendation", "critic"):
        tracker.on_span_event(_start(name))
        tracker.on_span_event(_end(name))

    keys = [s["key"] for s in tracker.snapshot()["stages"]]
    assert keys == ["profiler", "recommendation", "critic"]


def test_snapshot_shape():
    tracker = progress.ProgressTracker()
    tracker.on_span_event(_start("profiler"))

    snap = tracker.snapshot()
    assert set(snap) == {"finished", "status", "stages"}
    assert set(snap["stages"][0]) == {"key", "status", "elapsed_ms"}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_start_and_get_snapshot_round_trip():
    tracker = progress.start("p1")
    tracker.on_span_event(_start("profiler"))

    snap = progress.get_snapshot("p1")
    assert snap is not None
    assert [s["key"] for s in snap["stages"]] == ["profiler"]


def test_get_snapshot_unknown_id_is_none():
    assert progress.get_snapshot("nope") is None


def test_finish_sets_finished_and_status():
    progress.start("p1")
    progress.finish("p1", "ok")

    snap = progress.get_snapshot("p1")
    assert snap["finished"] is True
    assert snap["status"] == "ok"


def test_finish_unknown_id_is_a_noop():
    progress.finish("nope", "ok")  # must not raise
    assert progress.get_snapshot("nope") is None


def test_registry_evicts_oldest_past_size_cap():
    for i in range(progress.MAX_ENTRIES + 5):
        progress.start(f"p{i}")

    assert len(progress._registry) == progress.MAX_ENTRIES
    assert progress.get_snapshot("p0") is None
    assert progress.get_snapshot("p4") is None
    assert progress.get_snapshot("p5") is not None
    assert progress.get_snapshot(f"p{progress.MAX_ENTRIES + 4}") is not None


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def test_progress_endpoint_returns_snapshot(client):
    tracker = progress.start("p1")
    tracker.on_span_event(_start("profiler"))
    tracker.on_span_event(_end("profiler", duration_ms=900.0))
    tracker.on_span_event(_start("recommendation"))

    res = client.get("/progress/p1")

    assert res.status_code == 200
    body = res.json()
    assert body["finished"] is False
    assert body["status"] == "running"
    assert [(s["key"], s["status"]) for s in body["stages"]] == [
        ("profiler", "done"),
        ("recommendation", "running"),
    ]
    assert body["stages"][0]["elapsed_ms"] == 900.0


def test_progress_endpoint_404_for_unknown_id(client):
    res = client.get("/progress/unknown")

    assert res.status_code == 404
    assert res.json()["detail"] == "progress not found"
