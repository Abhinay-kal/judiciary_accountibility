from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case as sql_case
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Case, CaseMediaMention, Court, CourtStatsCache, Flag, Hearing, Judge, JudgeStatsCache
from app.open_data.anonymization import anonymize_rows
from app.open_data.catalog import DEFAULT_DATASET_CATALOG
from app.open_data.filters import ExportFilters, apply_case_export_filters
from app.open_data.formats import ExportFormat, serialize_rows
from app.open_data.metadata import build_metadata, compute_quality_indicators
from app.open_data.versioning import VersionRegistry


@dataclass(slots=True)
class ExportBundle:
    filename: str
    payload: bytes
    content_type: str
    metadata: dict
    row_count: int


class OpenDataExporter:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.catalog = DEFAULT_DATASET_CATALOG
        self.versions = VersionRegistry(self.catalog)

    def export_dataset(
        self,
        dataset_id: str,
        export_format: ExportFormat,
        filters: ExportFilters,
        requested_version: str | None = None,
        compress: bool = False,
    ) -> ExportBundle:
        entry = self.catalog.get_entry(dataset_id)
        if entry is None:
            raise ValueError(f"Dataset '{dataset_id}' not found")

        version = self.versions.resolve_version(dataset_id, requested_version)
        rows = self._fetch_rows(dataset_id, filters)

        anonymized = anonymize_rows(dataset_id, rows)
        serialized = serialize_rows(anonymized.rows, export_format=export_format, compress=compress)

        quality = compute_quality_indicators(anonymized.rows, [field.name for field in entry.fields])
        metadata = build_metadata(entry, version=version, row_count=len(anonymized.rows), quality=quality)
        metadata["masked_fields"] = anonymized.masked_fields
        metadata["filters_applied"] = filters.model_dump(exclude_none=True)

        filename = f"{dataset_id}_v{version}.{serialized.file_extension}"
        return ExportBundle(
            filename=filename,
            payload=serialized.payload,
            content_type=serialized.content_type,
            metadata=metadata,
            row_count=len(anonymized.rows),
        )

    def _fetch_rows(self, dataset_id: str, filters: ExportFilters) -> list[dict]:
        if dataset_id == "case_metadata":
            return self._case_metadata_rows(filters)
        if dataset_id == "hearing_timelines":
            return self._hearing_timeline_rows(filters)
        if dataset_id == "court_statistics":
            return self._court_statistics_rows(filters)
        if dataset_id == "judge_metrics_aggregated":
            return self._judge_metrics_rows(filters)
        if dataset_id == "delay_distributions":
            return self._delay_distribution_rows(filters)
        if dataset_id == "flagged_cases":
            return self._flagged_cases_rows(filters)
        if dataset_id == "external_coverage_links":
            return self._external_coverage_rows(filters)
        if dataset_id == "derived_analytics":
            return self._derived_analytics_rows(filters)
        raise ValueError(f"Unsupported dataset '{dataset_id}'")

    def _case_metadata_rows(self, filters: ExportFilters) -> list[dict]:
        query = self.db.query(Case, Court).join(Court, Case.court_id == Court.id)
        query = apply_case_export_filters(query, filters)
        rows = query.order_by(Case.id.asc()).limit(filters.max_rows).all()

        output = []
        for case_obj, court in rows:
            output.append(
                {
                    "case_id": case_obj.id,
                    "case_uid": case_obj.case_uid,
                    "cnr": case_obj.cnr,
                    "case_number": case_obj.case_number,
                    "court": court.name,
                    "state": case_obj.state,
                    "court_level": case_obj.court_level,
                    "case_type": case_obj.case_type,
                    "status": case_obj.status,
                    "filing_date": case_obj.filing_date,
                    "next_hearing_date": case_obj.next_hearing_date,
                    "importance_score": case_obj.importance_score,
                    "normalized_delay": case_obj.normalized_delay,
                    "public_status": case_obj.public_status.value if case_obj.public_status else None,
                    "last_source_updated_at": case_obj.last_source_updated_at,
                }
            )
        return output

    def _hearing_timeline_rows(self, filters: ExportFilters) -> list[dict]:
        case_query = self.db.query(Case.id)
        case_query = apply_case_export_filters(case_query, filters)
        case_ids_subquery = case_query.subquery()

        query = (
            self.db.query(Hearing)
            .join(case_ids_subquery, Hearing.case_id == case_ids_subquery.c.id)
            .filter(Hearing.is_deleted.is_(False))
            .order_by(Hearing.date.asc())
            .limit(filters.max_rows)
        )

        rows = query.all()
        return [
            {
                "hearing_id": item.id,
                "case_id": item.case_id,
                "hearing_date": item.date,
                "listing_type": item.listing_type,
                "outcome_type": item.outcome_type.value if item.outcome_type else None,
                "outcome_confidence": item.outcome_confidence,
                "source": item.source,
            }
            for item in rows
        ]

    def _court_statistics_rows(self, filters: ExportFilters) -> list[dict]:
        cached = (
            self.db.query(CourtStatsCache, Court)
            .join(Court, CourtStatsCache.court_id == Court.id)
            .order_by(CourtStatsCache.backlog_ratio.desc())
            .limit(filters.max_rows)
            .all()
        )
        if cached:
            rows = [
                {
                    "court_id": stat.court_id,
                    "court_name": court.name,
                    "state": court.state,
                    "total_cases": stat.total_cases,
                    "pending_cases": stat.pending_cases,
                    "disposed_cases": stat.disposed_cases,
                    "backlog_ratio": stat.backlog_ratio,
                    "computed_at": stat.computed_at,
                }
                for stat, court in cached
            ]
            if filters.state:
                rows = [row for row in rows if row.get("state") == filters.state]
            return rows[: filters.max_rows]

        pending_expr = sql_case((Case.status.ilike("%pending%"), 1), else_=0)
        disposed_expr = sql_case((Case.status.ilike("%disposed%"), 1), else_=0)

        query = (
            self.db.query(
                Court.id.label("court_id"),
                Court.name.label("court_name"),
                Court.state.label("state"),
                func.count(Case.id).label("total_cases"),
                func.sum(pending_expr).label("pending_cases"),
                func.sum(disposed_expr).label("disposed_cases"),
            )
            .join(Case, Case.court_id == Court.id)
            .filter(Case.is_deleted.is_(False), Court.is_deleted.is_(False))
            .group_by(Court.id, Court.name, Court.state)
        )

        if filters.state:
            query = query.filter(Court.state == filters.state)

        rows = query.limit(filters.max_rows).all()
        output = []
        for row in rows:
            total = int(row.total_cases or 0)
            pending = int(row.pending_cases or 0)
            output.append(
                {
                    "court_id": row.court_id,
                    "court_name": row.court_name,
                    "state": row.state,
                    "total_cases": total,
                    "pending_cases": pending,
                    "disposed_cases": int(row.disposed_cases or 0),
                    "backlog_ratio": float(pending / total) if total else 0.0,
                    "computed_at": datetime.utcnow(),
                }
            )
        return output

    def _judge_metrics_rows(self, filters: ExportFilters) -> list[dict]:
        cached = (
            self.db.query(JudgeStatsCache, Judge)
            .join(Judge, JudgeStatsCache.judge_id == Judge.id)
            .filter(Judge.is_deleted.is_(False))
            .order_by(JudgeStatsCache.hearing_count.desc())
            .limit(filters.max_rows)
            .all()
        )
        if cached:
            return [
                {
                    "judge_id": row.judge_id,
                    "judge_name": judge.name,
                    "court_id": judge.court_id,
                    "hearing_count": row.hearing_count,
                    "avg_outcome_confidence": row.avg_outcome_confidence,
                    "computed_at": row.computed_at,
                }
                for row, judge in cached
            ]

        query = (
            self.db.query(
                Judge.id.label("judge_id"),
                Judge.name.label("judge_name"),
                Judge.court_id.label("court_id"),
                func.count(Hearing.id).label("hearing_count"),
                func.avg(Hearing.outcome_confidence).label("avg_outcome_confidence"),
            )
            .join(Hearing, Hearing.judge_id == Judge.id)
            .filter(Judge.is_deleted.is_(False), Hearing.is_deleted.is_(False))
            .group_by(Judge.id, Judge.name, Judge.court_id)
            .order_by(func.count(Hearing.id).desc())
            .limit(filters.max_rows)
            .all()
        )

        return [
            {
                "judge_id": row.judge_id,
                "judge_name": row.judge_name,
                "court_id": row.court_id,
                "hearing_count": int(row.hearing_count or 0),
                "avg_outcome_confidence": float(row.avg_outcome_confidence or 0.0),
                "computed_at": datetime.utcnow(),
            }
            for row in query
        ]

    def _delay_distribution_rows(self, filters: ExportFilters) -> list[dict]:
        query = self.db.query(Case)
        query = apply_case_export_filters(query, filters)
        cases = query.filter(Case.normalized_delay.is_not(None)).limit(filters.max_rows).all()

        bins = {
            "0-0.5": 0,
            "0.5-1.0": 0,
            "1.0-2.0": 0,
            "2.0-3.0": 0,
            "3.0+": 0,
        }

        by_state_case_type: dict[tuple[str, str], dict[str, int]] = {}
        for case_obj in cases:
            state = case_obj.state or "unknown"
            case_type = case_obj.case_type or "unknown"
            key = (state, case_type)
            if key not in by_state_case_type:
                by_state_case_type[key] = dict(bins)

            delay = float(case_obj.normalized_delay or 0.0)
            if delay < 0.5:
                by_state_case_type[key]["0-0.5"] += 1
            elif delay < 1.0:
                by_state_case_type[key]["0.5-1.0"] += 1
            elif delay < 2.0:
                by_state_case_type[key]["1.0-2.0"] += 1
            elif delay < 3.0:
                by_state_case_type[key]["2.0-3.0"] += 1
            else:
                by_state_case_type[key]["3.0+"] += 1

        output: list[dict] = []
        for (state, case_type), distribution in by_state_case_type.items():
            total = sum(distribution.values())
            for delay_bin, count in distribution.items():
                if count == 0:
                    continue
                output.append(
                    {
                        "state": state,
                        "case_type": case_type,
                        "delay_bin": delay_bin,
                        "case_count": count,
                        "coverage_ratio": round(count / total, 4) if total else 0.0,
                    }
                )
        return output[: filters.max_rows]

    def _flagged_cases_rows(self, filters: ExportFilters) -> list[dict]:
        case_query = self.db.query(Case.id)
        case_query = apply_case_export_filters(case_query, filters)
        case_ids_subquery = case_query.subquery()

        query = (
            self.db.query(Flag)
            .join(case_ids_subquery, Flag.case_id == case_ids_subquery.c.id)
            .filter(Flag.is_deleted.is_(False), Flag.is_active.is_(True))
            .order_by(Flag.created_at.desc())
            .limit(filters.max_rows)
        )

        rows = query.all()
        return [
            {
                "flag_id": row.id,
                "case_id": row.case_id,
                "flag_type": row.flag_type,
                "score": row.score,
                "is_active": row.is_active,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def _external_coverage_rows(self, filters: ExportFilters) -> list[dict]:
        case_query = self.db.query(Case.id)
        case_query = apply_case_export_filters(case_query, filters)
        case_ids_subquery = case_query.subquery()

        query = (
            self.db.query(CaseMediaMention)
            .join(case_ids_subquery, CaseMediaMention.case_id == case_ids_subquery.c.id)
            .filter(CaseMediaMention.is_deleted.is_(False))
            .order_by(CaseMediaMention.published_at.desc())
            .limit(filters.max_rows)
        )

        rows = query.all()
        return [
            {
                "mention_id": row.id,
                "case_id": row.case_id,
                "source_name": row.source_name,
                "source_url": row.source_url,
                "published_at": row.published_at,
                "credibility_score": row.credibility_score,
            }
            for row in rows
        ]

    def _derived_analytics_rows(self, filters: ExportFilters) -> list[dict]:
        query = self.db.query(Case)
        query = apply_case_export_filters(query, filters)
        cases = query.limit(filters.max_rows).all()

        grouped: dict[tuple[str, str], list[Case]] = {}
        for case_obj in cases:
            key = (case_obj.state or "unknown", case_obj.court_level or "unknown")
            grouped.setdefault(key, []).append(case_obj)

        rows: list[dict] = []
        for (state, court_level), members in grouped.items():
            pending = sum(1 for item in members if (item.status or "").lower().startswith("pending"))
            importance_values = [float(item.importance_score) for item in members if item.importance_score is not None]
            delay_values = [float(item.normalized_delay) for item in members if item.normalized_delay is not None]
            high_importance = sum(1 for item in members if (item.importance_score or 0.0) >= 0.7)

            rows.append(
                {
                    "state": state,
                    "court_level": court_level,
                    "pending_cases": pending,
                    "avg_importance_score": (sum(importance_values) / len(importance_values)) if importance_values else 0.0,
                    "avg_normalized_delay": (sum(delay_values) / len(delay_values)) if delay_values else 0.0,
                    "high_importance_case_share": (high_importance / len(members)) if members else 0.0,
                }
            )

        rows.sort(key=lambda row: row["pending_cases"], reverse=True)
        return rows[: filters.max_rows]
