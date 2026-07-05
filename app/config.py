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

settings = Settings()