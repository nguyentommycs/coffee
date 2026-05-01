from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
from datetime import datetime

from app.models.taste_profile import TasteProfile


class RecommendationCandidate(BaseModel):
    name: str
    roaster: str
    product_url: HttpUrl
    origin_country: Optional[str] = None
    origin_region: Optional[str] = None
    process: Optional[str] = None
    roast_level: Optional[str] = None
    tasting_notes: list[str] = []
    price_usd: Optional[float] = None
    in_stock: Optional[bool] = None
    match_score: float = 0.0
    match_rationale: str = ""


class RecommendationResponse(BaseModel):
    user_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    taste_profile: TasteProfile
    recommendations: list[RecommendationCandidate]
    critic_notes: str
