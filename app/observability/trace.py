import time
import uuid
from contextlib import contextmanager


class TraceLogger:
    def __init__(self, pipeline_id: uuid.UUID, user_id: str):
        self.pipeline_id = pipeline_id
        self.user_id = user_id
        self.spans: list[dict] = []
        self.start_time = time.time()

    @contextmanager
    def span(self, name: str, **kwargs):
        span_start = time.time()
        span: dict = {"name": name, "start": span_start, "input": kwargs}
        try:
            yield span
            span["status"] = "ok"
        except Exception as exc:
            span["status"] = "error"
            span["error"] = str(exc)
            raise
        finally:
            span["duration_ms"] = round((time.time() - span_start) * 1000, 2)
            self.spans.append(span)

    def dump(self) -> dict:
        return {
            "pipeline_id": str(self.pipeline_id),
            "user_id": self.user_id,
            "total_duration_ms": round((time.time() - self.start_time) * 1000, 2),
            "spans": self.spans,
        }
