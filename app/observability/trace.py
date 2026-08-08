import logging
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# Ambient trace context. Set by the orchestrator for the duration of a pipeline run
# so nested code (llm.py, scraper.py, agents) can attach spans without signature churn.
_current_trace: ContextVar["TraceLogger | None"] = ContextVar("current_trace", default=None)
_current_span_id: ContextVar[str | None] = ContextVar("current_span_id", default=None)


class TraceLogger:
    def __init__(
        self,
        pipeline_id: uuid.UUID,
        user_id: str,
        listener: Callable[[dict], None] | None = None,
    ):
        self.pipeline_id = pipeline_id
        self.user_id = user_id
        self.spans: list[dict] = []
        self.start_time = time.time()
        self.listener = listener

    def _emit(self, event: dict) -> None:
        """Notifies the listener, if any. A listener bug must never break the pipeline."""
        if self.listener is None:
            return
        try:
            self.listener(event)
        except Exception:
            logger.warning("trace listener raised on event %r", event, exc_info=True)

    @contextmanager
    def activate(self):
        """Makes this trace the ambient trace for the enclosing block."""
        token = _current_trace.set(self)
        try:
            yield self
        finally:
            _current_trace.reset(token)

    @contextmanager
    def span(self, name: str, type: str = "agent", **attrs):
        span_start = time.time()
        span: dict = {
            "id": uuid.uuid4().hex[:8],
            "parent_id": _current_span_id.get(),
            "name": name,
            "type": type,
            "start": span_start,
            "attrs": attrs,
        }
        self._emit({"phase": "start", "name": name, "type": type})
        token = _current_span_id.set(span["id"])
        try:
            yield span
            span["status"] = "ok"
        except Exception as exc:
            span["status"] = "error"
            span["error"] = str(exc)
            raise
        finally:
            _current_span_id.reset(token)
            span["duration_ms"] = round((time.time() - span_start) * 1000, 2)
            self.spans.append(span)
            self._emit({
                "phase": "end",
                "name": name,
                "type": type,
                "status": span.get("status", "error"),
                "duration_ms": span["duration_ms"],
            })

    def dump(self) -> dict:
        return {
            "pipeline_id": str(self.pipeline_id),
            "user_id": self.user_id,
            "total_duration_ms": round((time.time() - self.start_time) * 1000, 2),
            "spans": self.spans,
        }


@contextmanager
def child_span(name: str, type: str, **attrs):
    """
    Attaches a span to the ambient trace, if one is active.
    Yields the mutable span dict (so callers can add result attrs), or None
    when no pipeline is running.
    """
    trace = _current_trace.get()
    if trace is None:
        yield None
        return
    with trace.span(name, type=type, **attrs) as span:
        yield span
