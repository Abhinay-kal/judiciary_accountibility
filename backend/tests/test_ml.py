"""Unit tests for the ML module.

Tests are organised by sub-module and cover:
- evaluation.py   — metric computation and time-based split
- features.py     — CaseFeatures dataclass, corruption flag, feature extractor
                     with missing data (filing_date=None)
- outliers.py     — delay ratio computation and severity classification
- predict.py      — graceful degradation when artifacts are absent
- train.py        — small-dataset fallback to baseline-only model

All tests are pure Python — no live database or trained model is required.
Heavy SQLAlchemy and sklearn imports are controlled via patching / tmp_path.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# evaluation.py
# ---------------------------------------------------------------------------


def test_compute_metrics_perfect():
    from app.ml.evaluation import compute_metrics

    y = np.array([100.0, 200.0, 300.0])
    m = compute_metrics(y, y)
    assert m["mae"] == 0.0
    assert m["rmse"] == 0.0
    assert m["r2"] == 1.0
    assert m["median_ae"] == 0.0


def test_compute_metrics_nonzero():
    from app.ml.evaluation import compute_metrics

    y_true = np.array([100.0, 200.0, 300.0])
    y_pred = np.array([120.0, 180.0, 310.0])
    m = compute_metrics(y_true, y_pred)
    assert m["mae"] > 0
    assert m["rmse"] > 0
    assert "r2" in m and "median_ae" in m


def test_time_based_split_proportions():
    from app.ml.evaluation import time_based_split

    df = pd.DataFrame(
        {
            "filing_date": pd.date_range("2015-01-01", periods=100, freq="ME"),
            "x": range(100),
        }
    )
    train, val = time_based_split(df, date_col="filing_date", train_fraction=0.8)
    assert len(train) == 80
    assert len(val) == 20


def test_time_based_split_chronological_ordering():
    from app.ml.evaluation import time_based_split

    df = pd.DataFrame(
        {
            "filing_date": pd.date_range("2010-01-01", periods=50, freq="ME"),
            "y": range(50),
        }
    )
    train, val = time_based_split(df, date_col="filing_date")
    assert train["filing_date"].max() <= val["filing_date"].min()


# ---------------------------------------------------------------------------
# outliers.py
# ---------------------------------------------------------------------------


def test_compute_delay_ratio_normal():
    from app.ml.outliers import compute_delay_ratio

    ratio = compute_delay_ratio(450.0, 300.0)
    assert ratio == pytest.approx(1.5, rel=1e-3)


def test_compute_delay_ratio_zero_denominator():
    from app.ml.outliers import compute_delay_ratio

    assert compute_delay_ratio(100.0, 0.0) == 0.0


def test_classify_none():
    from app.ml.outliers import classify_delay_severity

    assert classify_delay_severity(1.0) is None
    assert classify_delay_severity(1.49) is None


def test_classify_moderate():
    from app.ml.outliers import classify_delay_severity

    assert classify_delay_severity(1.5) == "moderate"
    assert classify_delay_severity(1.9) == "moderate"


def test_classify_severe():
    from app.ml.outliers import classify_delay_severity

    assert classify_delay_severity(2.0) == "severe"
    assert classify_delay_severity(2.9) == "severe"


def test_classify_extreme():
    from app.ml.outliers import classify_delay_severity

    assert classify_delay_severity(3.0) == "extreme"
    assert classify_delay_severity(10.0) == "extreme"


# ---------------------------------------------------------------------------
# features.py
# ---------------------------------------------------------------------------


def test_case_features_to_dict_roundtrip():
    from app.ml.features import CaseFeatures

    f = CaseFeatures(
        court_level="district",
        state="Maharashtra",
        case_type="Civil",
        court_id=7,
        filing_year=2019,
        filing_month=6,
        number_of_parties=3,
        politician_flag=0,
        corruption_keywords_flag=1,
        case_age_current_days=730.0,
        historical_adj_rate=0.4,
        backlog_at_filing=25.0,
        log_backlog=3.258,
        filing_month_sin=0.866,
        filing_month_cos=0.5,
        judge_id=None,
    )
    d = f.to_dict()
    assert d["court_level"] == "district"
    assert d["corruption_keywords_flag"] == 1
    assert d["judge_id"] is None
    assert len(d) == 16  # sanity-check total fields


def test_corruption_flag_detected():
    from app.ml.features import _check_corruption_flag

    case = MagicMock()
    case.case_type = "State vs. accused in corruption scam"
    case.case_number = "CR/001/2021"
    case.source_fields = {}
    assert _check_corruption_flag(case) == 1


def test_corruption_flag_absent():
    from app.ml.features import _check_corruption_flag

    case = MagicMock()
    case.case_type = "Matrimonial Dispute"
    case.case_number = "HMA/999/2022"
    case.source_fields = {}
    assert _check_corruption_flag(case) == 0


def test_feature_extractor_handles_missing_filing_date():
    """FeatureExtractor must not raise when filing_date is None."""
    from app.ml.features import FeatureExtractor

    extractor = FeatureExtractor()

    case = MagicMock()
    case.id = 55
    case.filing_date = None
    case.court_level = "district"
    case.state = "Delhi"
    case.court_id = 3
    case.case_type = "Criminal"
    case.case_number = "SC/555"
    case.source_fields = {}

    db = MagicMock()
    # Simulate all count() / first() queries returning 0 / None
    db.query.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.join.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    feats = extractor.extract(case, db)
    assert feats.case_age_current_days == 0.0
    assert feats.filing_year >= 2000
    assert feats.judge_id is None


def test_feature_extractor_cyclical_month_encoding():
    """Cyclical month encodings should be in [-1, 1] and month 1 == month 13."""
    import math
    from datetime import date

    from app.ml.features import FeatureExtractor

    extractor = FeatureExtractor()

    def _make_case(month: int) -> MagicMock:
        c = MagicMock()
        c.id = month
        c.filing_date = date(2021, month, 15)
        c.court_level = "high"
        c.state = "Karnataka"
        c.court_id = 1
        c.case_type = "Civil"
        c.case_number = f"X/{month}"
        c.source_fields = {}
        return c

    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.join.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    feats_jan = extractor.extract(_make_case(1), db)
    feats_dec = extractor.extract(_make_case(12), db)

    # Both sin and cos should be in [-1, 1]
    assert -1 <= feats_jan.filing_month_sin <= 1
    assert -1 <= feats_jan.filing_month_cos <= 1
    # January and the next January would have the same encoding
    jan_rad = (2 * math.pi * 1) / 12
    assert feats_jan.filing_month_sin == pytest.approx(math.sin(jan_rad), abs=1e-6)


# ---------------------------------------------------------------------------
# predict.py — graceful degradation
# ---------------------------------------------------------------------------


def test_predictor_unavailable_when_no_artifacts(tmp_path):
    """CaseDurationPredictor returns PREDICTION_UNAVAILABLE when artifacts are missing."""
    from app.ml.predict import CaseDurationPredictor, PREDICTION_UNAVAILABLE

    p = CaseDurationPredictor()
    p.settings = MagicMock()
    p.settings.ml_artifacts_dir = str(tmp_path)

    result = p.predict({"court_level": "district", "case_type": "Civil"})
    assert result is PREDICTION_UNAVAILABLE
    assert result.predicted_days == -1.0
    assert result.model_version == "unavailable"


def test_prediction_result_serialises():
    from app.ml.predict import PredictionResult

    r = PredictionResult(
        predicted_days=600.0,
        lower_bound=400.0,
        upper_bound=900.0,
        confidence=0.75,
        model_version="v20260317",
        top_features=[{"feature": "court_level", "importance": 0.42}],
    )
    d = r.to_dict()
    assert d["predicted_days"] == 600.0
    assert d["confidence"] == 0.75
    assert len(d["top_features"]) == 1


def test_predictor_prepare_dataframe_imputation():
    """Missing categorical columns must be filled with 'unknown'; numerics with 0."""
    from app.ml.predict import CaseDurationPredictor

    p = CaseDurationPredictor()
    df = p._prepare_dataframe({"court_level": None, "filing_year": None})
    assert df["court_level"].iloc[0] == "unknown"
    assert df["filing_year"].iloc[0] == 0


# ---------------------------------------------------------------------------
# train.py — insufficient-data fallback
# ---------------------------------------------------------------------------


def _make_tiny_df(n: int = 10) -> pd.DataFrame:
    """Return a minimal feature DataFrame with *n* rows for testing."""
    import math
    from datetime import date

    from app.ml.features import ALL_FEATURES

    rows = []
    for i in range(n):
        month = (i % 12) + 1
        row: dict = {
            "duration_days": 200 + i * 10,
            "filing_date": date(2020, month, 1),
            "case_id": i,
            "court_level": "district",
            "state": "MH",
            "case_type": "Civil",
            "court_id": 1,
            "filing_year": 2020,
            "filing_month": month,
            "number_of_parties": 2,
            "politician_flag": 0,
            "corruption_keywords_flag": 0,
            "case_age_current_days": 365.0,
            "judge_id": None,
            "historical_adj_rate": 0.3,
            "backlog_at_filing": 40.0,
            "log_backlog": math.log1p(40),
            "filing_month_sin": math.sin(2 * math.pi * month / 12),
            "filing_month_cos": math.cos(2 * math.pi * month / 12),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def test_train_falls_back_to_baseline_insufficient_data(tmp_path):
    """ModelTrainer saves a baseline-only model when data < ml_min_cases."""
    from app.ml.train import ModelTrainer

    trainer = ModelTrainer()
    trainer.settings = MagicMock()
    trainer.settings.ml_min_cases = 500
    trainer.settings.ml_artifacts_dir = str(tmp_path)
    trainer.settings.ml_model_version_prefix = "v"
    trainer.settings.ml_quantile_lower = 0.1
    trainer.settings.ml_quantile_upper = 0.9

    with patch("app.ml.train.build_training_dataset", return_value=_make_tiny_df(10)):
        result = trainer.train(MagicMock())

    assert result["best_model"] == "baseline"
    assert result.get("insufficient_data") is True
    assert (tmp_path / "duration_model.pkl").exists()
    assert (tmp_path / "metadata.json").exists()


def test_train_falls_back_to_baseline_empty_dataset(tmp_path):
    """ModelTrainer saves a baseline-only model when the dataset is empty."""
    from app.ml.train import ModelTrainer

    trainer = ModelTrainer()
    trainer.settings = MagicMock()
    trainer.settings.ml_min_cases = 500
    trainer.settings.ml_artifacts_dir = str(tmp_path)
    trainer.settings.ml_model_version_prefix = "v"
    trainer.settings.ml_quantile_lower = 0.1
    trainer.settings.ml_quantile_upper = 0.9

    with patch("app.ml.train.build_training_dataset", return_value=pd.DataFrame()):
        result = trainer.train(MagicMock())

    assert result["best_model"] == "baseline"
    assert result.get("insufficient_data") is True


def test_baseline_model_fit_and_predict():
    from app.ml.train import BaselineMedianModel

    df = _make_tiny_df(20)
    model = BaselineMedianModel()
    model.fit(df)

    preds = model.predict(df)
    assert len(preds) == len(df)
    assert all(p > 0 for p in preds)


def test_baseline_model_unknown_group_uses_global_median():
    from app.ml.train import BaselineMedianModel

    df = _make_tiny_df(10)
    model = BaselineMedianModel().fit(df)

    unknown_row = pd.DataFrame(
        [{"court_level": "supreme", "case_type": "Constitutional"}]
    )
    pred = model.predict(unknown_row)
    assert pred[0] == pytest.approx(model.global_median, rel=1e-6)


# ---------------------------------------------------------------------------
# train.py — full pipeline with sufficient synthetic data
# ---------------------------------------------------------------------------


def test_train_full_pipeline_with_synthetic_data(tmp_path):
    """ModelTrainer selects and saves a non-baseline model given enough data."""
    from app.ml.train import ModelTrainer

    trainer = ModelTrainer()
    trainer.settings = MagicMock()
    trainer.settings.ml_min_cases = 50  # low threshold for test speed
    trainer.settings.ml_artifacts_dir = str(tmp_path)
    trainer.settings.ml_model_version_prefix = "v"
    trainer.settings.ml_quantile_lower = 0.1
    trainer.settings.ml_quantile_upper = 0.9

    large_df = _make_tiny_df(200)  # 200 > 50

    with patch("app.ml.train.build_training_dataset", return_value=large_df):
        result = trainer.train(MagicMock())

    assert result["best_model"] in ("ridge", "hgbt_median")
    assert "metrics" in result
    assert (tmp_path / "duration_model.pkl").exists()
    assert (tmp_path / "lower_model.pkl").exists()
    assert (tmp_path / "upper_model.pkl").exists()
    assert (tmp_path / "metadata.json").exists()


# ---------------------------------------------------------------------------
# predict.py — end-to-end with saved artifact
# ---------------------------------------------------------------------------


def test_predictor_loads_and_predicts_after_training(tmp_path):
    """After training, the predictor should load artifacts and return real numbers."""
    from app.ml.predict import CaseDurationPredictor
    from app.ml.train import ModelTrainer

    # Train a small model
    trainer = ModelTrainer()
    trainer.settings = MagicMock()
    trainer.settings.ml_min_cases = 10
    trainer.settings.ml_artifacts_dir = str(tmp_path)
    trainer.settings.ml_model_version_prefix = "v"
    trainer.settings.ml_quantile_lower = 0.1
    trainer.settings.ml_quantile_upper = 0.9

    with patch("app.ml.train.build_training_dataset", return_value=_make_tiny_df(50)):
        trainer.train(MagicMock())

    # Now build a fresh predictor pointing at the same tmp_path
    predictor = CaseDurationPredictor()
    predictor.settings = MagicMock()
    predictor.settings.ml_artifacts_dir = str(tmp_path)
    assert predictor.load() is True

    result = predictor.predict(
        {
            "court_level": "district",
            "state": "MH",
            "case_type": "Civil",
            "court_id": 1,
            "filing_year": 2020,
            "filing_month": 3,
            "number_of_parties": 2,
            "politician_flag": 0,
            "corruption_keywords_flag": 0,
            "case_age_current_days": 365.0,
            "historical_adj_rate": 0.3,
            "backlog_at_filing": 40.0,
            "log_backlog": 3.7,
            "filing_month_sin": 0.5,
            "filing_month_cos": 0.866,
            "judge_id": None,
        }
    )
    assert result.predicted_days > 0
    assert result.lower_bound > 0
    assert result.upper_bound >= result.predicted_days
    assert 0.0 <= result.confidence <= 1.0
    assert result.model_version != "unavailable"
