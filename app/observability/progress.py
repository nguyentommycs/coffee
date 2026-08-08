"""
In-process pipeline progress registry.

The orchestrator registers a tracker under a client-supplied progress id and
feeds it TraceLogger span events; the frontend polls GET /progress/{id}.
Single-process uvicorn only — a module-level dict is deliberate.
"""
import time

# progress_id -> ProgressTracker. Insertion-ordered; oldest evicted past MAX_ENTRIES.
_registry: dict[str, "ProgressTracker"] = {}

MAX_ENTRIES = 50


class ProgressTracker:
    """Ordered agent-stage progress for one pipeline run."""

    def __init__(self) -> None:
        self.stages: list[dict] = []
        self.finished = False
        self.status = "running"

    def on_span_event(self, event: dict) -> None:
        if event.get("type") != "agent":
            return
        name = event.get("name")
        if event.get("phase") == "start":
            self.stages.append(
                {"key": name, "status": "running", "started_at": time.time(), "duration_ms": None}
            )
        elif event.get("phase") == "end":
            for stage in reversed(self.stages):
                if stage["key"] == name:
                    stage["status"] = "error" if event.get("status") == "error" else "done"
                    stage["duration_ms"] = event.get("duration_ms")
                    break

    def snapshot(self) -> dict:
        now = time.time()
        return {
            "finished": self.finished,
            "status": self.status,
            "stages": [
                {
                    "key": s["key"],
                    "status": s["status"],
                    "elapsed_ms": (
                        s["duration_ms"]
                        if s["duration_ms"] is not None
                        else round((now - s["started_at"]) * 1000, 2)
                    ),
                }
                for s in self.stages
            ],
        }


def start(progress_id: str) -> ProgressTracker:
    tracker = ProgressTracker()
    _registry[progress_id] = tracker
    while len(_registry) > MAX_ENTRIES:
        del _registry[next(iter(_registry))]
    return tracker


def get_snapshot(progress_id: str) -> dict | None:
    tracker = _registry.get(progress_id)
    return tracker.snapshot() if tracker else None


def finish(progress_id: str, status: str) -> None:
    tracker = _registry.get(progress_id)
    if tracker is None:
        return
    tracker.finished = True
    tracker.status = status
