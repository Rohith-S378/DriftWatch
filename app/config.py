from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Fallback to SQLite if PostgreSQL not available
    DATABASE_URL: str = "sqlite+aiosqlite:///./sirius.db"
    WEBHOOK_SECRET: str = "test"
    NODE_API_URL: Optional[str] = None
    INTERNAL_SECRET: Optional[str] = None
    PRICE_CHANGE_THRESHOLD_PCT: float = 5.0
    ANOMALY_ZSCORE_THRESHOLD: float = 2.5
    ALLOW_LOCAL_CRAWLS: bool = False
    # Legacy data access policy:
    # When False (default/strict), rows with user_id IS NULL are NOT visible
    # to authenticated users. Only the user's own rows are returned.
    # When True (backward-compat opt-in), legacy pre-auth rows are visible to all users.
    ALLOW_LEGACY_GLOBAL_READS: bool = False

    # Competitor Discovery settings
    TAVILY_API_KEY: Optional[str] = None
    SERPAPI_API_KEY: Optional[str] = None
    DISCOVERY_SEARCH_PROVIDER: str = "auto"  # "auto", "tavily", "serpapi", "mock"
    DISCOVERY_MAX_CANDIDATES: int = 10

    # Google OAuth settings (optional; honest unconfigured state when empty)
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = "http://localhost:8000/api/auth/google/callback"
    # Frontend URL for post-OAuth redirect (dashboard lives on the Vite dev server)
    FRONTEND_URL: Optional[str] = "http://localhost:5173"

settings = Settings()