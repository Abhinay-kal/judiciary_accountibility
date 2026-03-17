"""Volume-anomaly detection for ingestion runs.

Compares the *current* record count against a rolling window of
historical counts from recent :class:`~app.ingestion.models.IngestionRun`
rows to flag unexpected spikes or drops.

Algorithm
---------
1. Compute the rolling median of the last *N* historical counts
   (default ``window=10``).
2. Calculate the deviation ratio:
   ``deviation = |current - median| / max(median, 1)``
3. If ``current > median * (1 + threshold)`` → ``direction="spike"``.
4. If ``current < median * (1 - threshold)`` → ``direction="drop"``.
5. Otherwise no anomaly.

Usage::

    from app.ingestion.detectors.volume_anomaly import VolumeAnomalyDetector

    detector = VolumeAnomalyDetector(threshold=0.50)
    result = detector.check(current_count=120, historical_counts=[100, 98, 105, 102])
    if result.is_anomaly:
        print(result.direction, result.deviation_ratio)
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Sequence


@dataclass
class VolumeAnomalyResult:
    is_anomaly: bool
    direction: str  # "spike" | "drop" | "none"
    deviation_ratio: float
    rolling_median: float
    window_size: int


class VolumeAnomalyDetector:
    """Stateless rolling-median anomaly detector."""

    def __init__(self, threshold: float = 0.50, window: int = 10) -> None:
        self._threshold = threshold
        self._window = window

    def check(
        self,
        current_count: int,
        historical_counts: Sequence[int],
    ) -> VolumeAnomalyResult:
        """Evaluate whether *current_count* is anomalous.

        Parameters
        ----------
        current_count:
            Number of records fetched in the current run.
        historical_counts:
            Sequence of record counts from past successful runs,
            ordered oldest-first.  Only the last :attr:`_window`
            values are used.

        Returns
        -------
        VolumeAnomalyResult
        """
        # Keep only the most recent window of data
        window_counts = list(historical_counts[-self._window :])

        if not window_counts:
            # No history available — cannot make a judgement
            return VolumeAnomalyResult(
                is_anomaly=False,
                direction="none",
                deviation_ratio=0.0,
                rolling_median=float(current_count),
                window_size=0,
            )

        if len(window_counts) == 1:
            median = float(window_counts[0])
        else:
            median = statistics.median(window_counts)

        if median == 0:
            # Guard against division by zero when all history is zero
            is_anomaly = current_count > 0
            direction = "spike" if is_anomaly else "none"
            return VolumeAnomalyResult(
                is_anomaly=is_anomaly,
                direction=direction,
                deviation_ratio=1.0 if is_anomaly else 0.0,
                rolling_median=0.0,
                window_size=len(window_counts),
            )

        deviation = abs(current_count - median) / median

        if current_count > median * (1 + self._threshold):
            direction = "spike"
            is_anomaly = True
        elif current_count < median * (1 - self._threshold):
            direction = "drop"
            is_anomaly = True
        else:
            direction = "none"
            is_anomaly = False

        return VolumeAnomalyResult(
            is_anomaly=is_anomaly,
            direction=direction,
            deviation_ratio=round(deviation, 4),
            rolling_median=round(median, 2),
            window_size=len(window_counts),
        )

    def detect_spike_drop(
        self,
        current_count: int,
        historical_counts: Sequence[int],
    ) -> dict:
        """Convenience wrapper used by alerts/monitoring workflows."""
        result = self.check(current_count=current_count, historical_counts=historical_counts)
        return {
            "is_anomaly": result.is_anomaly,
            "direction": result.direction,
            "deviation_ratio": result.deviation_ratio,
            "rolling_median": result.rolling_median,
            "window_size": result.window_size,
        }
