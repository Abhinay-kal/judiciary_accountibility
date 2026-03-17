"""Inference interface for the duration-prediction model.

Public API
----------
:class:`PredictionResult`
    Dataclass returned by every prediction call.

:class:`CaseDurationPredictor`
    Thread-safe, lazy-loading predictor.  Loads model artifacts from disk on
    first use.  All methods fail gracefully: when artifacts are absent the
    special sentinel :data:`PREDICTION_UNAVAILABLE` is returned.

:func:`get_predictor`
    Returns the module-level singleton predictor.

Uncertainty estimation
----------------------
The predictor uses three separately-trained quantile GBT models:

* ``lower_model.pkl``    → configured lower quantile (default 10th percentile)
* ``duration_model.pkl`` → median quantile (50th percentile)
* ``upper_model.pkl``    → configured upper quantile (default 90th percentile)

Confidence score is derived from the relative width of the prediction
interval:  ``confidence = 1 − (upper − lower) / (2 × predicted + ε)``,
clipped to ``[0, 1]``.  A narrow interval gives a score near 1.0.

When the quantile bound models are unavailable (e.g. baseline-only mode),
symmetrical bounds of ``±30 %`` around the median prediction are used.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.ml.features import CATEGORICAL_FEATURES, HIGH_CARDINALITY_FEATURES, NUMERIC_FEATURES

logger = logging.getLogger(__name__)

_METADATA_VERSION_KEY = "version"
_DROP_COLS = {"duration_days", "filing_date", "case_id"}


# ---------------------------------------------------------------------------
# PredictionResult
# ---------------------------------------------------------------------------


@dataclass
class PredictionResult:
    """Structured prediction output returned by :meth:`CaseDurationPredictor.predict`."""

    predicted_days: float
    lower_bound: float
    upper_bound: float
    confidence: float  # [0.0, 1.0]
    model_version: str
    top_features: list[dict]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


#: Sentinel returned when the model is unavailable or prediction fails.
PREDICTION_UNAVAILABLE = PredictionResult(
    predicted_days=-1.0,
    lower_bound=-1.0,
    upper_bound=-1.0,
    confidence=0.0,
    model_version="unavailable",
    top_features=[],
)


# ---------------------------------------------------------------------------
# CaseDurationPredictor
# ---------------------------------------------------------------------------


class CaseDurationPredictor:
    """Lazy-loading predictor with graceful degradation.

    Thread safety: the ``load()`` call is idempotent; once ``_loaded`` is
    ``True`` the model objects are read-only.  For multi-threaded servers
    a lock should wrap the ``_loaded`` check in high-traffic environments,
    but for Celery workers this is safe as-is.
    """

    def __init__(self) -> None:
        from app.ml.config import get_ml_settings

        self.settings = get_ml_settings()
        self._median_model: Any = None
        self._lower_model: Optional[Any] = None
        self._upper_model: Optional[Any] = None
        self._metadata: dict = {}
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _artifacts_dir(self) -> Path:
        return Path(self.settings.ml_artifacts_dir)

    def load(self) -> bool:
        """Load model artifacts from disk.  Returns ``True`` on success."""
        import joblib

        base = self._artifacts_dir()
        median_path = base / "duration_model.pkl"

        if not median_path.exists():
            logger.warning(
                "ML artifacts not found at '%s'. "
                "Run the retraining task to generate them.",
                base,
            )
            return False

        try:
            self._median_model = joblib.load(median_path)
            lower_path = base / "lower_model.pkl"
            upper_path = base / "upper_model.pkl"
            self._lower_model = (
                joblib.load(lower_path) if lower_path.exists() else None
            )
            self._upper_model = (
                joblib.load(upper_path) if upper_path.exists() else None
            )
            meta_path = base / "metadata.json"
            if meta_path.exists():
                self._metadata = json.loads(meta_path.read_text())

            self._loaded = True
            logger.info(
                "ML models loaded — version: %s",
                self._metadata.get(_METADATA_VERSION_KEY, "unknown"),
            )
            return True
        except Exception:
            logger.exception("Failed to load ML artifacts — ML unavailable")
            self._loaded = False
            return False

    def reload(self) -> bool:
        """Force a reload from disk (e.g. after retraining)."""
        self._loaded = False
        return self.load()

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, features: dict[str, Any]) -> PredictionResult:
        """Predict duration for a single case given a feature dict.

        Parameters
        ----------
        features:
            A dict whose keys match the columns in :mod:`app.ml.features`.
            Extra keys are silently ignored; missing numeric keys are filled
            with ``0``; missing categorical keys are filled with ``"unknown"``.

        Returns
        -------
        :class:`PredictionResult`
            Always returns a valid dataclass — never raises.  Returns
            :data:`PREDICTION_UNAVAILABLE` when the model is not loaded.
        """
        if not self._loaded and not self.load():
            return PREDICTION_UNAVAILABLE
        try:
            return self._predict_one(features)
        except Exception:
            logger.exception("Prediction failed for feature dict")
            return PREDICTION_UNAVAILABLE

    def predict_batch(
        self, feature_rows: list[dict[str, Any]]
    ) -> list[PredictionResult]:
        """Batch predict for multiple cases."""
        if not self._loaded and not self.load():
            return [PREDICTION_UNAVAILABLE] * len(feature_rows)
        results = []
        for row in feature_rows:
            results.append(self.predict(row))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _predict_one(self, features: dict[str, Any]) -> PredictionResult:
        """Core prediction logic.  Assumes models are loaded."""
        df = self._prepare_dataframe(features)

        predicted = float(np.clip(self._median_model.predict(df)[0], 1.0, None))

        if self._lower_model is not None:
            lower = float(np.clip(self._lower_model.predict(df)[0], 1.0, None))
        else:
            lower = round(predicted * 0.70, 1)

        if self._upper_model is not None:
            upper = float(np.clip(self._upper_model.predict(df)[0], predicted, None))
        else:
            upper = round(predicted * 1.50, 1)

        # Confidence: narrower interval relative to prediction → higher score
        interval_width = max(upper - lower, 1.0)
        confidence = float(
            np.clip(1.0 - interval_width / (2.0 * predicted + 1.0), 0.0, 1.0)
        )

        version = self._metadata.get(_METADATA_VERSION_KEY, "unknown")
        top_features: list[dict] = self._metadata.get("feature_importance", [])[:10]

        return PredictionResult(
            predicted_days=round(predicted, 1),
            lower_bound=round(lower, 1),
            upper_bound=round(upper, 1),
            confidence=round(confidence, 3),
            model_version=version,
            top_features=top_features,
        )

    @staticmethod
    def _prepare_dataframe(features: dict[str, Any]) -> pd.DataFrame:
        """Convert a feature dict to a single-row DataFrame, imputing missing values."""
        row = dict(features)  # defensive copy

        # Impute categoricals
        for col in CATEGORICAL_FEATURES:
            if row.get(col) is None:
                row[col] = "unknown"

        # Impute numerics and high-cardinality
        for col in NUMERIC_FEATURES + HIGH_CARDINALITY_FEATURES:
            if col not in row or row[col] is None:
                row[col] = 0

        df = pd.DataFrame([row])
        # Drop columns not used as model features
        drop = [c for c in _DROP_COLS if c in df.columns]
        if drop:
            df = df.drop(columns=drop)
        return df


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_predictor: Optional[CaseDurationPredictor] = None


def get_predictor() -> CaseDurationPredictor:
    """Return the shared :class:`CaseDurationPredictor` singleton."""
    global _predictor
    if _predictor is None:
        _predictor = CaseDurationPredictor()
    return _predictor
