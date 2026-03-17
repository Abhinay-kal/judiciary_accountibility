from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.storage.storage_client import StorageClient
from app.ingestion.metrics import ARCHIVES_MOVED


@dataclass
class LifecyclePolicy:
    hot_days: int = 30
    warm_days: int = 90


class LifecycleManager:
    def __init__(self, storage: StorageClient, policy: LifecyclePolicy) -> None:
        self.storage = storage
        self.policy = policy

    def desired_tier_for_age(self, age_days: int) -> tuple[str, bool]:
        if age_days < self.policy.hot_days:
            return ("hot", False)
        if age_days < self.policy.warm_days:
            return ("warm", True)
        return ("cold", True)

    def apply_rules(self, object_keys: Iterable[str], now: datetime | None = None) -> dict[str, int]:
        now = now or datetime.now(timezone.utc)
        moved = {"hot": 0, "warm": 0, "cold": 0}
        for key in object_keys:
            meta = self.storage.get_metadata(key)
            if not meta:
                continue
            age_days = max(0, int((now - meta.updated_at).total_seconds() // 86400))
            target_tier, should_compress = self.desired_tier_for_age(age_days)
            if meta.tier != target_tier or meta.compressed != should_compress:
                self.storage.set_tier(key, target_tier, compress=should_compress)
                moved[target_tier] += 1
                ARCHIVES_MOVED.labels(tier=target_tier).inc()
        return moved

    def restore_archived(self, object_key: str) -> None:
        self.storage.restore_object(object_key)
