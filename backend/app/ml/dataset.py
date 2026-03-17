"""Dataset assembly from the application database.

:func:`build_training_dataset`
    Queries all *disposed* cases that have a recoverable disposal date and
    returns a :class:`pandas.DataFrame` ready for the training pipeline.
    Rows that fail feature extraction are logged and silently dropped.

:func:`build_inference_row`
    Extracts features for a single active case and returns a plain dict
    suitable for prediction.

Disposal date recovery strategy (in priority order):

1. ``source_fields`` field under common key names.
2. ``disposal_date`` attribute on the ORM object (if ever added to the model).
3. Falls back to ``updated_at`` **only** when ``status == 'disposed'`` — the
   last update timestamp is the best available proxy in that case.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.ml.features import FeatureExtractor

logger = logging.getLogger(__name__)

_extractor = FeatureExtractor()

# Keys checked in source_fields when looking for the disposal date.
_DISPOSAL_KEYS = (
    "disposal_date",
    "date_of_decision",
    "decision_date",
    "closed_date",
    "date_of_disposal",
    "judgement_date",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_training_dataset(db: Session) -> pd.DataFrame:
    """Return a feature DataFrame of all disposed cases with ground-truth labels.

    Only cases where **both** ``filing_date`` and a recoverable disposal date
    are present are included.  Cases with ``duration_days <= 0`` are dropped
    as likely data-entry errors.

    Returns an **empty DataFrame** (with no rows) if no qualifying cases are
    found — the caller is responsible for checking the result size.
    """
    from app.models.entities import Case

    cases = (
        db.query(Case)
        .filter(
            Case.status == "disposed",
            Case.filing_date.isnot(None),
            Case.is_deleted.is_(False),
        )
        .all()
    )

    rows: list[dict] = []
    for case in cases:
        disposal_date = _extract_disposal_date(case)
        if disposal_date is None:
            continue

        duration = (disposal_date - case.filing_date).days
        if duration <= 0:
            continue  # Data quality issue — skip rather than poison the model

        try:
            feats = _extractor.extract(case, db)
        except Exception:
            logger.debug(
                "Feature extraction failed for case %s — skipped from training set",
                case.id,
            )
            continue

        row = feats.to_dict()
        row["duration_days"] = duration
        row["filing_date"] = case.filing_date
        row["case_id"] = case.id
        rows.append(row)

    if not rows:
        logger.warning(
            "build_training_dataset: no disposed cases with valid features found"
        )
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    logger.info("Training dataset assembled: %d rows", len(df))
    return df


def build_inference_row(case: Any, db: Session) -> Optional[dict]:
    """Extract features for a single active case.

    Returns ``None`` if extraction fails for any reason, so callers can
    safely skip this row.
    """
    try:
        feats = _extractor.extract(case, db)
        row = feats.to_dict()
        row["case_id"] = case.id
        row["filing_date"] = case.filing_date
        return row
    except Exception:
        logger.exception(
            "build_inference_row: feature extraction failed for case %s", case.id
        )
        return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_disposal_date(case: Any) -> Optional[date]:
    """Best-effort extraction of disposal date from multiple possible sources."""
    from dateutil.parser import parse as _parse

    # 1. Explicit attribute (future-proofing if the schema gains this column)
    explicit = getattr(case, "disposal_date", None)
    if isinstance(explicit, date):
        return explicit

    # 2. source_fields JSON keys
    sf: dict = case.source_fields or {}
    for key in _DISPOSAL_KEYS:
        val = sf.get(key)
        if val:
            try:
                if isinstance(val, date):
                    return val
                return _parse(str(val)).date()
            except Exception:
                pass

    # 3. updated_at proxy — only for disposed cases.
    #    If the case was marked disposed, updated_at is a reasonable upper-bound.
    if case.status == "disposed" and case.updated_at:
        try:
            return case.updated_at.date()
        except Exception:
            pass

    return None
