from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
import uuid


class BeanProfile(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    name: str
    roaster: str
    source_url: Optional[HttpUrl] = None

    origin_country: Optional[str] = None
    origin_region: Optional[str] = None
    farm_or_cooperative: Optional[str] = None

    process: Optional[Literal["Washed", "Natural", "Honey", "Anaerobic"]] = None
    variety: Optional[str] = None
    roast_level: Optional[Literal["Light", "Medium-Light", "Medium", "Dark"]] = None

    tasting_notes: list[str] = []

    user_score: Optional[int] = None
    user_notes: Optional[str] = None

    confidence: float = 0.0
    missing_fields: list[str] = []
    input_raw: str
    input_type: Literal["url", "name", "freeform"]

    @field_validator("user_score")
    @classmethod
    def score_in_range(cls, v):
        if v is not None and not (1 <= v <= 10):
            raise ValueError("user_score must be between 1 and 10")
        return v
