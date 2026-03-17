from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampSoftDeleteMixin:
    """Reusable columns for auditability and soft deletion."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Court(TimestampSoftDeleteMixin, Base):
    __tablename__ = "courts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    level: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    cases: Mapped[list[Case]] = relationship(back_populates="court")


class Judge(TimestampSoftDeleteMixin, Base):
    __tablename__ = "judges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    court_id: Mapped[Optional[int]] = mapped_column(ForeignKey("courts.id"), nullable=True, index=True)

    hearings: Mapped[list[Hearing]] = relationship(back_populates="judge")


class Case(TimestampSoftDeleteMixin, Base):
    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("case_number", "court_id", name="uq_case_number_court"),
        Index("idx_cases_status_state", "status", "state"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_uid: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    cnr: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    case_number: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    court_id: Mapped[int] = mapped_column(ForeignKey("courts.id"), nullable=False, index=True)
    court_level: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    bench: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    judges_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    filing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_hearing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    case_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_source_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    court: Mapped[Court] = relationship(back_populates="cases")
    hearings: Mapped[list[Hearing]] = relationship(back_populates="case")
    adjournments: Mapped[list[Adjournment]] = relationship(back_populates="case")
    orders: Mapped[list[Order]] = relationship(back_populates="case")
    flags: Mapped[list[Flag]] = relationship(back_populates="case")
    parties: Mapped[list[CasePartyLink]] = relationship(back_populates="case")


class Hearing(TimestampSoftDeleteMixin, Base):
    __tablename__ = "hearings"
    __table_args__ = (Index("idx_hearing_case_date", "case_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    judge_id: Mapped[Optional[int]] = mapped_column(ForeignKey("judges.id"), nullable=True, index=True)
    listing_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    outcome_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)

    case: Mapped[Case] = relationship(back_populates="hearings")
    judge: Mapped[Optional[Judge]] = relationship(back_populates="hearings")


class Adjournment(TimestampSoftDeleteMixin, Base):
    __tablename__ = "adjournments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    hearing_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hearings.id"), nullable=True, index=True)
    is_adjournment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    reason_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)

    case: Mapped[Case] = relationship(back_populates="adjournments")


class Order(TimestampSoftDeleteMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    order_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    order_link: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    case: Mapped[Case] = relationship(back_populates="orders")


class Flag(TimestampSoftDeleteMixin, Base):
    __tablename__ = "flags"
    __table_args__ = (Index("idx_flags_case_type_active", "case_id", "flag_type", "is_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    flag_type: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    case: Mapped[Case] = relationship(back_populates="flags")


class PublicOfficial(TimestampSoftDeleteMixin, Base):
    __tablename__ = "public_officials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class CasePartyLink(TimestampSoftDeleteMixin, Base):
    __tablename__ = "case_party_links"
    __table_args__ = (Index("idx_case_party_type_name", "party_type", "party_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    party_type: Mapped[str] = mapped_column(String(50), nullable=False)
    party_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    official_id: Mapped[Optional[int]] = mapped_column(ForeignKey("public_officials.id"), nullable=True)
    match_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    case: Mapped[Case] = relationship(back_populates="parties")


class IngestionLog(TimestampSoftDeleteMixin, Base):
    __tablename__ = "ingestion_logs"
    __table_args__ = (Index("idx_ingestion_source_run", "source", "run_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_storage_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
