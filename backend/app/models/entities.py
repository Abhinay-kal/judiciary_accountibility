from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
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


class HearingOutcomeType(str, enum.Enum):
    LISTED = "LISTED"
    HEARD = "HEARD"
    ADJOURNED = "ADJOURNED"
    ORDER_RESERVED = "ORDER_RESERVED"
    DISPOSED = "DISPOSED"
    NOT_REACHED = "NOT_REACHED"
    NO_PROCEEDINGS = "NO_PROCEEDINGS"
    OTHER = "OTHER"


class JudgeAssignmentRole(str, enum.Enum):
    PRESIDING = "PRESIDING"
    CO_JUDGE = "CO_JUDGE"
    JUDGE_MEMBER = "JUDGE_MEMBER"
    AMICUS = "AMICUS"
    OTHER = "OTHER"


class PublicStatus(str, enum.Enum):
    PUBLIC = "PUBLIC"
    LIMITED = "LIMITED"
    HIDDEN = "HIDDEN"


class ModerationTargetType(str, enum.Enum):
    CASE = "case"
    FLAG = "flag"
    EVIDENCE = "evidence"
    HEARING = "hearing"


class ContentLabelKind(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    DATA_ANOMALY = "DATA_ANOMALY"
    UNUSUAL_DELAY_PATTERN = "UNUSUAL_DELAY_PATTERN"
    REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"
    SENSITIVE = "SENSITIVE"
    REMOVED = "REMOVED"
    LEGALLY_RESTRICTED = "LEGALLY_RESTRICTED"


class ContentLabelSource(str, enum.Enum):
    AUTOMATED = "automated"
    MANUAL = "manual"


class CorrectionRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class ModerationActionType(str, enum.Enum):
    LABEL_ADDED = "LABEL_ADDED"
    LABEL_REMOVED = "LABEL_REMOVED"
    CORRECTION_HANDLED = "CORRECTION_HANDLED"
    CONTENT_REDACED = "CONTENT_REDACED"
    TAKEDOWN = "TAKEDOWN"


class FeedbackResponderType(str, enum.Enum):
    INDIVIDUAL = "INDIVIDUAL"
    GOV_AGENCY = "GOV_AGENCY"
    COMPANY = "COMPANY"
    LAW_FIRM = "LAW_FIRM"
    NGO = "NGO"


class FeedbackVerificationMethod(str, enum.Enum):
    EMAIL_TOKEN = "email_token"
    DOMAIN_VERIFICATION = "domain_verification"
    LETTER_OF_AUTHORITY = "letter_of_authority"
    ADMIN_VERIFIED = "admin_verified"
    OAUTH_PROVIDER = "oauth_provider"


class FeedbackReceivedVia(str, enum.Enum):
    API = "API"
    WEB = "WEB"
    UPLOAD = "UPLOAD"


class FeedbackPublicStatus(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    LIMITED = "LIMITED"


class FeedbackDisplayLabel(str, enum.Enum):
    OFFICIAL_RESPONSE = "OFFICIAL_RESPONSE"
    RESPONSE_FROM_PARTY = "RESPONSE_FROM_PARTY"
    CLARIFICATION = "CLARIFICATION"


class FeedbackAuditAction(str, enum.Enum):
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    PUBLISHED = "published"
    REJECTED = "rejected"
    LIMITED = "limited"
    ESCALATED = "escalated"
    EDITED_BY_ADMIN = "edited_by_admin"
    DELETED = "deleted"
    URGENT_HIDDEN = "urgent_hidden"


hearing_outcome_enum = Enum(
    HearingOutcomeType,
    name="hearing_outcome_type",
    native_enum=False,
    validate_strings=True,
)


judge_assignment_role_enum = Enum(
    JudgeAssignmentRole,
    name="judge_assignment_role",
    native_enum=False,
    validate_strings=True,
)


public_status_enum = Enum(
    PublicStatus,
    name="public_visibility_status",
    native_enum=False,
    validate_strings=True,
)


moderation_target_type_enum = Enum(
    ModerationTargetType,
    name="moderation_target_type",
    native_enum=False,
    validate_strings=True,
)


content_label_kind_enum = Enum(
    ContentLabelKind,
    name="content_label_kind",
    native_enum=False,
    validate_strings=True,
)


content_label_source_enum = Enum(
    ContentLabelSource,
    name="content_label_source",
    native_enum=False,
    validate_strings=True,
)


correction_request_status_enum = Enum(
    CorrectionRequestStatus,
    name="correction_request_status",
    native_enum=False,
    validate_strings=True,
)


moderation_action_type_enum = Enum(
    ModerationActionType,
    name="moderation_action_type",
    native_enum=False,
    validate_strings=True,
)


feedback_responder_type_enum = Enum(
    FeedbackResponderType,
    name="feedback_responder_type",
    native_enum=False,
    validate_strings=True,
)


feedback_verification_method_enum = Enum(
    FeedbackVerificationMethod,
    name="feedback_verification_method",
    native_enum=False,
    validate_strings=True,
)


feedback_received_via_enum = Enum(
    FeedbackReceivedVia,
    name="feedback_received_via",
    native_enum=False,
    validate_strings=True,
)


feedback_public_status_enum = Enum(
    FeedbackPublicStatus,
    name="feedback_public_status",
    native_enum=False,
    validate_strings=True,
)


feedback_display_label_enum = Enum(
    FeedbackDisplayLabel,
    name="feedback_display_label",
    native_enum=False,
    validate_strings=True,
)


feedback_audit_action_enum = Enum(
    FeedbackAuditAction,
    name="feedback_audit_action",
    native_enum=False,
    validate_strings=True,
)


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


class JudgeRegistry(Base):
    __tablename__ = "judge_registry"
    __table_args__ = (
        Index("idx_judge_registry_canonical_name", "canonical_name"),
    )

    judge_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_variants: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    phonetic_keys: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    service_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    court_id: Mapped[Optional[int]] = mapped_column(ForeignKey("courts.id"), nullable=True, index=True)
    known_designations: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    is_provisional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    assignments: Mapped[list["JudgeAssignment"]] = relationship(back_populates="judge_registry")


class Case(TimestampSoftDeleteMixin, Base):
    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("case_number", "court_id", name="uq_case_number_court"),
        Index("idx_cases_status_state", "status", "state"),
        Index("idx_cases_court_status_next_hearing", "court_id", "status", "next_hearing_date"),
        Index("idx_cases_state_case_type_filing", "state", "case_type", "filing_date"),
        Index("idx_cases_dormancy_status_score", "dormancy_status", "dormancy_score"),
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
    importance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    importance_components: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    importance_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    importance_override: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    normalized_delay: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    delay_percentile: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    robust_z_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delay_severity: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    baseline_level_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    baseline_sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    baseline_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_baseline_update: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    plain_summary_short: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plain_summary_detailed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_summary_update: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    impact_headline: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    impact_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    impact_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    impact_last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    dormancy_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    dormancy_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    days_since_last_activity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_activity_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    dormancy_last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    case_duration_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    is_disposed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, index=True)
    public_status: Mapped[PublicStatus] = mapped_column(public_status_enum, nullable=False, default=PublicStatus.PUBLIC, index=True)
    public_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_label_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_label_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    court: Mapped[Court] = relationship(back_populates="cases")
    hearings: Mapped[list[Hearing]] = relationship(back_populates="case")
    adjournments: Mapped[list[Adjournment]] = relationship(back_populates="case")
    orders: Mapped[list[Order]] = relationship(back_populates="case")
    flags: Mapped[list[Flag]] = relationship(back_populates="case")
    parties: Mapped[list[CasePartyLink]] = relationship(back_populates="case")
    media_mentions: Mapped[list["CaseMediaMention"]] = relationship(back_populates="case")
    importance_audits: Mapped[list["ImportanceAuditLog"]] = relationship(back_populates="case")
    feedback_entries: Mapped[list["CaseFeedback"]] = relationship(back_populates="case")
    prediction: Mapped[Optional["CasePrediction"]] = relationship(
        back_populates="case", uselist=False
    )


class CaseMediaMention(TimestampSoftDeleteMixin, Base):
    __tablename__ = "case_media_mentions"
    __table_args__ = (
        Index("idx_case_media_case_published", "case_id", "published_at"),
        Index("idx_case_media_credibility", "credibility_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    credibility_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)

    case: Mapped[Case] = relationship(back_populates="media_mentions")


class ImportanceConfig(TimestampSoftDeleteMixin, Base):
    __tablename__ = "importance_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    weights_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    case_type_map_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    min_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    media_decay_lambda: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    monetary_cap: Mapped[float] = mapped_column(Float, nullable=False, default=50_000_000.0)
    updated_by_admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class ImportanceAuditLog(Base):
    __tablename__ = "importance_audit_logs"
    __table_args__ = (
        Index("idx_importance_audit_case_created", "case_id", "created_at"),
        Index("idx_importance_audit_action_created", "action", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    old_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    new_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    case: Mapped[Case] = relationship(back_populates="importance_audits")


class Hearing(TimestampSoftDeleteMixin, Base):
    __tablename__ = "hearings"
    __table_args__ = (
        Index("idx_hearing_case_date", "case_id", "date"),
        Index("idx_hearing_judge_date", "judge_id", "date"),
        Index("idx_hearing_outcome_date_judge", "outcome_type", "date", "judge_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    judge_id: Mapped[Optional[int]] = mapped_column(ForeignKey("judges.id"), nullable=True, index=True)
    listing_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    raw_bench: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome_type: Mapped[Optional[HearingOutcomeType]] = mapped_column(hearing_outcome_enum, nullable=True, index=True)
    outcome_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_outcome_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parser_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    annotated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    annotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)

    case: Mapped[Case] = relationship(back_populates="hearings")
    judge: Mapped[Optional[Judge]] = relationship(back_populates="hearings")
    outcome_audits: Mapped[list["HearingOutcomeAudit"]] = relationship(back_populates="hearing")
    judge_assignments: Mapped[list["JudgeAssignment"]] = relationship(back_populates="hearing")

    def is_substantive_hearing(self) -> bool:
        return self.outcome_type in {
            HearingOutcomeType.HEARD,
            HearingOutcomeType.DISPOSED,
            HearingOutcomeType.ORDER_RESERVED,
        }

    def is_adjourned(self) -> bool:
        return self.outcome_type == HearingOutcomeType.ADJOURNED


class HearingOutcomeAudit(Base):
    __tablename__ = "hearing_outcome_audits"
    __table_args__ = (
        Index("idx_hearing_outcome_audit_hearing_changed", "hearing_id", "changed_at"),
        Index("idx_hearing_outcome_audit_admin_changed", "admin_id", "changed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hearing_id: Mapped[int] = mapped_column(ForeignKey("hearings.id"), nullable=False, index=True)
    admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    previous_outcome_type: Mapped[Optional[HearingOutcomeType]] = mapped_column(hearing_outcome_enum, nullable=True)
    new_outcome_type: Mapped[Optional[HearingOutcomeType]] = mapped_column(hearing_outcome_enum, nullable=True)
    previous_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    new_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    previous_parser_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_parser_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    hearing: Mapped[Hearing] = relationship(back_populates="outcome_audits")


class JudgeAssignment(Base):
    __tablename__ = "judge_assignments"
    __table_args__ = (
        UniqueConstraint("hearing_id", "judge_id", "sequence_index", name="uq_hearing_judge_sequence"),
        Index("idx_judge_assignments_hearing", "hearing_id"),
        Index("idx_judge_assignments_judge", "judge_id"),
        Index("idx_judge_assignments_confidence", "attribution_confidence"),
    )

    assignment_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    hearing_id: Mapped[int] = mapped_column(ForeignKey("hearings.id"), nullable=False, index=True)
    judge_id: Mapped[str] = mapped_column(ForeignKey("judge_registry.judge_id"), nullable=False, index=True)
    judge_name_raw: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[JudgeAssignmentRole] = mapped_column(judge_assignment_role_enum, nullable=False)
    is_presiding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attribution_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    matched_on: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ingestion_sources.id"), nullable=True, index=True)
    ingestion_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    raw_bench_snapshot_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    parser_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    annotated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    annotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    hearing: Mapped[Hearing] = relationship(back_populates="judge_assignments")
    judge_registry: Mapped[JudgeRegistry] = relationship(back_populates="assignments")


class JudgeAttributionAudit(Base):
    __tablename__ = "judge_attribution_audits"
    __table_args__ = (
        Index("idx_judge_attribution_audit_hearing", "hearing_id", "created_at"),
        Index("idx_judge_attribution_audit_registry", "judge_registry_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    hearing_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hearings.id"), nullable=True, index=True)
    assignment_id: Mapped[Optional[str]] = mapped_column(ForeignKey("judge_assignments.assignment_id"), nullable=True)
    judge_registry_id: Mapped[Optional[str]] = mapped_column(ForeignKey("judge_registry.judge_id"), nullable=True)
    admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    old_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    new_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Adjournment(TimestampSoftDeleteMixin, Base):
    __tablename__ = "adjournments"
    __table_args__ = (Index("idx_adjournments_case_is_adj", "case_id", "is_adjournment"),)

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
    public_status: Mapped[PublicStatus] = mapped_column(public_status_enum, nullable=False, default=PublicStatus.PUBLIC, index=True)
    public_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_label_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_label_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    case: Mapped[Case] = relationship(back_populates="orders")


class Flag(TimestampSoftDeleteMixin, Base):
    __tablename__ = "flags"
    __table_args__ = (
        Index("idx_flags_case_type_active", "case_id", "flag_type", "is_active"),
        Index("idx_flags_type_active_created", "flag_type", "is_active", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    flag_type: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    public_status: Mapped[PublicStatus] = mapped_column(public_status_enum, nullable=False, default=PublicStatus.PUBLIC, index=True)
    public_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_label_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_label_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    case: Mapped[Case] = relationship(back_populates="flags")


class PublicOfficial(TimestampSoftDeleteMixin, Base):
    __tablename__ = "public_officials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class CasePartyLink(TimestampSoftDeleteMixin, Base):
    __tablename__ = "case_party_links"
    __table_args__ = (
        Index("idx_case_party_type_name", "party_type", "party_name"),
        Index("idx_case_party_official_verified", "official_id", "is_verified"),
    )

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
    __table_args__ = (
        Index("idx_ingestion_source_run", "source", "run_id"),
        Index("idx_ingestion_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_storage_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ContentLabel(Base):
    __tablename__ = "content_labels"
    __table_args__ = (
        Index("idx_content_labels_target", "target_type", "target_id"),
        Index("idx_content_labels_label", "label", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[ModerationTargetType] = mapped_column(moderation_target_type_enum, nullable=False, index=True)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    label: Mapped[ContentLabelKind] = mapped_column(content_label_kind_enum, nullable=False, index=True)
    label_source: Mapped[ContentLabelSource] = mapped_column(content_label_source_enum, nullable=False, default=ContentLabelSource.AUTOMATED)
    label_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class CorrectionRequest(Base):
    __tablename__ = "correction_requests"
    __table_args__ = (
        Index("idx_corrections_target", "target_type", "target_id", "submitted_at"),
        Index("idx_corrections_status", "status", "submitted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[ModerationTargetType] = mapped_column(moderation_target_type_enum, nullable=False, index=True)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    requester_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requester_contact: Mapped[str] = mapped_column(String(255), nullable=False)
    requester_affiliation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    request_reason: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    evidence_upload_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[CorrectionRequestStatus] = mapped_column(correction_request_status_enum, nullable=False, default=CorrectionRequestStatus.PENDING, index=True)
    assigned_admin: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    review_notes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ModerationLog(Base):
    __tablename__ = "moderation_logs"
    __table_args__ = (
        Index("idx_moderation_logs_target", "target_type", "target_id", "created_at"),
        Index("idx_moderation_logs_action", "action_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_type: Mapped[ModerationActionType] = mapped_column(moderation_action_type_enum, nullable=False, index=True)
    target_type: Mapped[ModerationTargetType] = mapped_column(moderation_target_type_enum, nullable=False, index=True)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CaseFeedback(Base):
    __tablename__ = "case_feedback"
    __table_args__ = (
        Index("idx_case_feedback_case_status_submitted", "case_id", "public_status", "submitted_at"),
        Index("idx_case_feedback_contact_hash_submitted", "responder_contact_hash", "submitted_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    responder_type: Mapped[FeedbackResponderType] = mapped_column(feedback_responder_type_enum, nullable=False)
    responder_name: Mapped[str] = mapped_column(Text, nullable=False)
    responder_affiliation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responder_contact: Mapped[str] = mapped_column(Text, nullable=False)
    responder_contact_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    responder_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    responder_verification_method: Mapped[Optional[FeedbackVerificationMethod]] = mapped_column(
        feedback_verification_method_enum, nullable=True
    )
    verification_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_text_index: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachments_ref: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    received_via: Mapped[FeedbackReceivedVia] = mapped_column(feedback_received_via_enum, nullable=False, default=FeedbackReceivedVia.WEB)
    public_status: Mapped[FeedbackPublicStatus] = mapped_column(
        feedback_public_status_enum, nullable=False, default=FeedbackPublicStatus.PENDING_REVIEW, index=True
    )
    public_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_label: Mapped[FeedbackDisplayLabel] = mapped_column(
        feedback_display_label_enum, nullable=False, default=FeedbackDisplayLabel.RESPONSE_FROM_PARTY
    )
    moderator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    moderation_notes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expiry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    legal_escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    urgent_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    loa_attachment_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    case: Mapped[Case] = relationship(back_populates="feedback_entries")
    verifications: Mapped[list["FeedbackVerification"]] = relationship(back_populates="feedback")
    audit_logs: Mapped[list["FeedbackAuditLog"]] = relationship(back_populates="feedback")


class FeedbackVerification(Base):
    __tablename__ = "feedback_verifications"
    __table_args__ = (Index("idx_feedback_verification_feedback", "feedback_id", "method"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[str] = mapped_column(ForeignKey("case_feedback.id"), nullable=False, index=True)
    method: Mapped[FeedbackVerificationMethod] = mapped_column(feedback_verification_method_enum, nullable=False)
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    verifier_admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    feedback: Mapped[CaseFeedback] = relationship(back_populates="verifications")


class FeedbackAuditLog(Base):
    __tablename__ = "feedback_audit_logs"
    __table_args__ = (Index("idx_feedback_audit_feedback_created", "feedback_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[str] = mapped_column(ForeignKey("case_feedback.id"), nullable=False, index=True)
    action: Mapped[FeedbackAuditAction] = mapped_column(feedback_audit_action_enum, nullable=False, index=True)
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    feedback: Mapped[CaseFeedback] = relationship(back_populates="audit_logs")


class CasePrediction(TimestampSoftDeleteMixin, Base):
    """ML-generated duration prediction and delay classification for a case.

    One row per case (unique on ``case_id``).  Created or updated by the
    ``run_ml_batch_inference`` Celery task.  The table is **additive** to the
    core schema — dropping it has no effect on other functionality.
    """

    __tablename__ = "case_predictions"
    __table_args__ = (
        Index("idx_case_pred_flag_severity", "ml_delay_flag", "ml_delay_severity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id"), nullable=False, unique=True, index=True
    )

    # Point estimate and uncertainty bounds (all in days)
    predicted_duration_days: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound_days: Mapped[float] = mapped_column(Float, nullable=False)
    upper_bound_days: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Delay analysis
    delay_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ml_delay_flag: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    ml_delay_severity: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, index=True
    )

    # Model provenance
    ml_model_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Explainability payload ({top_features: [{feature, importance}, ...]})
    feature_importance: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    case: Mapped["Case"] = relationship(back_populates="prediction")


class DelayBaseline(Base):
    __tablename__ = "delay_baselines"
    __table_args__ = (
        UniqueConstraint("baseline_level", "court_id", "state", "case_type", name="uq_delay_baseline_level_scope"),
        Index("idx_delay_baseline_level_scope", "baseline_level", "court_id", "state", "case_type"),
        Index("idx_delay_baseline_computed", "computed_at"),
        Index("idx_delay_baseline_sample", "sample_size"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    court_id: Mapped[Optional[int]] = mapped_column(ForeignKey("courts.id"), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    case_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    baseline_level: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    median_delay: Mapped[float] = mapped_column(Float, nullable=False)
    p75_delay: Mapped[float] = mapped_column(Float, nullable=False)
    p90_delay: Mapped[float] = mapped_column(Float, nullable=False)
    iqr_delay: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    window_years: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SurvivalCurve(Base):
    __tablename__ = "survival_curves"
    __table_args__ = (
        UniqueConstraint("grouping_type", "grouping_value", "case_type", name="uq_survival_curve_group"),
        Index("idx_survival_curve_group", "grouping_type", "grouping_value", "case_type"),
        Index("idx_survival_curve_computed", "computed_at"),
    )

    curve_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grouping_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    grouping_value: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    case_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    time_points: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    survival_probabilities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    lower_ci: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    upper_ci: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    hazard_rates: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    median_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvestigationSnapshot(Base):
    __tablename__ = "investigation_snapshots"
    __table_args__ = (
        UniqueConstraint("case_id", "version_number", name="uq_investigation_snapshot_case_version"),
        Index("idx_investigation_snapshot_case_current", "case_id", "is_current"),
        Index("idx_investigation_snapshot_generated", "generated_at"),
        Index("idx_investigation_snapshot_hash", "content_hash"),
    )

    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    data_cutoff_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    snapshot_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
