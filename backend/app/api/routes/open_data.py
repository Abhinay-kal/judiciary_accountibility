from __future__ import annotations

import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.open_data import DEFAULT_DATASET_CATALOG, DeliveryManager, ExportFilters, ExportFormat, OpenDataExporter
from app.open_data.anonymization import anonymize_rows
from app.open_data.formats import stream_ndjson


router = APIRouter(prefix="/datasets")
_catalog = DEFAULT_DATASET_CATALOG
_delivery = DeliveryManager()


@dataclass(slots=True)
class AccessTier:
    name: str
    requests_per_hour: int
    max_rows: int


PUBLIC_TIER = AccessTier(name="public", requests_per_hour=60, max_rows=50_000)
KEY_TIER = AccessTier(name="api_key", requests_per_hour=300, max_rows=250_000)


class InMemoryQuota:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        with self._lock:
            history = self._hits.setdefault(key, [])
            cutoff = now - window_seconds
            while history and history[0] < cutoff:
                history.pop(0)
            if len(history) >= limit:
                return False
            history.append(now)
            return True


_quota = InMemoryQuota()


def _valid_api_keys() -> set[str]:
    raw = os.getenv("OPEN_DATA_API_KEYS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _access_tier(request: Request) -> AccessTier:
    key = request.headers.get("x-api-key")
    if key and key in _valid_api_keys():
        return KEY_TIER
    return PUBLIC_TIER


def _apply_quota(request: Request, tier: AccessTier) -> None:
    client = request.client.host if request.client else "anonymous"
    quota_key = f"{client}:{tier.name}:open_data"
    if not _quota.allow(quota_key, limit=tier.requests_per_hour, window_seconds=3600):
        raise HTTPException(status_code=429, detail="Hourly open-data quota exceeded")


def _parse_format(format_name: str) -> ExportFormat:
    try:
        return ExportFormat(format_name.lower())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported format '{format_name}'") from exc


def _filters_from_query(
    state: str | None,
    court: str | None,
    case_type: str | None,
    date_from: str | None,
    date_to: str | None,
    status: str | None,
    importance_score: float | None,
    max_rows: int,
) -> ExportFilters:
    return ExportFilters(
        state=state,
        court=court,
        case_type=case_type,
        date_from=date_from,
        date_to=date_to,
        status=status,
        min_importance_score=importance_score,
        max_rows=max_rows,
    )


@router.get("")
def list_datasets() -> dict[str, Any]:
    entries = _catalog.list_entries()
    return {
        "items": [
            {
                "dataset_id": entry.dataset_id,
                "name": entry.name,
                "description": entry.description,
                "version": entry.version,
                "update_frequency": entry.update_frequency.value,
                "privacy_classification": entry.privacy_classification.value,
                "license": entry.license,
                "recommended_citation": entry.recommended_citation,
            }
            for entry in entries
        ],
        "count": len(entries),
    }


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str) -> dict[str, Any]:
    entry = _catalog.get_entry(dataset_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return {
        "dataset_id": entry.dataset_id,
        "name": entry.name,
        "description": entry.description,
        "schema": entry.schema,
        "fields": [
            {
                "name": field.name,
                "type": field.field_type,
                "description": field.description,
                "nullable": field.nullable,
                "example": field.example,
            }
            for field in entry.fields
        ],
        "update_frequency": entry.update_frequency.value,
        "version": entry.version,
        "license": entry.license,
        "data_quality_notes": entry.data_quality_notes,
        "privacy_classification": entry.privacy_classification.value,
        "methodology_notes": entry.methodology_notes,
        "known_limitations": entry.known_limitations,
        "provenance_summary": entry.provenance_summary,
        "permitted_uses": entry.permitted_uses,
        "recommended_citation": entry.recommended_citation,
        "last_updated": entry.last_updated.isoformat(),
    }


@router.get("/{dataset_id}/v/{version}")
def get_dataset_version(dataset_id: str, version: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    entry = _catalog.get_entry(dataset_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    exporter = OpenDataExporter(db)
    resolved = exporter.versions.resolve_version(dataset_id, version)

    return {
        "dataset_id": dataset_id,
        "version": resolved,
        "download_url": f"/api/v1/datasets/{dataset_id}/download?version={resolved}",
        "schema_url": f"/api/v1/datasets/{dataset_id}/schema",
        "notes": "Versioned endpoint for reproducible research.",
    }


@router.get("/{dataset_id}/schema")
def get_dataset_schema(dataset_id: str) -> dict[str, Any]:
    entry = _catalog.get_entry(dataset_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return {
        "dataset_id": entry.dataset_id,
        "schema": entry.schema,
        "version": entry.version,
        "fields": [
            {
                "name": field.name,
                "type": field.field_type,
                "description": field.description,
                "nullable": field.nullable,
                "example": field.example,
            }
            for field in entry.fields
        ],
        "data_dictionary": {field.name: field.description for field in entry.fields},
    }


@router.get("/{dataset_id}/download")
def download_dataset(
    request: Request,
    dataset_id: str,
    format: str = Query(default="csv", pattern="^(csv|json|parquet|ndjson)$"),
    version: str | None = None,
    state: str | None = None,
    court: str | None = None,
    case_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    importance_score: float | None = Query(default=None, ge=0.0, le=1.0),
    max_rows: int = Query(default=100_000, ge=1, le=500_000),
    compress: bool = Query(default=False),
    stream: bool = Query(default=False),
    precomputed: bool = Query(default=True),
    cloud_link: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    entry = _catalog.get_entry(dataset_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    tier = _access_tier(request)
    _apply_quota(request, tier)

    if max_rows > tier.max_rows:
        raise HTTPException(
            status_code=403,
            detail=f"Requested max_rows exceeds tier limit ({tier.max_rows})",
        )

    export_format = _parse_format(format)
    filters = _filters_from_query(
        state=state,
        court=court,
        case_type=case_type,
        date_from=date_from,
        date_to=date_to,
        status=status,
        importance_score=importance_score,
        max_rows=max_rows,
    )

    exporter = OpenDataExporter(db)

    if stream and export_format == ExportFormat.NDJSON:
        rows = exporter._fetch_rows(dataset_id, filters)
        anonymized = anonymize_rows(dataset_id, rows)
        return StreamingResponse(
            stream_ndjson(anonymized.rows, chunk_size=500),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="{dataset_id}.ndjson"'},
        )

    bundle = exporter.export_dataset(
        dataset_id=dataset_id,
        export_format=export_format,
        filters=filters,
        requested_version=version,
        compress=compress,
    )

    if bundle.row_count > max_rows:
        return _delivery.error_response(dataset_id, 413, "Dataset exceeds max_rows limit")

    if precomputed:
        cached_file = _delivery.maybe_get_cached(dataset_id, bundle.metadata["version"], format, filters.model_dump(exclude_none=True))
        if cached_file:
            if cloud_link:
                return JSONResponse(
                    {
                        "dataset_id": dataset_id,
                        "version": bundle.metadata["version"],
                        "delivery": _delivery.cloud_storage_link(cached_file),
                        "metadata": bundle.metadata,
                    }
                )
            return _delivery.build_file_response(dataset_id, cached_file, bundle.filename, bundle.content_type)

        cached_path = _delivery.cache_bundle(
            dataset_id,
            version=bundle.metadata["version"],
            format_name=format,
            filters=filters.model_dump(exclude_none=True),
            bundle=bundle,
        )
        if cloud_link:
            return JSONResponse(
                {
                    "dataset_id": dataset_id,
                    "version": bundle.metadata["version"],
                    "delivery": _delivery.cloud_storage_link(cached_path),
                    "metadata": bundle.metadata,
                }
            )
        return _delivery.build_file_response(dataset_id, cached_path, bundle.filename, bundle.content_type)

    return _delivery.build_download_response(dataset_id, bundle)


@router.get("/monitoring/usage")
def open_data_monitoring(request: Request) -> dict[str, Any]:
    tier = _access_tier(request)
    if tier.name != KEY_TIER.name:
        raise HTTPException(status_code=403, detail="API key required for monitoring endpoint")
    return _delivery.monitoring_snapshot()
