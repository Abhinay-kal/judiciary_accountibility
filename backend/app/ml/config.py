"""ML-specific configuration.

All settings read from the same .env / environment as the main application.
Prefix: ``ML_`` (pydantic-settings case-insensitive).

Example .env entries::

    ML_ENABLED=true
    ML_DELAY_THRESHOLD_MODERATE=1.5
    ML_DELAY_THRESHOLD_SEVERE=2.0
    ML_DELAY_THRESHOLD_EXTREME=3.0
    ML_MIN_CASES=500
    ML_ARTIFACTS_DIR=app/ml/artifacts
    ML_QUANTILE_LOWER=0.1
    ML_QUANTILE_UPPER=0.9
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    """Optional ML settings — safe defaults allow core system to run without ML."""

    # Master on/off switch
    ml_enabled: bool = True
    ml_parser_enabled: bool = False

    # Delay severity thresholds (delay_ratio = current_age / predicted_duration)
    ml_delay_threshold_moderate: float = 1.5
    ml_delay_threshold_severe: float = 2.0
    ml_delay_threshold_extreme: float = 3.0

    # Minimum disposed-case rows required to train a real model.
    # If the dataset is smaller, BaselineMedianModel is used instead.
    ml_min_cases: int = 500

    # Filesystem path (relative to working directory) where model artifacts are stored.
    ml_artifacts_dir: str = "app/ml/artifacts"

    # Hearing outcome parser artifacts.
    ml_parser_artifact_name: str = "hearing_outcome_model.pkl"
    ml_parser_report_name: str = "hearing_outcome_evaluation.json"

    # Prefix prepended to auto-generated model version strings (e.g. "v20250317_0200")
    ml_model_version_prefix: str = "v"

    # Quantiles used for uncertainty-interval GBT models
    ml_quantile_lower: float = 0.1
    ml_quantile_upper: float = 0.9

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_ml_settings() -> MLSettings:
    """Return a cached ML settings instance."""
    return MLSettings()
