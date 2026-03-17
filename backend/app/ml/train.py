"""Model training pipeline.

Trains three interpretable models and selects the best by validation MAE:

1. **BaselineMedianModel** — lookup table of median ``duration_days`` grouped
   by ``(court_level, case_type)``.  Used as a sanity-check baseline and as
   the fallback when training data is insufficient.

2. **Ridge regression** — linear model with L2 regularisation, preprocessed
   by one-hot encoding categorical features and standard-scaling numerics.

3. **HistGradientBoostingRegressor (median quantile)** — gradient-boosted
   trees with ``loss='quantile'`` at ``q=0.50``.  Has native NaN support so
   imputation is only needed for categoricals.

Two additional **quantile** GBT models are trained at the configured lower
and upper quantile levels to provide prediction-interval bounds.

Artifacts saved to ``ml_artifacts_dir``:

* ``duration_model.pkl`` — best point-estimate model pipeline
* ``lower_model.pkl``    — lower-quantile GBT pipeline
* ``upper_model.pkl``    — upper-quantile GBT pipeline
* ``baseline_model.pkl`` — BaselineMedianModel (always saved)
* ``metadata.json``      — version, metrics, feature importance, timestamps

Retraining strategy
-------------------
Each :meth:`ModelTrainer.train` call generates a new timestamped version
string (``vYYYYMMDD_HHMM``).  Previous artifacts are *overwritten* in-place;
callers that need versioned history should copy artifacts before retraining,
or mount a versioned storage directory.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import joblib

from app.ml.config import get_ml_settings
from app.ml.dataset import build_training_dataset
from app.ml.evaluation import compute_metrics, time_based_split
from app.ml.features import (
    ALL_FEATURES,
    CATEGORICAL_FEATURES,
    HIGH_CARDINALITY_FEATURES,
    NUMERIC_FEATURES,
)

logger = logging.getLogger(__name__)

_TARGET = "duration_days"
_META_COLS = [_TARGET, "filing_date", "case_id"]


# ---------------------------------------------------------------------------
# Preprocessing helpers
# ---------------------------------------------------------------------------


def _build_preprocessor() -> ColumnTransformer:
    """Return a ColumnTransformer that handles categorical, numeric, and
    high-cardinality columns in a single pass."""
    cat_pipe = Pipeline(
        [("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]
    )
    num_pipe = Pipeline([("scaler", StandardScaler())])
    return ColumnTransformer(
        transformers=[
            ("cat", cat_pipe, CATEGORICAL_FEATURES),
            ("num", num_pipe, NUMERIC_FEATURES),
            # judge_id: pass through as a single numeric; HistGBT handles NaN
            ("hc", "passthrough", HIGH_CARDINALITY_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def impute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing values **in-place** (returns a copy).

    * Categorical columns → ``"unknown"``
    * Numeric and high-cardinality columns → ``0``

    This mirrors the inference imputation in :mod:`app.ml.predict` so that
    train and predict pipelines see identical data.
    """
    df = df.copy()
    for col in CATEGORICAL_FEATURES:
        if col in df.columns:
            df[col] = df[col].fillna("unknown")
    for col in NUMERIC_FEATURES + HIGH_CARDINALITY_FEATURES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


# ---------------------------------------------------------------------------
# Baseline model
# ---------------------------------------------------------------------------


class BaselineMedianModel:
    """Lookup-table model: median ``duration_days`` by ``(court_level, case_type)``.

    Falls back to the global median for unseen group combinations.
    Suitable for use even with very small datasets.
    """

    def fit(self, df: pd.DataFrame) -> "BaselineMedianModel":
        self._global_median: float = float(df[_TARGET].median())
        self._table: dict = (
            df.groupby(["court_level", "case_type"])[_TARGET].median().to_dict()
        )
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        preds = []
        for _, row in df.iterrows():
            key = (
                row.get("court_level", "unknown"),
                row.get("case_type", "unknown"),
            )
            preds.append(self._table.get(key, self._global_median))
        return np.array(preds, dtype=float)

    @property
    def global_median(self) -> float:
        return getattr(self, "_global_median", 365.0)


