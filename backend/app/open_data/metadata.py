from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.open_data.catalog import DatasetCatalogEntry


@dataclass(slots=True)
class DataQualityIndicators:
    completeness: float
    coverage: float
    confidence_level: float
    missing_data_rate: float


def compute_quality_indicators(rows: list[dict], required_fields: list[str]) -> DataQualityIndicators:
    if not rows:
        return DataQualityIndicators(
            completeness=0.0,
            coverage=0.0,
            confidence_level=0.0,
            missing_data_rate=1.0,
        )

    total_cells = len(rows) * max(len(required_fields), 1)
    missing = 0
    confidence_values: list[float] = []

    for row in rows:
        for field in required_fields:
            value = row.get(field)
            if value is None or value == "":
                missing += 1
        if row.get("outcome_confidence") is not None:
            confidence_values.append(float(row["outcome_confidence"]))
        elif row.get("importance_confidence") is not None:
            confidence_values.append(float(row["importance_confidence"]))

    completeness = max(0.0, min(1.0, 1.0 - (missing / total_cells)))
    coverage = min(1.0, len(rows) / max(len(rows), 1))
    confidence_level = sum(confidence_values) / len(confidence_values) if confidence_values else 0.75
    missing_data_rate = 1.0 - completeness

    return DataQualityIndicators(
        completeness=round(completeness, 4),
        coverage=round(coverage, 4),
        confidence_level=round(confidence_level, 4),
        missing_data_rate=round(missing_data_rate, 4),
    )


def build_metadata(entry: DatasetCatalogEntry, version: str, row_count: int, quality: DataQualityIndicators) -> dict:
    return {
        "dataset_id": entry.dataset_id,
        "name": entry.name,
        "description": entry.description,
        "schema": entry.schema,
        "version": version,
        "license": entry.license,
        "permitted_uses": entry.permitted_uses,
        "recommended_citation": entry.recommended_citation,
        "update_frequency": entry.update_frequency.value,
        "privacy_classification": entry.privacy_classification.value,
        "field_definitions": [
            {
                "name": field.name,
                "type": field.field_type,
                "description": field.description,
                "nullable": field.nullable,
                "example": field.example,
            }
            for field in entry.fields
        ],
        "data_dictionary": {field.name: field.description for field in entry.fields},
        "methodology_notes": entry.methodology_notes,
        "known_limitations": entry.known_limitations,
        "provenance_summary": entry.provenance_summary,
        "data_quality_notes": entry.data_quality_notes,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "record_count": row_count,
        "quality_indicators": {
            "completeness": quality.completeness,
            "coverage": quality.coverage,
            "confidence_level": quality.confidence_level,
            "missing_data_rate": quality.missing_data_rate,
        },
    }
