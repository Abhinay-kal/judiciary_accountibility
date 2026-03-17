from app.ingestion.fetcher import DeltaFetcher
from app.ingestion.lifecycle import LifecycleManager, LifecyclePolicy
from app.ingestion.parser_minimal import parse_minimal
from app.ingestion.models import IngestionSource
from app.storage.storage_client import StorageClient


class DummyResp:
    def __init__(self, status_code=200, headers=None, content=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content


def test_minimal_fetch_parse_store_lifecycle(monkeypatch, tmp_path):
    source = IngestionSource(
        id=1,
        source_name="demo",
        source_type="HTML",
        base_url="https://example.com/data",
        expected_update_interval_minutes=60,
        config_json={},
    )
    fetcher = DeltaFetcher()

    html = b"<html><body>Case ID: X-1 Date: 01/01/2025 Bench: A Outcome: Listed</body></html>"

    def fake_request(method, url, headers=None, timeout=30):
        if method == "HEAD":
            return DummyResp(status_code=200, headers={"ETag": '"v1"'})
        return DummyResp(status_code=200, headers={"ETag": '"v1"'}, content=html)

    monkeypatch.setattr(fetcher.session, "request", fake_request)
    monkeypatch.setattr(fetcher, "_respect_robots", lambda *_: None)
    monkeypatch.setattr(fetcher, "_enforce_rate_limit", lambda *_: None)

    fetched = fetcher.fetch(source)
    parsed = parse_minimal(fetched.body, "text/html")

    storage = StorageClient(base_dir=str(tmp_path / "store"))
    key = "raw/ab/test-object"
    storage.put_bytes(key, fetched.body, tier="hot")

    manager = LifecycleManager(storage, LifecyclePolicy(hot_days=0, warm_days=0))
    moved = manager.apply_rules([key])

    assert fetched.not_modified is False
    assert parsed.case_id == "X-1"
    assert moved["warm"] + moved["cold"] >= 1
