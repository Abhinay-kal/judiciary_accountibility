from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class UpdateFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    REALTIME = "realtime"


class PrivacyClassification(str, Enum):
    PUBLIC = "public"
    ANONYMIZED_PUBLIC = "anonymized_public"
    RESTRICTED = "restricted"


@dataclass(slots=True)
class DatasetField:
    name: str
    field_type: str
    description: str
    nullable: bool = True
    example: Any | None = None


@dataclass(slots=True)
class DatasetCatalogEntry:
    dataset_id: str
    name: str
    description: str
    schema: str
    fields: list[DatasetField]
    update_frequency: UpdateFrequency
    version: str
    license: str
    data_quality_notes: str
    privacy_classification: PrivacyClassification
    methodology_notes: str
    known_limitations: str
    provenance_summary: str
    permitted_uses: str
    recommended_citation: str
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


OPEN_DATA_LICENSE = "Open Data Commons Attribution License (ODC-By 1.0)"


def _base_citation() -> str:
    return (
        "Data from Court Case Delay & Justice Tracker, "
        "retrieved on [date]."
    )


def default_catalog_entries() -> list[DatasetCatalogEntry]:
    return [
        DatasetCatalogEntry(
            dataset_id="case_metadata",
            name="Case Metadata",
            description="Core metadata for public court cases.",
            schema="justice_tracker.case_metadata.v1",
            fields=[
                DatasetField("case_id", "integer", "Internal case identifier", False, 123),
                DatasetField("case_uid", "string", "Stable case UID", False, "SC_2025_0001"),
                DatasetField("cnr", "string", "Case Number Record identifier"),
                DatasetField("case_number", "string", "Human readable case number", False),
                DatasetField("court", "string", "Court name", False),
                DatasetField("state", "string", "State"),
                DatasetField("court_level", "string", "Court level"),
                DatasetField("case_type", "string", "Case type"),
                DatasetField("status", "string", "Current case status"),
                DatasetField("filing_date", "date", "Filing date"),
                DatasetField("next_hearing_date", "date", "Next hearing date"),
                DatasetField("importance_score", "float", "Normalized importance score"),
                DatasetField("normalized_delay", "float", "Delay score normalized against peers"),
                DatasetField("public_status", "string", "Public visibility status"),
                DatasetField("last_source_updated_at", "datetime", "Source data refresh timestamp"),
            ],
            update_frequency=UpdateFrequency.DAILY,
            version="1.0.0",
            license=OPEN_DATA_LICENSE,
            data_quality_notes="Case status and date fields can lag source portals.",
            privacy_classification=PrivacyClassification.ANONYMIZED_PUBLIC,
            methodology_notes="Extracted from official court feeds and normalized for analytics.",
            known_limitations="Inconsistent source formatting for legacy cases.",
            provenance_summary="Derived from ingestion runs and verified source links.",
            permitted_uses="Research, journalism, civic analysis, public accountability.",
            recommended_citation=_base_citation(),
        ),
        DatasetCatalogEntry(
            dataset_id="hearing_timelines",
            name="Hearing Timelines",
            description="Chronological hearing-level events by case.",
            schema="justice_tracker.hearing_timelines.v1",
            fields=[
                DatasetField("hearing_id", "integer", "Hearing identifier", False),
                DatasetField("case_id", "integer", "Case identifier", False),
                DatasetField("hearing_date", "date", "Date of hearing", False),
                DatasetField("listing_type", "string", "Listing classification"),
                DatasetField("outcome_type", "string", "Derived outcome type"),
                DatasetField("outcome_confidence", "float", "Parser confidence score"),
                DatasetField("source", "string", "Source system"),
            ],
            update_frequency=UpdateFrequency.DAILY,
            version="1.0.0",
            license=OPEN_DATA_LICENSE,
            data_quality_notes="Outcome extraction confidence may vary across courts.",
            privacy_classification=PrivacyClassification.ANONYMIZED_PUBLIC,
            methodology_notes="Outcome labels are parser-assisted and auditable.",
            known_limitations="Raw bench text omitted to reduce privacy risk.",
            provenance_summary="Built from hearings table and parser metadata.",
            permitted_uses="Timeline analyses and hearing behavior studies.",
            recommended_citation=_base_citation(),
        ),
        DatasetCatalogEntry(
            dataset_id="court_statistics",
            name="Court Statistics",
            description="Aggregated court-level pending/disposed metrics.",
            schema="justice_tracker.court_statistics.v1",
            fields=[
                DatasetField("court_id", "integer", "Court identifier", False),
                DatasetField("court_name", "string", "Court name", False),
                DatasetField("state", "string", "State"),
                DatasetField("total_cases", "integer", "Total case count", False),
                DatasetField("pending_cases", "integer", "Pending case count", False),
                DatasetField("disposed_cases", "integer", "Disposed case count", False),
                DatasetField("backlog_ratio", "float", "Pending / total ratio", False),
                DatasetField("computed_at", "datetime", "Metric computation timestamp"),
            ],
            update_frequency=UpdateFrequency.DAILY,
            version="1.0.0",
            license=OPEN_DATA_LICENSE,
            data_quality_notes="Backlog ratio derived from current status labels.",
            privacy_classification=PrivacyClassification.PUBLIC,
            methodology_notes="Uses precomputed cache when available, otherwise live aggregation.",
            known_limitations="Court merges/renames can impact historical continuity.",
            provenance_summary="Derived from courts, cases, and court_stats cache.",
            permitted_uses="Policy analysis and public reporting.",
            recommended_citation=_base_citation(),
        ),
        DatasetCatalogEntry(
            dataset_id="judge_metrics_aggregated",
            name="Judge Metrics (Aggregated)",
            description="Judge-level aggregate hearing and confidence indicators.",
            schema="justice_tracker.judge_metrics_aggregated.v1",
            fields=[
                DatasetField("judge_id", "integer", "Judge identifier", False),
                DatasetField("judge_name", "string", "Judge display name", False),
                DatasetField("court_id", "integer", "Court identifier"),
                DatasetField("hearing_count", "integer", "Count of hearings", False),
                DatasetField("avg_outcome_confidence", "float", "Average parser confidence"),
                DatasetField("computed_at", "datetime", "Metric timestamp"),
            ],
            update_frequency=UpdateFrequency.WEEKLY,
            version="1.0.0",
            license=OPEN_DATA_LICENSE,
            data_quality_notes="Intentionally aggregated to avoid sensitive profiling.",
            privacy_classification=PrivacyClassification.ANONYMIZED_PUBLIC,
            methodology_notes="Only aggregate indicators, no personal identifiers exported.",
            known_limitations="Confidence values depend on parser model version.",
            provenance_summary="Derived from judge_stats cache and hearings.",
            permitted_uses="Systemic workload and process analysis.",
            recommended_citation=_base_citation(),
        ),
        DatasetCatalogEntry(
            dataset_id="delay_distributions",
            name="Delay Distributions",
            description="Distribution bins for delay signals by state/case type.",
            schema="justice_tracker.delay_distributions.v1",
            fields=[
                DatasetField("state", "string", "State"),
                DatasetField("case_type", "string", "Case type"),
                DatasetField("delay_bin", "string", "Delay interval bin"),
                DatasetField("case_count", "integer", "Cases in bin", False),
                DatasetField("coverage_ratio", "float", "Share of filtered case set"),
            ],
            update_frequency=UpdateFrequency.WEEKLY,
            version="1.0.0",
            license=OPEN_DATA_LICENSE,
            data_quality_notes="Requires normalized delay values to be present.",
            privacy_classification=PrivacyClassification.PUBLIC,
            methodology_notes="Binned from normalized delay values in case records.",
            known_limitations="Sparse jurisdictions may produce unstable bins.",
            provenance_summary="Derived analytics over cases table.",
            permitted_uses="Delay benchmarking and trend analysis.",
            recommended_citation=_base_citation(),
        ),
        DatasetCatalogEntry(
            dataset_id="flagged_cases",
            name="Flagged Cases",
            description="Publicly visible flags and severity signals by case.",
            schema="justice_tracker.flagged_cases.v1",
            fields=[
                DatasetField("flag_id", "integer", "Flag identifier", False),
                DatasetField("case_id", "integer", "Case identifier", False),
                DatasetField("flag_type", "string", "Flag category", False),
                DatasetField("score", "float", "Flag score"),
                DatasetField("is_active", "boolean", "Whether flag is active", False),
                DatasetField("created_at", "datetime", "Flag creation time", False),
            ],
            update_frequency=UpdateFrequency.DAILY,
            version="1.0.0",
            license=OPEN_DATA_LICENSE,
            data_quality_notes="Flag logic may evolve with model updates.",
            privacy_classification=PrivacyClassification.ANONYMIZED_PUBLIC,
            methodology_notes="Only public-status flags are exported.",
            known_limitations="Flag score semantics vary by flag type.",
            provenance_summary="Derived from flags table.",
            permitted_uses="Accountability and anomaly reporting.",
            recommended_citation=_base_citation(),
        ),
        DatasetCatalogEntry(
            dataset_id="external_coverage_links",
            name="External Coverage Links",
            description="External media links associated with cases.",
            schema="justice_tracker.external_coverage_links.v1",
            fields=[
                DatasetField("mention_id", "integer", "Mention identifier", False),
                DatasetField("case_id", "integer", "Case identifier", False),
                DatasetField("source_name", "string", "Media source name", False),
                DatasetField("source_url", "string", "Coverage URL", False),
                DatasetField("published_at", "datetime", "Coverage publication time"),
                DatasetField("credibility_score", "float", "Mention credibility score"),
            ],
            update_frequency=UpdateFrequency.DAILY,
            version="1.0.0",
            license=OPEN_DATA_LICENSE,
            data_quality_notes="External links may expire or move.",
            privacy_classification=PrivacyClassification.PUBLIC,
            methodology_notes="Captured from media mention ingestion workflows.",
            known_limitations="Not exhaustive across all media ecosystems.",
            provenance_summary="Derived from case_media_mentions.",
            permitted_uses="Media monitoring and case impact studies.",
            recommended_citation=_base_citation(),
        ),
        DatasetCatalogEntry(
            dataset_id="derived_analytics",
            name="Derived Analytics",
            description="Derived indicators combining delay, impact, and case outcomes.",
            schema="justice_tracker.derived_analytics.v1",
            fields=[
                DatasetField("state", "string", "State"),
                DatasetField("court_level", "string", "Court level"),
                DatasetField("pending_cases", "integer", "Pending case count"),
                DatasetField("avg_importance_score", "float", "Average importance"),
                DatasetField("avg_normalized_delay", "float", "Average normalized delay"),
                DatasetField("high_importance_case_share", "float", "Share with importance >= threshold"),
            ],
            update_frequency=UpdateFrequency.WEEKLY,
            version="1.0.0",
            license=OPEN_DATA_LICENSE,
            data_quality_notes="Derived indicators depend on model freshness.",
            privacy_classification=PrivacyClassification.PUBLIC,
            methodology_notes="Computed from aggregate statistics over filtered cases.",
            known_limitations="Non-random missingness can bias averages.",
            provenance_summary="Derived from cases with validated delay/importance values.",
            permitted_uses="Policy, research, and civic reporting.",
            recommended_citation=_base_citation(),
        ),
    ]


class DatasetCatalog:
    def __init__(self, entries: list[DatasetCatalogEntry] | None = None) -> None:
        self._entries = {entry.dataset_id: entry for entry in (entries or default_catalog_entries())}

    def list_entries(self) -> list[DatasetCatalogEntry]:
        return sorted(self._entries.values(), key=lambda entry: entry.dataset_id)

    def get_entry(self, dataset_id: str) -> DatasetCatalogEntry | None:
        return self._entries.get(dataset_id)

    def exists(self, dataset_id: str) -> bool:
        return dataset_id in self._entries


DEFAULT_DATASET_CATALOG = DatasetCatalog()
