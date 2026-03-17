from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

REL_DERIVED_FROM = "DERIVED_FROM"
REL_CONFLICTS_WITH = "CONFLICTS_WITH"
REL_CONFIRMED_BY = "CONFIRMED_BY"

SOURCE_API = "API"
SOURCE_HTML = "HTML"
SOURCE_PDF = "PDF"
SOURCE_MANUAL = "MANUAL"


class FieldProvenance(Base):
    __tablename__ = "field_provenance"
    __table_args__ = (
        Index("idx_field_provenance_entity_field", "entity_type", "entity_id", "field_name", "created_at"),
        Index("idx_field_provenance_hash", "field_value_hash"),
        Index("idx_field_provenance_source", "source_name", "fetch_time"),
        Index("idx_field_provenance_run", "ingestion_run_id"),
        Index("idx_field_provenance_primary", "entity_type", "entity_id", "field_name", "is_primary_source"),
    )

    provenance_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    field_value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(120), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fetch_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ingestion_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    transformation_steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_primary_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    parent_links: Mapped[list["ProvenanceLink"]] = relationship(
        back_populates="parent_provenance",
        foreign_keys="ProvenanceLink.parent_provenance_id",
    )
    child_links: Mapped[list["ProvenanceLink"]] = relationship(
        back_populates="child_provenance",
        foreign_keys="ProvenanceLink.child_provenance_id",
    )


class ProvenanceLink(Base):
    __tablename__ = "provenance_links"
    __table_args__ = (
        UniqueConstraint("parent_provenance_id", "child_provenance_id", "relationship_type", name="uq_provenance_links_rel"),
        Index("idx_provenance_links_parent", "parent_provenance_id"),
        Index("idx_provenance_links_child", "child_provenance_id"),
        Index("idx_provenance_links_rel", "relationship_type"),
    )

    link_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parent_provenance_id: Mapped[int] = mapped_column(ForeignKey("field_provenance.provenance_id"), nullable=False)
    child_provenance_id: Mapped[int] = mapped_column(ForeignKey("field_provenance.provenance_id"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    parent_provenance: Mapped[FieldProvenance] = relationship(
        back_populates="parent_links",
        foreign_keys=[parent_provenance_id],
    )
    child_provenance: Mapped[FieldProvenance] = relationship(
        back_populates="child_links",
        foreign_keys=[child_provenance_id],
    )
