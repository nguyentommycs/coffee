from pydantic import BaseModel
from datetime import datetime


class LLMCallRecord(BaseModel):
    span: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    timestamp: datetime