# ---------------------------------------------------------------------------
# Model trainer
# ---------------------------------------------------------------------------


class ModelTrainer:
    """Orchestrates training, evaluation, model selection, and artifact saving."""

    def __init__(self) -> None:
        self.settings = get_ml_settings()

    # ------------------------------------------------------------------
    # Artifacts directory (lazy, respects settings override in tests)
    # ------------------------------------------------------------------

    def _artifacts_path(self) -> Path:
        path = Path(self.settings.ml_artifacts_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def train(self, db_session: Any) -> dict[str, Any]:
        """Run the full training pipeline.

        1. Load dataset from DB.
        2. Validate minimum dataset size.
        3. Impute and time-split.
        4. Train all models and evaluate.
        5. Select best model by validation MAE.
        6. Save all artifacts.

        Returns a dict with ``version``, ``best_model``, ``metrics``,
        ``train_size``, ``val_size``.  When data is insufficient, returns
        a dict with ``insufficient_data: True`` and ``best_model: "baseline"``.
        """
        df = build_training_dataset(db_session)

        if df.empty or len(df) < self.settings.ml_min_cases:
            logger.warning(
                "Insufficient training data (%d rows, minimum %d). "
                "Saving baseline-only model.",
                len(df),
                self.settings.ml_min_cases,
            )
            return self._save_baseline_only(df)

        df = impute_features(df)
        train_df, val_df = time_based_split(df, date_col="filing_date")

        X_train = train_df.drop(columns=_META_COLS, errors="ignore")
        y_train = train_df[_TARGET].values
        X_val = val_df.drop(columns=_META_COLS, errors="ignore")
        y_val = val_df[_TARGET].values

        # --- Baseline ---
        baseline = BaselineMedianModel().fit(train_df)
        baseline_metrics = compute_metrics(y_val, baseline.predict(val_df))
        logger.info("Baseline  MAE=%.1f  RMSE=%.1f", baseline_metrics["mae"], baseline_metrics["rmse"])

        # --- Ridge ---
        ridge_pipe = Pipeline(
            [("pre", _build_preprocessor()), ("model", Ridge(alpha=100.0))]
        )
        ridge_pipe.fit(X_train, y_train)
        ridge_metrics = compute_metrics(y_val, ridge_pipe.predict(X_val))
        logger.info("Ridge     MAE=%.1f  RMSE=%.1f", ridge_metrics["mae"], ridge_metrics["rmse"])

        # --- HistGBT median ---
        hgbt_median = Pipeline(
            [
                ("pre", _build_preprocessor()),
                (
                    "model",
                    HistGradientBoostingRegressor(
                        loss="quantile",
                        quantile=0.5,
                        max_iter=300,
                        learning_rate=0.05,
                        max_depth=6,
                        random_state=42,
                    ),
                ),
            ]
        )
        hgbt_median.fit(X_train, y_train)
        hgbt_metrics = compute_metrics(y_val, hgbt_median.predict(X_val))
        logger.info("HistGBT   MAE=%.1f  RMSE=%.1f", hgbt_metrics["mae"], hgbt_metrics["rmse"])

        # --- Quantile bound models ---
        hgbt_lower = self._build_quantile_model(self.settings.ml_quantile_lower)
        hgbt_lower.fit(X_train, y_train)

        hgbt_upper = self._build_quantile_model(self.settings.ml_quantile_upper)
        hgbt_upper.fit(X_train, y_train)

        # --- Select best point-estimate model ---
        candidates = {
            "ridge": (ridge_pipe, ridge_metrics),
            "hgbt_median": (hgbt_median, hgbt_metrics),
        }
        best_name = min(candidates, key=lambda k: candidates[k][1]["mae"])
        best_model, best_metrics = candidates[best_name]
        logger.info(
            "Selected best model: %s  (MAE=%.1f days)", best_name, best_metrics["mae"]
        )

        version = (
            self.settings.ml_model_version_prefix
            + datetime.utcnow().strftime("%Y%m%d_%H%M")
        )
        feature_importance = _extract_feature_importance(best_model, X_train)

        self._save_artifacts(
            best_model=best_model,
            lower_model=hgbt_lower,
            upper_model=hgbt_upper,
            baseline=baseline,
            metrics=best_metrics,
            version=version,
            best_name=best_name,
            feature_importance=feature_importance,
            train_size=len(train_df),
            val_size=len(val_df),
        )

        return {
            "version": version,
            "best_model": best_name,
            "metrics": best_metrics,
            "train_size": len(train_df),
            "val_size": len(val_df),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_quantile_model(quantile: float) -> Pipeline:
        return Pipeline(
            [
                ("pre", _build_preprocessor()),
                (
                    "model",
                    HistGradientBoostingRegressor(
                        loss="quantile",
                        quantile=quantile,
                        max_iter=300,
                        learning_rate=0.05,
                        max_depth=6,
                        random_state=42,
                    ),
                ),
            ]
        )

    def _save_baseline_only(self, df: pd.DataFrame) -> dict[str, Any]:
        """Persist a baseline-only model when training data is insufficient."""
        baseline = BaselineMedianModel()
        if not df.empty:
            baseline.fit(df)
        else:
            baseline._global_median = 365.0
            baseline._table = {}

        version = "baseline-" + datetime.utcnow().strftime("%Y%m%d")
        meta: dict[str, Any] = {
            "version": version,
            "best_model": "baseline",
            "insufficient_data": True,
            "train_size": len(df),
            "created_at": datetime.utcnow().isoformat(),
        }
        path = self._artifacts_path()
        joblib.dump(baseline, path / "duration_model.pkl")
        joblib.dump(None, path / "lower_model.pkl")
        joblib.dump(None, path / "upper_model.pkl")
        joblib.dump(baseline, path / "baseline_model.pkl")
        (path / "metadata.json").write_text(json.dumps(meta, indent=2))
        logger.info("Baseline-only model saved: %s", version)
        return meta

    def _save_artifacts(
        self,
        *,
        best_model: Any,
        lower_model: Any,
        upper_model: Any,
        baseline: BaselineMedianModel,
        metrics: dict,
        version: str,
        best_name: str,
        feature_importance: list[dict],
        train_size: int,
        val_size: int,
    ) -> None:
        path = self._artifacts_path()
        joblib.dump(best_model, path / "duration_model.pkl")
        joblib.dump(lower_model, path / "lower_model.pkl")
        joblib.dump(upper_model, path / "upper_model.pkl")
        joblib.dump(baseline, path / "baseline_model.pkl")

        meta: dict[str, Any] = {
            "version": version,
            "best_model": best_name,
            "metrics": metrics,
            "train_size": train_size,
            "val_size": val_size,
            "feature_importance": feature_importance[:20],
            "features": ALL_FEATURES,
            "created_at": datetime.utcnow().isoformat(),
        }
        (path / "metadata.json").write_text(json.dumps(meta, indent=2))
        logger.info("ML artifacts saved → %s  version=%s", path, version)


# ---------------------------------------------------------------------------
# Feature importance extraction
# ---------------------------------------------------------------------------


def _extract_feature_importance(
    pipeline: Pipeline, X_sample: pd.DataFrame
) -> list[dict]:
    """Return a sorted list of ``{feature, importance}`` dicts.

    Works for both tree-based models (``feature_importances_``) and linear
    models (``abs(coef_)``).  Returns ``[]`` if extraction fails.
    """
    try:
        model = pipeline.named_steps["model"]
        pre = pipeline.named_steps["pre"]
        feature_names = list(pre.get_feature_names_out())

        importances: np.ndarray | None = getattr(model, "feature_importances_", None)
        if importances is None:
            coef = getattr(model, "coef_", None)
            if coef is not None:
                importances = np.abs(np.asarray(coef).ravel())

        if importances is None or len(importances) != len(feature_names):
            return []

        pairs = sorted(
            zip(feature_names, importances.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )
        return [{"feature": n, "importance": round(v, 6)} for n, v in pairs]
    except Exception:
        logger.debug("Feature importance extraction failed", exc_info=True)
        return []
