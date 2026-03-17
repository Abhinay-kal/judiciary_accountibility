from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from app.core.config import get_settings
from app.models import JudgeRegistry
from app.services.judge_resolution import normalize_name


@dataclass
class JudgeMLSuggestion:
    judge_id: str
    score: float
    match_type: str


class JudgeMLMatcher:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._artifact_dir = Path("app/ml/artifacts")
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        self._artifact_path = self._artifact_dir / "judge_matcher.pkl"

    def train(self, db_session: Any) -> dict[str, Any]:
        registry_entries = db_session.query(JudgeRegistry).all()
        rows = [
            {
                "judge_id": entry.judge_id,
                "text": normalize_name(entry.canonical_name),
            }
            for entry in registry_entries
            if normalize_name(entry.canonical_name)
        ]
        if len(rows) < 5:
            return {"trained": False, "reason": "insufficient_registry_rows", "rows": len(rows)}

        frame = pd.DataFrame(rows)
        vectorizer = TfidfVectorizer(ngram_range=(1, 3), min_df=1)
        matrix = vectorizer.fit_transform(frame["text"])
        model = NearestNeighbors(metric="cosine")
        model.fit(matrix)
        artifact = {
            "judge_ids": frame["judge_id"].tolist(),
            "vectorizer": vectorizer,
            "model": model,
        }
        joblib.dump(artifact, self._artifact_path)
        return {"trained": True, "rows": len(rows), "artifact": str(self._artifact_path)}

    def suggest(self, raw_name: str, limit: int = 5) -> list[JudgeMLSuggestion]:
        if not self.settings.enable_judge_ml_matcher:
            return []
        if not self._artifact_path.exists():
            return []

        artifact = joblib.load(self._artifact_path)
        vectorizer = artifact["vectorizer"]
        model = artifact["model"]
        judge_ids = artifact["judge_ids"]

        normalized = normalize_name(raw_name)
        if not normalized:
            return []

        query = vectorizer.transform([normalized])
        distances, indices = model.kneighbors(query, n_neighbors=min(limit, len(judge_ids)))
        suggestions: list[JudgeMLSuggestion] = []
        for distance, index in zip(distances[0], indices[0]):
            confidence = max(0.0, min(1.0, 1.0 - float(distance))) * 0.75
            suggestions.append(
                JudgeMLSuggestion(
                    judge_id=judge_ids[int(index)],
                    score=confidence,
                    match_type="ML_MATCH",
                )
            )
        return suggestions
