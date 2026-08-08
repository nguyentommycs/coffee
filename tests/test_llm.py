"""Unit tests for tracing inside app/llm.py::llm_complete (the genai client is mocked)."""
import uuid
from unittest.mock import MagicMock, patch

import pytest

import app.llm as llm_module
from app.llm import llm_complete
from app.observability.trace import TraceLogger


def _mock_response(text: str, input_tokens=11, output_tokens=22) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    resp.usage_metadata.prompt_token_count = input_tokens
    resp.usage_metadata.candidates_token_count = output_tokens
    return resp


@pytest.fixture(autouse=True)
def no_throttle():
    """Reset the inter-call throttle so tests never sleep."""
    llm_module._last_call_at = 0.0
    yield
    llm_module._last_call_at = 0.0


async def test_llm_span_collects_tokens_and_texts():
    trace = TraceLogger(pipeline_id=uuid.uuid4(), user_id="u1")
    with (
        patch("app.llm._get_client", return_value=MagicMock()),
        patch("app.llm._generate", return_value=_mock_response('{"ok": true}')),
    ):
        with trace.activate():
            with trace.span("recommendation"):
                text = await llm_complete("extract this", span="recommendation_extract")

    assert text == '{"ok": true}'
    span = next(s for s in trace.spans if s["type"] == "llm")
    assert span["name"] == "llm:recommendation_extract"
    assert span["status"] == "ok"
    assert span["attrs"]["label"] == "recommendation_extract"
    assert span["attrs"]["input_tokens"] == 11
    assert span["attrs"]["output_tokens"] == 22
    assert span["attrs"]["retried_429"] is False
    assert span["attrs"]["prompt"] == "extract this"
    assert span["attrs"]["response"] == '{"ok": true}'


async def test_llm_span_truncates_long_prompt_and_response():
    long_prompt = "x" * 5000
    trace = TraceLogger(pipeline_id=uuid.uuid4(), user_id="u1")
    with (
        patch("app.llm._get_client", return_value=MagicMock()),
        patch("app.llm._generate", return_value=_mock_response("y" * 5000)),
    ):
        with trace.activate():
            await llm_complete(long_prompt, span="profiler")

    span = trace.spans[0]
    assert span["attrs"]["prompt"] == "x" * 4000 + "… [truncated]"
    assert span["attrs"]["response"] == "y" * 4000 + "… [truncated]"


async def test_llm_span_tolerates_missing_usage_metadata():
    resp = MagicMock()
    resp.text = "{}"
    resp.usage_metadata = None
    trace = TraceLogger(pipeline_id=uuid.uuid4(), user_id="u1")
    with (
        patch("app.llm._get_client", return_value=MagicMock()),
        patch("app.llm._generate", return_value=resp),
    ):
        with trace.activate():
            await llm_complete("hi", span="profiler")

    span = trace.spans[0]
    assert span["attrs"]["input_tokens"] is None
    assert span["attrs"]["output_tokens"] is None


async def test_llm_failure_records_error_span():
    trace = TraceLogger(pipeline_id=uuid.uuid4(), user_id="u1")
    with (
        patch("app.llm._get_client", return_value=MagicMock()),
        patch("app.llm._generate", side_effect=RuntimeError("upstream down")),
    ):
        with trace.activate():
            with pytest.raises(RuntimeError):
                await llm_complete("hi", span="profiler")

    span = trace.spans[0]
    assert span["status"] == "error"
    assert span["error"] == "upstream down"


async def test_llm_without_active_trace_still_works():
    with (
        patch("app.llm._get_client", return_value=MagicMock()),
        patch("app.llm._generate", return_value=_mock_response("done")),
    ):
        assert await llm_complete("hi", span="profiler") == "done"
