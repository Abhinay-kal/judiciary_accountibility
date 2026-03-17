from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.analytics.delay.trends import time_weighted_median


def test_time_weighted_median_prefers_recent_values():
    now = datetime.now(timezone.utc)
    values = [100.0, 100.0, 400.0]
    timestamps = [now - timedelta(days=1500), now - timedelta(days=1200), now - timedelta(days=20)]

    weighted = time_weighted_median(values, timestamps, half_life_days=365)

    assert weighted >= 100.0
