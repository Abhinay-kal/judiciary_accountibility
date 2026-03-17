from app.ingestion.canary import run_canary_for_source
from app.ingestion.models import IngestionSource


class DummyDB:
    def flush(self):
        return None


def test_canary_detects_schema_break():
    source = IngestionSource(
        id=1,
        source_name="demo",
        source_type="HTML",
        base_url="https://example.com",
        config_json={"required_selectors": [".must-exist"]},
        schema_baseline={"tag_freq": {"div": 10}, "avg_depth": 3, "node_count": 10, "content_hash": "x"},
    )

    payload = b"<html><body><span>changed structure</span></body></html>"
    result = run_canary_for_source(
        DummyDB(),
        source=source,
        payload=payload,
        content_type="text/html",
        threshold=0.2,
    )
    assert result.is_schema_drift is True
    assert source.config_json.get("aggressive_parsing_paused") is True
