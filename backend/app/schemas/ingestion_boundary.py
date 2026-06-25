from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


_DATE_PATTERN_DDMMYYYY = re.compile(r"(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})")
_DATE_PATTERN_YYYYMMDD = re.compile(r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})")


class RawHearingPayload(BaseModel):
    case_number: str
    filing_year: int
    hearing_date: date
    raw_bench_string: str
    raw_outcome_text: str

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    @field_validator("hearing_date", mode="before")
    @classmethod
    def coerce_hearing_date(cls, value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if not isinstance(value, str):
            raise ValueError("hearing_date must be a string/date/datetime")

        candidate = value.strip()
        if not candidate:
            raise ValueError("hearing_date is empty")

        direct_formats = ("%Y-%m-%d", "%d/%m/%Y")
        for fmt in direct_formats:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue

        match = _DATE_PATTERN_YYYYMMDD.search(candidate)
        if match is not None:
            return date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            )

        match = _DATE_PATTERN_DDMMYYYY.search(candidate)
        if match is not None:
            return date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            )

        raise ValueError(f"Unparsable hearing_date: {value!r}")