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
    ingestion_worker_count: int = 6
    parsing_worker_count: int = 4
    analytics_worker_count: int = 2
    notification_worker_count: int = 3
    queue_priority_enabled: bool = True
    ingestion_queue_max_depth: int = 2000
    ingestion_rate_limit_per_minute: int = 120

    scraper_user_agent: str = "JusticeTrackerBot/1.0 (+public-accountability-platform)"
    scraper_timeout_seconds: int = 30
    scraper_max_retries: int = 3
    scraper_rate_limit_seconds: float = 1.0
    scraper_concurrency: int = 5

    cache_ttl_seconds: int = 60
    cache_enabled: bool = True
    cache_default_ttl: int = 120
    cache_warmup_enabled: bool = True
    cache_app_prefix: str = "app"
    cache_key_version: str = "v1"
    cache_l1_max_items: int = 5000
    cache_ttl_short_seconds: int = 60
    cache_ttl_medium_seconds: int = 300
    cache_ttl_long_seconds: int = 1800
    cache_stale_multiplier: int = 3
    materialized_view_refresh_interval: int = 3600
    rate_limit_per_minute: int = 120

    default_outcome_confidence_verify: float = 0.60
    outcome_parser_version: str = "outcome-rules-v1"

    judge_match_levenshtein_threshold: float = 0.18
    judge_match_confidence_threshold: float = 0.60
    enable_judge_ml_matcher: bool = False
    judge_provisional_retention_days: int = 365
    judge_atribution_batch_size: int = 500
    judge_attribution_batch_size: int = 500

    delta_fetch_enabled: bool = True
    cas_enabled: bool = True
    lifecycle_hot_days: int = 30
    lifecycle_warm_days: int = 90
    manual_ingest_enabled: bool = True
    ingest_alert_hours: int = 24

    importance_weights_json: str | None = None
    importance_min_confidence: float = 0.20
    importance_media_decay_lambda: float = 0.05
    importance_monetary_cap: float = 50000000.0
    importance_min_case_signals: int = 2
    importance_fastpass_enabled: bool = True
    importance_daily_batch_size: int = 1000

    delay_baseline_window_years: int = 7
    delay_min_group_sample_size: int = 20
    delay_use_time_weighted_baseline: bool = False
    delay_half_life_days: int = 730
    delay_update_batch_size: int = 2000
    delay_percentile_anomaly_threshold: float = 90.0
    delay_robust_z_anomaly_threshold: float = 2.0
    delay_ratio_moderate_threshold: float = 1.5
    delay_ratio_high_threshold: float = 2.0
    delay_ratio_extreme_threshold: float = 3.0

    survival_window_years: int = 10
    survival_min_sample_size: int = 25
    survival_recompute_batch_size: int = 5000
    survival_prediction_horizon_days: int = 365 * 5
    survival_unusual_percentile_threshold: float = 90.0
    survival_low_probability_threshold: float = 0.10

    dormancy_min_days_default: int = 180
    dormancy_normalized_threshold: float = 2.0
    dormancy_severe_normalized_threshold: float = 3.0
    dormancy_min_data_confidence: float = 0.5
    dormancy_baseline_min_samples: int = 20
    dormancy_batch_size: int = 3000
    dormancy_future_listing_horizon_days: int = 30

    defamation_mode: str = "standard"
    defamation_default_label: str = "UNVERIFIED"
    defamation_min_confidence_to_show_name: float = 0.70
    correction_request_retention_days: int = 365
    notify_on_correction_email: str = ""
    rate_limit_correction_requests_per_target_per_month: int = 3

    feedback_token_expiry_hours: int = 48
    feedback_max_attachments: int = 5
    feedback_max_attachment_size_mb: int = 10
    feedback_rate_limit_per_contact_per_month: int = 3
    feedback_whitelisted_domains: str = ""
    feedback_auto_verify_domains: str = ""
    feedback_public_display_delay_seconds: int = 0
    feedback_email_from: str = "noreply@justice-tracker.local"
    feedback_webhook_url: str = ""
    feedback_attachment_total_limit_mb: int = 25
    feedback_enable_captcha_for_anonymous: bool = False
    feedback_enable_oauth_verification: bool = False

    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""

    return Settings()
