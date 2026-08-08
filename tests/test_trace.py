"""Unit tests for app/observability/trace.py."""
import uuid

import pytest

from app.observability.trace import TraceLogger, child_span


def _new_trace() -> TraceLogger:
    return TraceLogger(pipeline_id=uuid.uuid4(), user_id="u1")


def _by_name(trace: TraceLogger) -> dict[str, dict]:
    return {span["name"]: span for span in trace.spans}


def test_nesting_sets_parent_ids():
    trace = _new_trace()
    with trace.activate():
        with trace.span("recommendation", type="agent"):
            with child_span("scrape_page", type="tool", url="https://x.test"):
                pass
            with child_span("llm:extract", type="llm"):
                pass

    spans = _by_name(trace)
    assert spans["recommendation"]["parent_id"] is None
    assert spans["scrape_page"]["parent_id"] == spans["recommendation"]["id"]
    assert spans["llm:extract"]["parent_id"] == spans["recommendation"]["id"]
    assert spans["scrape_page"]["type"] == "tool"
    assert spans["scrape_page"]["attrs"]["url"] == "https://x.test"


def test_sibling_spans_do_not_nest():
    trace = _new_trace()
    with trace.activate():
        with trace.span("profiler"):
            pass
        with trace.span("critic"):
            pass

    spans = _by_name(trace)
    assert spans["profiler"]["parent_id"] is None
    assert spans["critic"]["parent_id"] is None
    assert spans["profiler"]["id"] != spans["critic"]["id"]


def test_child_span_is_noop_without_active_trace():
    with child_span("scrape_page", type="tool", url="https://x.test") as span:
        assert span is None


def test_trace_deactivated_after_block():
    trace = _new_trace()
    with trace.activate():
        pass
    with child_span("scrape_page", type="tool") as span:
        assert span is None
    assert trace.spans == []


def test_exception_marks_error_and_reraises():
    trace = _new_trace()
    with pytest.raises(RuntimeError):
        with trace.activate():
            with trace.span("recommendation"):
                raise RuntimeError("boom")

    span = trace.spans[0]
    assert span["status"] == "error"
    assert span["error"] == "boom"
    assert "duration_ms" in span


def test_error_in_child_does_not_leak_span_context():
    trace = _new_trace()
    with trace.activate():
        with trace.span("recommendation") as parent:
            with pytest.raises(ValueError):
                with child_span("llm:extract", type="llm"):
                    raise ValueError("bad json")
            with child_span("scrape_page", type="tool"):
                pass

    spans = _by_name(trace)
    assert spans["llm:extract"]["status"] == "error"
    assert spans["scrape_page"]["parent_id"] == parent["id"]


def test_dump_top_level_shape():
    trace = _new_trace()
    with trace.activate():
        with trace.span("profiler", n_beans=3):
            pass

    dumped = trace.dump()
    assert set(dumped) == {"pipeline_id", "user_id", "total_duration_ms", "spans"}
    assert dumped["user_id"] == "u1"
    assert dumped["spans"][0]["attrs"] == {"n_beans": 3}
