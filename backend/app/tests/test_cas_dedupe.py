from app.ingestion import cas
from app.storage.storage_client import StorageClient


class FakeSession:
    def __init__(self):
        self.rows = []
        self.next_id = 1

    def add(self, row):
        row.payload_id = self.next_id
        self.next_id += 1
        self.rows.append(row)

    def flush(self):
        return None


def test_cas_deduplicates(tmp_path):
    storage = StorageClient(base_dir=str(tmp_path / "store"))
    db = FakeSession()

    def lookup(_db, checksum):
        for row in db.rows:
            if row.checksum == checksum:
                return row
        return None

    cas.lookup_by_checksum = lookup

    first = cas.store_payload(
        db,
        storage,
        payload=b"same-content",
        media_type="text/html",
        source_id=1,
        ingestion_run_id=1,
    )
    second = cas.store_payload(
        db,
        storage,
        payload=b"same-content",
        media_type="text/html",
        source_id=1,
        ingestion_run_id=2,
    )

    assert first.is_duplicate is False
    assert second.is_duplicate is True
    assert first.storage_ref == second.storage_ref
