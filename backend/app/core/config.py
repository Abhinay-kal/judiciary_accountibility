from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Court Case Delay & Justice Tracker"
    app_env: str = "development"
    app_debug: bool = True
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg2://postgres:postgres@db:5432/justice_tracker"
    redis_url: str = "redis://redis:6379/0"

    celery_task_default_queue: str = "ingestion"

    scraper_user_agent: str = "JusticeTrackerBot/1.0 (+public-accountability-platform)"
    scraper_timeout_seconds: int = 30
    scraper_max_retries: int = 3
    scraper_rate_limit_seconds: float = 1.0

    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""

    return Settings()
