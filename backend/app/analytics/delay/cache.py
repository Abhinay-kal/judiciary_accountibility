from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.cache import get_or_set_json
from app.models import DelayBaseline


def load_baselines_snapshot(db: Session, *, namespace_key: str = "latest") -> dict:
    def _producer() -> dict:
        rows = db.query(DelayBaseline).all()
        payload: dict[str, dict] = {}
        for row in rows:
            key = f"{row.baseline_level}|{row.court_id}|{row.state}|{row.case_type}"
            payload[key] = {
                "baseline_level": row.baseline_level,
                "court_id": row.court_id,
                "state": row.state,
                "case_type": row.case_type,
                "median_delay": row.median_delay,
                "p75_delay": row.p75_delay,
                "p90_delay": row.p90_delay,
                "iqr_delay": row.iqr_delay,
                "sample_size": row.sample_size,
                "computed_at": row.computed_at.isoformat() if row.computed_at else None,
            }
        return payload

    return get_or_set_json("delay_baselines", namespace_key, _producer, ttl_seconds=3600)
