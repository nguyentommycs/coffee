import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = os.environ["DATABASE_URL"]
    brave_api_key: str | None = os.environ.get("BRAVE_API_KEY")
    google_api_key: str | None = os.environ.get("GOOGLE_API_KEY")
    # Gemini model for all LLM calls. Flash is free-tier.
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")


settings = Settings()
