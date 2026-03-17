from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from app.open_data.exporter import ExportBundle


@dataclass(slots=True)
class CachedExport:
    path: Path
    expires_at: datetime
    size_bytes: int


class DeliveryManager:
    def __init__(self, base_dir: Path | None = None, cache_ttl_minutes: int = 30) -> None:
        self.base_dir = base_dir or Path("raw_data/open_data_exports")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.cache: dict[str, CachedExport] = {}

        self.download_count: dict[str, int] = {}
        self.error_count: dict[str, int] = {}
        self.bytes_served: dict[str, int] = {}

    def _cache_key(self, dataset_id: str, version: str, format_name: str, filter_fingerprint: str) -> str:
        key = f"{dataset_id}:{version}:{format_name}:{filter_fingerprint}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _fingerprint_filters(self, filters: dict) -> str:
        if not filters:
            return "none"
        key = "|".join(f"{k}={v}" for k, v in sorted(filters.items()))
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def maybe_get_cached(
        self,
        dataset_id: str,
        version: str,
        format_name: str,
        filters: dict,
    ) -> Path | None:
        key = self._cache_key(dataset_id, version, format_name, self._fingerprint_filters(filters))
        cached = self.cache.get(key)
        if cached is None:
            return None
        if cached.expires_at < datetime.now(timezone.utc) or not cached.path.exists():
            self.cache.pop(key, None)
            return None
        return cached.path

    def cache_bundle(
        self,
        dataset_id: str,
        version: str,
        format_name: str,
        filters: dict,
        bundle: ExportBundle,
    ) -> Path:
        key = self._cache_key(dataset_id, version, format_name, self._fingerprint_filters(filters))
        target = self.base_dir / bundle.filename
        target.write_bytes(bundle.payload)
        self.cache[key] = CachedExport(
            path=target,
            expires_at=datetime.now(timezone.utc) + self.cache_ttl,
            size_bytes=len(bundle.payload),
        )
        return target

    def build_download_response(self, dataset_id: str, bundle: ExportBundle):
        self.download_count[dataset_id] = self.download_count.get(dataset_id, 0) + 1
        self.bytes_served[dataset_id] = self.bytes_served.get(dataset_id, 0) + len(bundle.payload)

        return StreamingResponse(
            iter([bundle.payload]),
            media_type=bundle.content_type,
            headers={"Content-Disposition": f'attachment; filename="{bundle.filename}"'},
        )

    def build_file_response(self, dataset_id: str, file_path: Path, filename: str, content_type: str):
        self.download_count[dataset_id] = self.download_count.get(dataset_id, 0) + 1
        self.bytes_served[dataset_id] = self.bytes_served.get(dataset_id, 0) + file_path.stat().st_size
        return FileResponse(
            path=file_path,
            media_type=content_type,
            filename=filename,
        )

    def cloud_storage_link(self, file_path: Path, expires_minutes: int = 60) -> dict:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        token = hashlib.sha1(f"{file_path}:{expires_at.isoformat()}".encode("utf-8")).hexdigest()[:12]
        return {
            "url": f"https://example-bucket.local/{file_path.name}?token={token}",
            "expires_at": expires_at.isoformat(),
            "provider": "mock-s3",
        }

    def error_response(self, dataset_id: str, status_code: int, detail: str) -> JSONResponse:
        self.error_count[dataset_id] = self.error_count.get(dataset_id, 0) + 1
        return JSONResponse(status_code=status_code, content={"detail": detail})

    def monitoring_snapshot(self) -> dict:
        dataset_ids = sorted(set(self.download_count) | set(self.error_count) | set(self.bytes_served))
        return {
            "downloads": {dataset_id: self.download_count.get(dataset_id, 0) for dataset_id in dataset_ids},
            "errors": {dataset_id: self.error_count.get(dataset_id, 0) for dataset_id in dataset_ids},
            "bytes_served": {dataset_id: self.bytes_served.get(dataset_id, 0) for dataset_id in dataset_ids},
            "popular_datasets": sorted(
                [{"dataset_id": dataset_id, "downloads": self.download_count.get(dataset_id, 0)} for dataset_id in dataset_ids],
                key=lambda row: row["downloads"],
                reverse=True,
            ),
            "cache_items": len(self.cache),
        }
