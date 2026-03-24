from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.ml.config import get_ml_settings
from app.models import Hearing, HearingOutcomeType, Order

_TEXT_COLUMN = "raw_outcome_text"
_META_COLUMNS = ["source_type", "parser_version", "presence_of_order_pdf"]


@dataclass
class OutcomeMLPrediction:
    outcome_type: HearingOutcomeType
    confidence: float
    probabilities: dict[str, float]


class OutcomeMLParser:
    def __init__(self) -> None:
        self.settings = get_ml_settings()

    def _artifact_path(self) -> Path:
        return Path(self.settings.ml_artifacts_dir) / self.settings.ml_parser_artifact_name

    def _report_path(self) -> Path:
        return Path(self.settings.ml_artifacts_dir) / self.settings.ml_parser_report_name

    def _load_model(self):
        artifact = self._artifact_path()
        if not artifact.exists():
            return None
        return joblib.load(artifact)

    def predict(
        self,
        *,
        raw_outcome_text: str,
        source_type: str,
        parser_version: str,
        presence_of_order_pdf: bool,
    ) -> OutcomeMLPrediction | None:
        model = self._load_model()
        if model is None:
            return None
        frame = pd.DataFrame(
            [
                {
                    _TEXT_COLUMN: raw_outcome_text or "",
                    "source_type": source_type,
                    "parser_version": parser_version,
                    "presence_of_order_pdf": str(bool(presence_of_order_pdf)).lower(),
                }
            ]
        )
        probabilities = model.predict_proba(frame)[0]
        classes = list(model.named_steps["model"].classes_)
        best_index = int(probabilities.argmax())
        return OutcomeMLPrediction(
            outcome_type=HearingOutcomeType(classes[best_index]),
            confidence=float(probabilities[best_index]),
            probabilities={classes[idx]: float(probabilities[idx]) for idx in range(len(classes))},
        )

    def train_from_annotations(self, db_session: Any) -> dict[str, Any]:
        records = []
        hearings = (
            db_session.query(Hearing)
            .filter(Hearing.annotated_by.isnot(None), Hearing.outcome_type.isnot(None), Hearing.is_deleted.is_(False))
            .all()
        )
        for hearing in hearings:
            has_order_pdf = (
                db_session.query(Order)
                .filter(Order.case_id == hearing.case_id, Order.order_date == hearing.date, Order.is_deleted.is_(False))
                .first()
                is not None
            )
            records.append(
                {
                    _TEXT_COLUMN: hearing.raw_outcome_text or hearing.outcome_text or "",
                    "source_type": hearing.source,
                    "parser_version": hearing.parser_version or "unknown",
                    "presence_of_order_pdf": str(has_order_pdf).lower(),
                    "label": hearing.outcome_type.value,
                }
            )

        artifacts_dir = Path(self.settings.ml_artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        if len(records) < 8:
            report = {"trained": False, "reason": "insufficient_annotations", "rows": len(records)}
            self._report_path().write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report

        df = pd.DataFrame(records)
        train_df, test_df = train_test_split(df, test_size=0.25, random_state=42, stratify=df["label"])
        pipeline = _build_pipeline()
        pipeline.fit(train_df.drop(columns=["label"]), train_df["label"])
        predictions = pipeline.predict(test_df.drop(columns=["label"]))
        report = classification_report(test_df["label"], predictions, output_dict=True, zero_division=0)
        top_features = _top_features(pipeline)

        joblib.dump(pipeline, self._artifact_path())
        evaluation_payload = {
            "trained": True,
            "rows": len(records),
            "labels": sorted(df["label"].unique().tolist()),
            "classification_report": report,
            "top_features": top_features,
        }
        self._report_path().write_text(json.dumps(evaluation_payload, indent=2), encoding="utf-8")
        return evaluation_payload


def _build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("text", TfidfVectorizer(ngram_range=(1, 2), min_df=1), _TEXT_COLUMN),
            ("meta", OneHotEncoder(handle_unknown="ignore"), _META_COLUMNS),
        ]
    )
    return Pipeline(
        steps=[
            ("pre", preprocessor),
            ("model", LogisticRegression(max_iter=2000)),
        ]
    )


def _top_features(pipeline: Pipeline, limit: int = 10) -> list[dict[str, float]]:
    model = pipeline.named_steps["model"]
    pre = pipeline.named_steps["pre"]
    feature_names = list(pre.get_feature_names_out())
    importances = model.coef_
    weights = importances.max(axis=0)
    top_indices = weights.argsort()[-limit:][::-1]
    return [{"feature": feature_names[index], "importance": float(weights[index])} for index in top_indices]