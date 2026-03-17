from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.ingestion.alerts import ALERT_SCHEMA_CHANGE, AlertManager
from app.ingestion.detectors.schema_change import SchemaChangeDetector
from app.ingestion.models import IngestionSource


@dataclass
class CanaryResult:
    source_id: int
    is_schema_drift: bool
    mismatch_fraction: float
    paused_aggressive_parse: bool


def run_canary_for_source(
    db: Session,
    *,
    source: IngestionSource,
    payload: bytes,
    content_type: str,
    threshold: float,
    alert_manager: Optional[AlertManager] = None,
) -> CanaryResult:
    detector = SchemaChangeDetector(threshold=threshold, source_config=source.config_json or {})
    if "json" in content_type.lower():
        import json

        try:
            parsed = json.loads(payload)
        except Exception:
            parsed = {}
        result = detector.check_json(parsed, source.schema_baseline)
    else:
        result = detector.check_html(payload, source.schema_baseline)

    paused = False
    if result.new_snapshot is not None:
        source.schema_baseline = result.new_snapshot

    if result.is_changed:
        cfg = dict(source.config_json or {})
        cfg["aggressive_parsing_paused"] = True
        cfg["last_schema_drift_fraction"] = result.mismatch_fraction
        source.config_json = cfg
        paused = True
        if alert_manager:
            alert_manager.fire(
                source,
                ALERT_SCHEMA_CHANGE,
                details={
                    "mismatch_fraction": result.mismatch_fraction,
                    "details": result.details,
                    "canary": True,
                },
            )

    db.flush()
    return CanaryResult(
        source_id=source.id,
        is_schema_drift=result.is_changed,
        mismatch_fraction=result.mismatch_fraction,
        paused_aggressive_parse=paused,
    )
