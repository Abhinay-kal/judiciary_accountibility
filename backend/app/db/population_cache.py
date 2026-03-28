"""In-memory and database-backed cache for population baseline metrics.

The PopulationCache manages the baseline metrics computed from all resolved cases.
It provides:
- Reading baseline from cache (fast)
- Invalidation and recalculation
- Persistence in the database for cross-session availability
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, Float, Integer, JSON, String, DateTime, create_engine
from sqlalchemy.orm import Session, declarative_base
from sqlalchemy.pool import NullPool

Base = declarative_base()


class PopulationBaselineRecord(Base):
    """Database record for cached population baseline metrics."""

    __tablename__ = "population_baseline_cache"

    id = Column(Integer, primary_key=True)
    density_mean = Column(Float, nullable=False)
    density_std = Column(Float, nullable=False)
    party_score_mean = Column(Float, nullable=False)
    party_score_std = Column(Float, nullable=False)
    dormancy_cv_mean = Column(Float, nullable=False)
    dormancy_cv_std = Column(Float, nullable=False)
    bench_hunting_mean = Column(Float, nullable=False)
    bench_hunting_std = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    calculation_date = Column(DateTime, nullable=False)
    cache_version = Column(String(10), default="1.0")
    metadata_ = Column(JSON, nullable=True)

    def __repr__(self):
        return (
            f"<PopulationBaseline sample_size={self.sample_size} "
            f"calculated={self.calculation_date}>"
        )


# In-memory cache for fast access
_BASELINE_CACHE: Optional[object] = None
_CACHE_TIMESTAMP: Optional[datetime] = None
_CACHE_TTL_SECONDS = 3600  # 1 hour


class PopulationCache:
    """Manages caching of population baseline metrics.

    This class provides a two-level cache:
    1. In-memory cache (fast, per-process)
    2. Database cache (persistent, cross-process)

    The in-memory cache is invalidated after _CACHE_TTL_SECONDS or on explicit set.
    """

    def __init__(self, db: Session):
        """Initialize cache manager.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_baseline_metrics(self) -> Optional[object]:
        """Get cached baseline metrics (fast path via in-memory cache).

        Returns:
            BaselineMetrics dataclass or None if not available
        """
        global _BASELINE_CACHE, _CACHE_TIMESTAMP

        # Check in-memory cache validity
        if _BASELINE_CACHE is not None and _CACHE_TIMESTAMP is not None:
            age_seconds = (datetime.utcnow() - _CACHE_TIMESTAMP).total_seconds()
            if age_seconds < _CACHE_TTL_SECONDS:
                return _BASELINE_CACHE

        # Fall through to database cache
        return self._get_baseline_from_db()

    def set_baseline_metrics(self, baseline: object) -> None:
        """Cache baseline metrics in memory and database.

        Args:
            baseline: BaselineMetrics dataclass to cache
        """
        global _BASELINE_CACHE, _CACHE_TIMESTAMP

        # Update in-memory cache
        _BASELINE_CACHE = baseline
        _CACHE_TIMESTAMP = datetime.utcnow()

        # Persist to database
        self._save_baseline_to_db(baseline)

    def invalidate(self) -> None:
        """Invalidate all cached baseline metrics."""
        global _BASELINE_CACHE, _CACHE_TIMESTAMP

        _BASELINE_CACHE = None
        _CACHE_TIMESTAMP = None

        # Clear database cache
        try:
            self.db.query(PopulationBaselineRecord).delete()
            self.db.commit()
        except Exception:
            pass  # Ignore errors during invalidation

    def _get_baseline_from_db(self) -> Optional[object]:
        """Retrieve baseline from database cache.

        Returns:
            BaselineMetrics dataclass or None
        """
        try:
            record = (
                self.db.query(PopulationBaselineRecord)
                .order_by(PopulationBaselineRecord.calculation_date.desc())
                .first()
            )

            if record is None:
                return None

            # Convert database record to dataclass
            from app.services.delay_detection_phase3 import BaselineMetrics

            baseline = BaselineMetrics(
                density_mean=record.density_mean,
                density_std=record.density_std,
                party_score_mean=record.party_score_mean,
                party_score_std=record.party_score_std,
                dormancy_cv_mean=record.dormancy_cv_mean,
                dormancy_cv_std=record.dormancy_cv_std,
                bench_hunting_mean=record.bench_hunting_mean,
                bench_hunting_std=record.bench_hunting_std,
                sample_size=record.sample_size,
                calculation_date=record.calculation_date,
            )

            # Update in-memory cache
            global _BASELINE_CACHE, _CACHE_TIMESTAMP
            _BASELINE_CACHE = baseline
            _CACHE_TIMESTAMP = datetime.utcnow()

            return baseline

        except Exception:
            return None

    def _save_baseline_to_db(self, baseline: object) -> None:
        """Save baseline metrics to database.

        Args:
            baseline: BaselineMetrics dataclass to persist
        """
        try:
            # Use separate session to avoid corrupting the calling session
            from app.db.session import SessionLocal
            
            separate_db = SessionLocal()
            try:
                # Delete old records
                separate_db.query(PopulationBaselineRecord).delete()

                # Create and insert new record
                record = PopulationBaselineRecord(
                    density_mean=baseline.density_mean,
                    density_std=baseline.density_std,
                    party_score_mean=baseline.party_score_mean,
                    party_score_std=baseline.party_score_std,
                    dormancy_cv_mean=baseline.dormancy_cv_mean,
                    dormancy_cv_std=baseline.dormancy_cv_std,
                    bench_hunting_mean=baseline.bench_hunting_mean,  
                    bench_hunting_std=baseline.bench_hunting_std,
                    sample_size=baseline.sample_size,
                    calculation_date=baseline.calculation_date,
                    cache_version="1.0",
                    metadata_={
                        "cached_at": datetime.utcnow().isoformat(),
                        "ttl_seconds": _CACHE_TTL_SECONDS,
                    },
                )

                separate_db.add(record)
                separate_db.commit()
                
            finally:
                separate_db.close()

        except Exception:
            # Ignore persistence errors - in-memory cache still works
            pass


def create_population_cache_table(engine) -> None:
    """Create the population_baseline_cache table if it doesn't exist.

    Args:
        engine: SQLAlchemy engine
    """
    try:
        Base.metadata.create_all(engine)
    except Exception:
        # Table may already exist or database may be locked
        pass
