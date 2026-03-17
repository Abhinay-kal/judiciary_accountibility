import gzip

import pytest

from app.ingestion.parser_minimal import parse_minimal


SAMPLES = [
    f"Case ID: C-{i}\nDate: 01/01/202{i%10}\nBench: Bench {i}\nOutcome: Listed" for i in range(10)
]


@pytest.mark.parametrize("sample", SAMPLES)
def test_parser_minimal_html_samples(sample):
    payload = f"<html><body><pre>{sample}</pre><a href='order.pdf'>Order</a></body></html>".encode()
    result = parse_minimal(payload, "text/html")
    assert result.case_id is not None
    assert result.hearing_date is not None
    assert result.bench is not None
    assert result.outcome_text is not None
    assert result.order_pdf_url == "order.pdf"
    assert result.parser_confidence >= 0.75
    assert gzip.decompress(result.full_text_gzip)
