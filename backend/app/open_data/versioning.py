from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.open_data.catalog import DatasetCatalog


@dataclass(slots=True)
class DatasetVersion:
    version: str
    published_at: datetime
    changelog: str


class VersionRegistry:
    """Simple in-memory version ledger for reproducible data exports."""

    def __init__(self, catalog: DatasetCatalog) -> None:
        self._versions: dict[str, list[DatasetVersion]] = {}
        for entry in catalog.list_entries():
            self._versions[entry.dataset_id] = [
                DatasetVersion(
                    version=entry.version,
                    published_at=entry.last_updated,
                    changelog="Initial public release",
                )
            ]

    def list_versions(self, dataset_id: str) -> list[DatasetVersion]:
        return list(self._versions.get(dataset_id, []))

    def resolve_version(self, dataset_id: str, requested_version: str | None) -> str:
        versions = self._versions.get(dataset_id, [])
        if not versions:
            raise ValueError(f"Unknown dataset '{dataset_id}'")

        if requested_version is None:
            return versions[-1].version

        for version in versions:
            if version.version == requested_version:
                return requested_version

        raise ValueError(f"Version '{requested_version}' is not available for dataset '{dataset_id}'")

    def add_version(self, dataset_id: str, version: str, changelog: str) -> DatasetVersion:
        record = DatasetVersion(
            version=version,
            published_at=datetime.now(timezone.utc),
            changelog=changelog,
        )
        self._versions.setdefault(dataset_id, []).append(record)
        return record
