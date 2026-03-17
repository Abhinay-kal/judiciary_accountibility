from __future__ import annotations

import csv
import gzip
import io
import json
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ExportFormat(str, Enum):
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"
    NDJSON = "ndjson"


@dataclass(slots=True)
class FormatOutput:
    content_type: str
    file_extension: str
    payload: bytes


def _to_csv_bytes(rows: list[dict]) -> bytes:
    if not rows:
        return b""

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _to_json_bytes(rows: list[dict]) -> bytes:
    return json.dumps(rows, default=str, ensure_ascii=True).encode("utf-8")


def _to_ndjson_bytes(rows: list[dict]) -> bytes:
    chunks = [json.dumps(row, default=str, ensure_ascii=True) for row in rows]
    if not chunks:
        return b""
    return ("\n".join(chunks) + "\n").encode("utf-8")


def _to_parquet_bytes(rows: list[dict]) -> bytes:
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise ValueError("Parquet export requires pandas") from exc

    if not rows:
        df = pd.DataFrame()
    else:
        df = pd.DataFrame(rows)

    out = io.BytesIO()
    try:
        df.to_parquet(out, index=False)
    except Exception as exc:  # pragma: no cover
        raise ValueError("Parquet export requires pyarrow or fastparquet") from exc

    return out.getvalue()


def serialize_rows(rows: list[dict], export_format: ExportFormat, compress: bool = False) -> FormatOutput:
    if export_format == ExportFormat.CSV:
        payload = _to_csv_bytes(rows)
        content_type = "text/csv"
        extension = "csv"
    elif export_format == ExportFormat.JSON:
        payload = _to_json_bytes(rows)
        content_type = "application/json"
        extension = "json"
    elif export_format == ExportFormat.NDJSON:
        payload = _to_ndjson_bytes(rows)
        content_type = "application/x-ndjson"
        extension = "ndjson"
    elif export_format == ExportFormat.PARQUET:
        payload = _to_parquet_bytes(rows)
        content_type = "application/octet-stream"
        extension = "parquet"
    else:  # pragma: no cover
        raise ValueError(f"Unsupported format: {export_format}")

    if compress:
        payload = gzip.compress(payload)
        content_type = "application/gzip"
        extension = f"{extension}.gz"

    return FormatOutput(content_type=content_type, file_extension=extension, payload=payload)


def stream_ndjson(rows: Iterable[dict], chunk_size: int = 500) -> Iterable[bytes]:
    chunk: list[str] = []
    for row in rows:
        chunk.append(json.dumps(row, default=str, ensure_ascii=True))
        if len(chunk) >= chunk_size:
            yield ("\n".join(chunk) + "\n").encode("utf-8")
            chunk = []
    if chunk:
        yield ("\n".join(chunk) + "\n").encode("utf-8")
