from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ml.config import get_ml_settings


@dataclass
class ImportanceMLPrediction:
    calibrated_score: float
    confidence: float
    feature_importance: dict[str, float]


def maybe_predict_importance(features: dict[str, Any]) -> ImportanceMLPrediction | None:
    """Optional ML hook for future calibrated importance scoring.

    Returns ``None`` when ML is disabled so deterministic rule scoring remains the source of truth.
    """

    ml_cfg = get_ml_settings()
    if not ml_cfg.ml_enabled:
        return None

    # Placeholder for future model inference. Keep deterministic behavior for now.
    return None
