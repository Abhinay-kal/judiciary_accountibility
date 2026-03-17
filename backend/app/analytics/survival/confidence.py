from __future__ import annotations


def curve_confidence(*, sample_size: int, event_count: int, mean_ci_width: float) -> float:
    sample_score = min(1.0, sample_size / 300.0)
    event_ratio = 0.0 if sample_size <= 0 else (event_count / sample_size)
    event_score = min(1.0, event_ratio / 0.6)
    ci_score = max(0.1, 1.0 - min(1.0, mean_ci_width))

    confidence = (0.45 * sample_score) + (0.30 * event_score) + (0.25 * ci_score)
    return max(0.0, min(1.0, round(confidence, 4)))
