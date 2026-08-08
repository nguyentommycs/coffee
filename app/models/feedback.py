from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RecommendationFeedback(BaseModel):
    user_id: str
    roaster: str
    name: str
    # Plain str rather than HttpUrl — this round-trips straight to/from a TEXT column.
    product_url: str
    verdict: Literal["up", "down"]
    updated_at: datetime = Field(default_factory=datetime.utcnow)
