"""Feature engineering for the ML duration-prediction module.

Extracts a flat, ML-ready feature vector from a ``Case`` ORM object plus its
relational context (parties, hearings, adjournments).

Responsibilities
----------------
* Define the authoritative feature schema (column groups used by both
  ``train.py`` and ``predict.py``).
* Handle missing / null values at every step — database rows are messy.
* Compute cyclical encoding for calendar month.
* Estimate court-level historical adjournment rate and backlog proxy.
* Detect politician and corruption-keyword flags.

All heavy SQLAlchemy imports are deferred to method bodies so that this
module can be imported in isolation (e.g. in unit tests) without a live DB.
"""
from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature schema — canonical column lists consumed by train.py / predict.py
# ---------------------------------------------------------------------------

#: Low-cardinality categorical columns — one-hot encoded.
CATEGORICAL_FEATURES: list[str] = ["court_level", "state", "case_type"]

#: Continuous / ordinal numeric columns — standard-scaled.
NUMERIC_FEATURES: list[str] = [
    "court_id",
    "filing_year",
    "filing_month",
    "number_of_parties",
    "politician_flag",
    "corruption_keywords_flag",
    "case_age_current_days",
    "historical_adj_rate",
    "backlog_at_filing",
    "log_backlog",
    "filing_month_sin",
    "filing_month_cos",
]

#: High-cardinality identifiers — passed through as numerics; HistGBT handles
#: them natively without bespoke target-encoding.
HIGH_CARDINALITY_FEATURES: list[str] = ["judge_id"]

#: All feature columns in the order expected by the sklearn ColumnTransformer.
ALL_FEATURES: list[str] = CATEGORICAL_FEATURES + NUMERIC_FEATURES + HIGH_CARDINALITY_FEATURES

# ---------------------------------------------------------------------------
# Domain keyword sets
# ---------------------------------------------------------------------------

_CORRUPTION_KEYWORDS: frozenset[str] = frozenset(
    {
        "bribery",
        "corruption",
        "scam",
        "fraud",
        "embezzlement",
        "disproportionate",
        "dacoit",
        "dacoity",
        "hawala",
        "benami",
        "misappropriation",
        "kickback",
        "forgery",
        "cheating",
    }
)

_POLITICIAN_ROLES: frozenset[str] = frozenset(
    {
        "mla",
        "mp",
        "minister",
        "chief minister",
        "cm",
        "governor",
        "councillor",
        "sarpanch",
        "pradhan",
        "alderman",
        "member of parliament",
        "member of legislative assembly",
    }
)

# ---------------------------------------------------------------------------
# CaseFeatures dataclass
# ---------------------------------------------------------------------------


