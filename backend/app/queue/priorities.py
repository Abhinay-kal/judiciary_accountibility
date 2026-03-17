from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PriorityLevels:
    high: int = 9
    normal: int = 5
    low: int = 1


PRIORITIES = PriorityLevels()


def clamp_priority(value: int | None, default: int = PRIORITIES.normal) -> int:
    if value is None:
        return default
    return max(PRIORITIES.low, min(PRIORITIES.high, int(value)))
