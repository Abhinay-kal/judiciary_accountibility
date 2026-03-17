from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InvalidationEvent:
    reason: str
    entity_type: str | None = None
    entity_id: str | None = None


class InvalidationRegistry:
    def __init__(self) -> None:
        self._resource_map = {
            "CASE_UPDATED": ["case", "cases", "investigation_page", "stats_court", "stats_judge"],
            "HEARING_ADDED": ["case", "cases", "case_timeline", "stats_court", "stats_judge"],
            "INGESTION_COMPLETED": [
                "case",
                "cases",
                "case_timeline",
                "courts",
                "judges",
                "judge",
                "judge_stats",
                "stats_court",
                "stats_judge",
                "flags",
                "investigation_page",
            ],
            "ANALYTICS_RECOMPUTED": ["cases", "case", "stats_court", "stats_judge", "survival_curves"],
            "VERSION_CHANGED": ["case", "cases", "investigation_page", "survival_curves"],
            "MANUAL_OVERRIDE": ["case", "cases", "stats_court", "stats_judge", "investigation_page"],
        }

    def resources_for_event(self, event: InvalidationEvent) -> list[str]:
        return self._resource_map.get(event.reason, ["case", "cases"])