@dataclass
class CaseFeatures:
    """Flat feature vector for a single case.

    All fields use Python primitives so the dataclass serialises cleanly
    to a dict that can be passed directly to a pandas DataFrame constructor.
    ``None`` is allowed only for ``judge_id`` (high-cardinality optional FK).
    """

    # Categorical
    court_level: str
    state: str
    case_type: str

    # Numeric identifiers / counts
    court_id: int
    filing_year: int
    filing_month: int
    number_of_parties: int

    # Binary flags
    politician_flag: int  # 0 or 1
    corruption_keywords_flag: int  # 0 or 1

    # Continuous
    case_age_current_days: float
    historical_adj_rate: float  # fraction in [0, 1]
    backlog_at_filing: float  # proxy count
    log_backlog: float  # log1p(backlog_at_filing)

    # Cyclical month encoding
    filing_month_sin: float
    filing_month_cos: float

    # High-cardinality optional
    judge_id: Optional[int]

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict (suitable as a DataFrame row)."""
        return asdict(self)


# ---------------------------------------------------------------------------
# FeatureExtractor
# ---------------------------------------------------------------------------


class FeatureExtractor:
    """Stateless extractor — safe to instantiate once and reuse."""

    def extract(self, case: Any, db: Session) -> CaseFeatures:
        """Return a :class:`CaseFeatures` for *case*.

        Parameters
        ----------
        case:
            A SQLAlchemy ``Case`` ORM instance.
        db:
            An active database session used for aggregate queries.

        Returns
        -------
        CaseFeatures
            Never raises; missing column values fall back to safe defaults.
        """
        filing_date: Optional[date] = getattr(case, "filing_date", None)
        today = date.today()

        filing_year = filing_date.year if filing_date else today.year
        filing_month = filing_date.month if filing_date else today.month
        case_age = float((today - filing_date).days) if filing_date else 0.0

        month_rad = (2.0 * math.pi * filing_month) / 12.0
        filing_month_sin = math.sin(month_rad)
        filing_month_cos = math.cos(month_rad)

        num_parties = _count_parties(case.id, db)
        politician_flag = _check_politician_flag(case, db)
        corruption_flag = _check_corruption_flag(case)
        adj_rate = _compute_court_adj_rate(case.court_id, db)
        backlog = float(_estimate_backlog(case.court_id, filing_date, db))
        log_backlog = math.log1p(backlog)
        judge_id = _get_recent_judge_id(case.id, db)

        return CaseFeatures(
            court_level=case.court_level or "unknown",
            state=case.state or "unknown",
            case_type=case.case_type or "unknown",
            court_id=int(case.court_id or 0),
            filing_year=filing_year,
            filing_month=filing_month,
            number_of_parties=num_parties,
            politician_flag=politician_flag,
            corruption_keywords_flag=corruption_flag,
            case_age_current_days=case_age,
            historical_adj_rate=adj_rate,
            backlog_at_filing=backlog,
            log_backlog=log_backlog,
            filing_month_sin=filing_month_sin,
            filing_month_cos=filing_month_cos,
            judge_id=judge_id,
        )


# ---------------------------------------------------------------------------
# Private helper functions
# ---------------------------------------------------------------------------


def _count_parties(case_id: int, db: Session) -> int:
    from app.models.entities import CasePartyLink

    return (
        db.query(CasePartyLink)
        .filter(CasePartyLink.case_id == case_id)
        .count()
    )


def _check_politician_flag(case: Any, db: Session) -> int:
    """Return 1 if any linked party is a public official with a politician role."""
    from app.models.entities import CasePartyLink, PublicOfficial

    linked = (
        db.query(PublicOfficial.role)
        .join(CasePartyLink, CasePartyLink.official_id == PublicOfficial.id)
        .filter(CasePartyLink.case_id == case.id)
        .all()
    )
    for (role,) in linked:
        if role and role.strip().lower() in _POLITICIAN_ROLES:
            return 1
    return 0


def _check_corruption_flag(case: Any) -> int:
    """Return 1 if corruption-related keywords appear in the case metadata."""
    text = " ".join(
        filter(
            None,
            [
                str(case.case_type or ""),
                str(case.case_number or ""),
                str(case.source_fields or {}),
            ],
        )
    ).lower()
    for kw in _CORRUPTION_KEYWORDS:
        if kw in text:
            return 1
    return 0


def _compute_court_adj_rate(court_id: int, db: Session) -> float:
    """Fraction of hearings at *court_id* that resulted in adjournment."""
    from app.models.entities import Adjournment, Case as CaseModel

    total = (
        db.query(Adjournment)
        .join(CaseModel, CaseModel.id == Adjournment.case_id)
        .filter(CaseModel.court_id == court_id)
        .count()
    )
    if total == 0:
        return 0.0
    adj = (
        db.query(Adjournment)
        .join(CaseModel, CaseModel.id == Adjournment.case_id)
        .filter(CaseModel.court_id == court_id, Adjournment.is_adjournment.is_(True))
        .count()
    )
    return round(adj / total, 4)


def _estimate_backlog(
    court_id: int, filing_date: Optional[date], db: Session
) -> int:
    """Count active cases filed at *court_id* in the 90 days before *filing_date*.

    This is a proxy for how busy the court was at the time of filing.
    Returns 0 when *filing_date* is unknown.
    """
    from datetime import timedelta

    from app.models.entities import Case as CaseModel

    if not filing_date:
        return 0
    lookback = filing_date - timedelta(days=90)
    return (
        db.query(CaseModel)
        .filter(
            CaseModel.court_id == court_id,
            CaseModel.filing_date >= lookback,
            CaseModel.filing_date <= filing_date,
            CaseModel.is_deleted.is_(False),
        )
        .count()
    )


def _get_recent_judge_id(case_id: int, db: Session) -> Optional[int]:
    """Return the judge_id from the most recent hearing of *case_id*, or None."""
    from app.models.entities import Hearing

    row = (
        db.query(Hearing.judge_id)
        .filter(Hearing.case_id == case_id, Hearing.judge_id.isnot(None))
        .order_by(Hearing.date.desc())
        .first()
    )
    return row[0] if row else None
