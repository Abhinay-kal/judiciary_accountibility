from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.api.routes import open_data
from app.main import app
from app.open_data.anonymization import anonymize_rows
from app.open_data.catalog import DEFAULT_DATASET_CATALOG
from app.open_data.filters import ExportFilters, apply_dict_filters
from app.open_data.formats import ExportFormat, serialize_rows, stream_ndjson
from app.open_data.versioning import VersionRegistry


def test_catalog_has_required_datasets() -> None:
    dataset_ids = {entry.dataset_id for entry in DEFAULT_DATASET_CATALOG.list_entries()}
    assert {
        "case_metadata",
        "hearing_timelines",
        "court_statistics",
        "judge_metrics_aggregated",
        "delay_distributions",
        "flagged_cases",
        "external_coverage_links",
        "derived_analytics",
    }.issubset(dataset_ids)


def test_filtering_logic() -> None:
    rows = [
        {"state": "Delhi", "case_type": "Civil", "status": "pending", "importance_score": 0.9},
        {"state": "Kerala", "case_type": "Criminal", "status": "disposed", "importance_score": 0.4},
    ]
    filters = ExportFilters(state="Delhi", case_type="Civil", status="pending", min_importance_score=0.7)
    filtered = apply_dict_filters(rows, filters)
    assert len(filtered) == 1
    assert filtered[0]["state"] == "Delhi"


def test_format_validity_csv_json_ndjson() -> None:
    rows = [{"case_id": 1, "state": "Delhi"}]

    csv_out = serialize_rows(rows, ExportFormat.CSV)
    assert csv_out.content_type == "text/csv"
    assert b"case_id" in csv_out.payload

    json_out = serialize_rows(rows, ExportFormat.JSON)
    assert json_out.content_type == "application/json"
    assert b'"case_id"' in json_out.payload

    ndjson_out = serialize_rows(rows, ExportFormat.NDJSON)
    assert ndjson_out.content_type == "application/x-ndjson"
    assert ndjson_out.payload.endswith(b"\n")


def test_version_consistency() -> None:
    registry = VersionRegistry(DEFAULT_DATASET_CATALOG)
    latest = registry.resolve_version("case_metadata", None)
    explicit = registry.resolve_version("case_metadata", latest)
    assert latest == explicit

    with pytest.raises(ValueError):
        registry.resolve_version("case_metadata", "9.9.9")


def test_anonymization_rules() -> None:
    rows = [
        {
            "case_id": 101,
            "requester_contact": "+919999999999",
            "email": "user@example.com",
            "public_note": "Contact me at user@example.com",
            "source_url": "https://example.org/case/101",
        }
    ]
    result = anonymize_rows("case_metadata", rows)
    assert result.rows[0]["requester_contact"] == "[masked]"
    assert result.rows[0]["email"] == "[masked]"
    assert result.masked_fields >= 2


def test_large_dataset_streaming() -> None:
    rows = ({"id": idx, "value": idx * 2} for idx in range(1200))
    chunks = list(stream_ndjson(rows, chunk_size=250))
    assert len(chunks) >= 4
    total_lines = sum(chunk.decode("utf-8").count("\n") for chunk in chunks)
    assert total_lines == 1200


@dataclass
class _FakeBundle:
    filename: str
    payload: bytes
    content_type: str
    metadata: dict
    row_count: int


class _FakeExporter:
    def __init__(self, _db) -> None:
        pass

    class versions:  # noqa: D401
        @staticmethod
        def resolve_version(dataset_id: str, requested_version: str | None) -> str:
            return requested_version or "1.0.0"

    def _fetch_rows(self, dataset_id: str, filters: ExportFilters):
        return [{"dataset_id": dataset_id, "state": filters.state or "all"}]

    def export_dataset(self, dataset_id: str, export_format: ExportFormat, filters: ExportFilters, requested_version=None, compress=False):
        _ = export_format
        _ = filters
        _ = compress
        return _FakeBundle(
            filename=f"{dataset_id}.json",
            payload=b"[{\"ok\": true}]",
            content_type="application/json",
            metadata={"version": requested_version or "1.0.0"},
            row_count=1,
        )


def _override_get_db():
    yield None


def test_open_data_api_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(open_data, "OpenDataExporter", _FakeExporter)
    app.dependency_overrides[open_data.get_db] = _override_get_db

    client = TestClient(app)

    catalog_resp = client.get("/api/v1/datasets")
    assert catalog_resp.status_code == 200
    assert catalog_resp.json()["count"] >= 8

    schema_resp = client.get("/api/v1/datasets/case_metadata/schema")
    assert schema_resp.status_code == 200
    assert "fields" in schema_resp.json()

    version_resp = client.get("/api/v1/datasets/case_metadata/v/1.0.0")
    assert version_resp.status_code == 200
    assert version_resp.json()["version"] == "1.0.0"

    download_resp = client.get("/api/v1/datasets/case_metadata/download?format=json&max_rows=1000")
    assert download_resp.status_code == 200

    blocked_resp = client.get("/api/v1/datasets/case_metadata/download?format=json&max_rows=999999")
    assert blocked_resp.status_code in {403, 422}

    app.dependency_overrides.clear()
