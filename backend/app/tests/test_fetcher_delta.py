from types import SimpleNamespace

from app.ingestion.fetcher import DeltaFetcher
from app.ingestion.models import IngestionSource


class DummyResp:
    def __init__(self, status_code=200, headers=None, content=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content


def test_head_304_short_circuit(monkeypatch):
    source = IngestionSource(
        id=1,
        source_name="demo",
        source_type="HTML",
        base_url="https://example.com/data",
        config_json={"etag": '"abc"'},
        expected_update_interval_minutes=60,
    )
    fetcher = DeltaFetcher()

    calls = []

    def fake_request(method, url, headers=None, timeout=30):
        calls.append(method)
        if method == "HEAD":
            return DummyResp(status_code=304, headers={"ETag": '"abc"'})
        return DummyResp(status_code=200, content=b"unexpected")

    monkeypatch.setattr(fetcher.session, "request", fake_request)
    monkeypatch.setattr(fetcher, "_respect_robots", lambda *_: None)
    monkeypatch.setattr(fetcher, "_enforce_rate_limit", lambda *_: None)

    result = fetcher.fetch(source)
    assert result.not_modified is True
    assert result.body == b""
    assert calls == ["HEAD"]


def test_etag_match_without_304(monkeypatch):
    source = IngestionSource(
        id=1,
        source_name="demo",
        source_type="HTML",
        base_url="https://example.com/data",
        config_json={"etag": '"abc"'},
        expected_update_interval_minutes=60,
    )
    fetcher = DeltaFetcher()

    def fake_request(method, url, headers=None, timeout=30):
        if method == "HEAD":
            return DummyResp(status_code=200, headers={"ETag": '"abc"'})
        raise AssertionError("GET should not be called")

    monkeypatch.setattr(fetcher.session, "request", fake_request)
    monkeypatch.setattr(fetcher, "_respect_robots", lambda *_: None)
    monkeypatch.setattr(fetcher, "_enforce_rate_limit", lambda *_: None)

    result = fetcher.fetch(source)
    assert result.not_modified is True
    assert result.strategy == "head_etag_match"
