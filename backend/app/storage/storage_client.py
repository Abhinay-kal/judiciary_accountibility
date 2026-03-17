from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class ObjectMetadata:
    key: str
    size_bytes: int
    tier: str
    compressed: bool
    updated_at: datetime


class StorageClient:
    """Local-first object storage wrapper.

    This class is intentionally cloud-agnostic. In environments without S3/GCS
    credentials it stores bytes on local disk. Replace internals with SDK calls
    while keeping this interface stable.
    """

    def __init__(self, base_dir: str = "raw_data/object_store") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir = self.base_dir / ".meta"
        self.meta_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        return self.base_dir / key

    def _meta_path_for(self, key: str) -> Path:
        safe_key = key.replace("/", "__")
        return self.meta_dir / f"{safe_key}.json"

    def put_bytes(self, key: str, payload: bytes, *, tier: str = "hot", compress: bool = False) -> str:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = gzip.compress(payload) if compress else payload
        path.write_bytes(content)
        self._write_meta(
            key,
            ObjectMetadata(
                key=key,
                size_bytes=len(content),
                tier=tier,
                compressed=compress,
                updated_at=datetime.now(timezone.utc),
            ),
        )
        return key

    def get_bytes(self, key: str) -> bytes:
        path = self._path_for(key)
        raw = path.read_bytes()
        meta = self.get_metadata(key)
        if meta and meta.compressed:
            return gzip.decompress(raw)
        return raw

    def exists(self, key: str) -> bool:
        return self._path_for(key).exists()

    def get_metadata(self, key: str) -> Optional[ObjectMetadata]:
        meta_path = self._meta_path_for(key)
        if not meta_path.exists():
            if self.exists(key):
                stat = self._path_for(key).stat()
                return ObjectMetadata(
                    key=key,
                    size_bytes=stat.st_size,
                    tier="hot",
                    compressed=False,
                    updated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                )
            return None
        payload = json.loads(meta_path.read_text())
        return ObjectMetadata(
            key=payload["key"],
            size_bytes=payload["size_bytes"],
            tier=payload["tier"],
            compressed=payload["compressed"],
            updated_at=datetime.fromisoformat(payload["updated_at"]),
        )

    def set_tier(self, key: str, tier: str, *, compress: bool | None = None) -> None:
        meta = self.get_metadata(key)
        if meta is None:
            raise FileNotFoundError(f"Object not found: {key}")
        path = self._path_for(key)
        content = path.read_bytes()

        should_compress = meta.compressed if compress is None else compress
        if should_compress and not meta.compressed:
            content = gzip.compress(content)
        elif not should_compress and meta.compressed:
            content = gzip.decompress(content)

        path.write_bytes(content)
        self._write_meta(
            key,
            ObjectMetadata(
                key=key,
                size_bytes=len(content),
                tier=tier,
                compressed=should_compress,
                updated_at=datetime.now(timezone.utc),
            ),
        )

    def restore_object(self, key: str) -> None:
        """Restore an archived object to hot tier for on-demand reads."""
        self.set_tier(key, tier="hot", compress=False)

    def _write_meta(self, key: str, meta: ObjectMetadata) -> None:
        self._meta_path_for(key).write_text(
            json.dumps(
                {
                    "key": meta.key,
                    "size_bytes": meta.size_bytes,
                    "tier": meta.tier,
                    "compressed": meta.compressed,
                    "updated_at": meta.updated_at.isoformat(),
                }
            )
        )
