from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CourtStatsCache(Base):
    __tablename__ = "court_stats"
    __table_args__ = (
        Index("idx_court_stats_court", "court_id"),
        Index("idx_court_stats_computed", "computed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    court_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    pending_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    disposed_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    backlog_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class JudgeStatsCache(Base):
    __tablename__ = "judge_stats"
    __table_args__ = (
        Index("idx_judge_stats_judge", "judge_id"),
        Index("idx_judge_stats_computed", "computed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    judge_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    hearing_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_outcome_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class StateMetricsCache(Base):
    __tablename__ = "state_metrics"
    __table_args__ = (
        Index("idx_state_metrics_state", "state"),
        Index("idx_state_metrics_computed", "computed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    pending_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_normalized_delay: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class CaseTypeMetricsCache(Base):
    __tablename__ = "case_type_metrics"
    __table_args__ = (
        Index("idx_case_type_metrics_type", "case_type"),
        Index("idx_case_type_metrics_computed", "computed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    pending_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_delay_percentile: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
