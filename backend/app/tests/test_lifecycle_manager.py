from datetime import datetime, timedelta, timezone

from app.ingestion.lifecycle import LifecycleManager, LifecyclePolicy
from app.storage.storage_client import StorageClient


def test_lifecycle_moves_tiers(tmp_path):
    storage = StorageClient(base_dir=str(tmp_path / "store"))
    storage.put_bytes("raw/aa/object1", b"x" * 100, tier="hot")

    manager = LifecycleManager(storage, LifecyclePolicy(hot_days=1, warm_days=2))

    # Simulate old object by rewriting metadata timestamp
    meta = storage.get_metadata("raw/aa/object1")
    assert meta is not None
    old = datetime.now(timezone.utc) - timedelta(days=5)
    storage._write_meta(
        "raw/aa/object1",
        meta.__class__(
            key=meta.key,
            size_bytes=meta.size_bytes,
            tier=meta.tier,
            compressed=meta.compressed,
            updated_at=old,
        ),
    )

    moved = manager.apply_rules(["raw/aa/object1"])
    assert moved["cold"] == 1
    assert storage.get_metadata("raw/aa/object1").tier == "cold"
