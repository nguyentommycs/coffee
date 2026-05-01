from pydantic import BaseModel, Field
from datetime import datetime


class TasteProfile(BaseModel):
    user_id: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    preferred_origins: list[str]
    preferred_processes: list[str]
    preferred_roast_levels: list[str]
    flavor_affinities: list[str]
    avoided_flavors: list[str]

    narrative_summary: str

    total_beans_logged: int
    profile_confidence: float
