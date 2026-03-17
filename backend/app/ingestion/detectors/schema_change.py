"""Schema-change detection for ingestion payloads.

Detects structural drift between the *current* payload and a stored
*baseline snapshot*, for both HTML and JSON/dict payloads.

HTML detection
--------------
* Builds a DOM tree fingerprint (depth, tag-name frequency map).
* Checks presence of configurable required CSS selectors.
* Runs optional text-pattern regex checks.

JSON detection
--------------
* Compares the top-level key set (added / removed keys).
* Validates per-key data types against the baseline.

If the fraction of mismatches exceeds
:attr:`~app.ingestion.config.IngestionSettings.ingest_schema_mismatch_threshold`
the result is ``is_changed=True`` with a confidence penalty applied by
:mod:`app.ingestion.pipeline`.

Usage::

    from app.ingestion.detectors.schema_change import SchemaChangeDetector

    detector = SchemaChangeDetector(source_config=source.config_json)
    result = detector.check_html(content_bytes, baseline_snapshot)
    if result.is_changed:
        ...
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class SchemaCheckResult:
    is_changed: bool
    mismatch_fraction: float  # 0.0 to 1.0
    details: dict[str, Any] = field(default_factory=dict)
    new_snapshot: Optional[dict] = None


# ---------------------------------------------------------------------------
# SchemaChangeDetector
# ---------------------------------------------------------------------------


class SchemaChangeDetector:
    """Stateless detector — cheap to instantiate per run."""

    def __init__(
        self,
        threshold: float = 0.20,
        source_config: Optional[dict] = None,
    ) -> None:
        self._threshold = threshold
        cfg = source_config or {}
        # CSS selectors that must be present in the HTML
        self._required_selectors: list[str] = cfg.get("required_selectors", [])
        # Regex patterns that must match somewhere in the HTML text
        self._required_patterns: list[str] = cfg.get("required_patterns", [])

    # ------------------------------------------------------------------
    # HTML detection
    # ------------------------------------------------------------------

    def check_html(
        self,
        content: bytes,
        baseline: Optional[dict],
    ) -> SchemaCheckResult:
        """Detect structural drift in an HTML payload.

        Parameters
        ----------
        content:
            Raw HTML bytes.
        baseline:
            Previously stored snapshot dict (or None → first run, no drift).

        Returns
        -------
        SchemaCheckResult
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("beautifulsoup4 not available — schema check skipped")
            return SchemaCheckResult(is_changed=False, mismatch_fraction=0.0)

        soup = BeautifulSoup(content, "lxml")
        current_snapshot = self._html_snapshot(soup)

        if baseline is None:
            # First run — record baseline, no change detected
            return SchemaCheckResult(
                is_changed=False,
                mismatch_fraction=0.0,
                details={"first_run": True},
                new_snapshot=current_snapshot,
            )

        details: dict[str, Any] = {}
        total_checks = 0
        failures = 0

        # 1. Tag-frequency fingerprint comparison
        baseline_tags = baseline.get("tag_freq", {})
        current_tags = current_snapshot.get("tag_freq", {})
        all_tags = set(baseline_tags) | set(current_tags)
        if all_tags:
            tag_changed = sum(
                1
                for t in all_tags
                if abs(baseline_tags.get(t, 0) - current_tags.get(t, 0))
                > max(2, 0.3 * baseline_tags.get(t, 1))
            )
            tag_fraction = tag_changed / len(all_tags)
            total_checks += 1
            if tag_fraction > self._threshold:
                failures += 1
            details["tag_drift_fraction"] = round(tag_fraction, 4)

        # 2. Required selectors
        for selector in self._required_selectors:
            total_checks += 1
            if not soup.select(selector):
                failures += 1
                details.setdefault("missing_selectors", []).append(selector)

        # 3. Required patterns
        html_text = soup.get_text()
        for pattern in self._required_patterns:
            total_checks += 1
            if not re.search(pattern, html_text, re.IGNORECASE | re.DOTALL):
                failures += 1
                details.setdefault("missing_patterns", []).append(pattern)

        # 4. DOM depth comparison
        baseline_depth = baseline.get("avg_depth", 0)
        current_depth = current_snapshot.get("avg_depth", 0)
        if baseline_depth > 0:
            depth_delta = abs(current_depth - baseline_depth) / baseline_depth
            total_checks += 1
            if depth_delta > self._threshold:
                failures += 1
            details["depth_delta_fraction"] = round(depth_delta, 4)

        # 5. Structural checksum
        if baseline.get("content_hash") != current_snapshot.get("content_hash"):
            details["content_hash_changed"] = True

        mismatch = failures / max(total_checks, 1)
        is_changed = mismatch >= self._threshold

        return SchemaCheckResult(
            is_changed=is_changed,
            mismatch_fraction=round(mismatch, 4),
            details=details,
            new_snapshot=current_snapshot,
        )

    def dom_fingerprint(self, content: bytes) -> dict[str, Any]:
        """Compute a compact DOM fingerprint for canary regression baselines."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(content, "lxml")
        snapshot = self._html_snapshot(soup)
        return {
            "node_count": snapshot.get("node_count", 0),
            "avg_depth": snapshot.get("avg_depth", 0),
            "tag_freq": snapshot.get("tag_freq", {}),
            "content_hash": snapshot.get("content_hash"),
        }

    def schema_drift_score(self, baseline: dict, current: dict) -> float:
        """Return drift score in [0,1] using tag and depth deltas."""
        baseline_tags = baseline.get("tag_freq", {})
        current_tags = current.get("tag_freq", {})
        all_tags = set(baseline_tags) | set(current_tags)
        if not all_tags:
            return 0.0
        tag_delta = sum(
            abs(int(baseline_tags.get(tag, 0)) - int(current_tags.get(tag, 0)))
            for tag in all_tags
        ) / max(sum(int(v) for v in baseline_tags.values()), 1)

        base_depth = float(baseline.get("avg_depth", 0) or 0)
        cur_depth = float(current.get("avg_depth", 0) or 0)
        depth_delta = 0.0 if base_depth <= 0 else abs(cur_depth - base_depth) / base_depth
        return round(min(1.0, (tag_delta * 0.7) + (depth_delta * 0.3)), 4)

    # ------------------------------------------------------------------
    # JSON detection
    # ------------------------------------------------------------------

    def check_json(
        self,
        payload: Any,
        baseline: Optional[dict],
    ) -> SchemaCheckResult:
        """Detect structural drift in a JSON/dict payload.

        Operates on the top-level key set and per-key type signatures.
        For list payloads the first element is inspected.
        """
        if isinstance(payload, list):
            sample = payload[0] if payload else {}
        elif isinstance(payload, dict):
            sample = payload
        else:
            return SchemaCheckResult(is_changed=False, mismatch_fraction=0.0)

        current_snapshot = self._json_snapshot(sample)

        if baseline is None:
            return SchemaCheckResult(
                is_changed=False,
                mismatch_fraction=0.0,
                details={"first_run": True},
                new_snapshot=current_snapshot,
            )

        baseline_keys = set(baseline.get("keys", []))
        current_keys = set(current_snapshot.get("keys", []))

        added = current_keys - baseline_keys
        removed = baseline_keys - current_keys
        all_keys = baseline_keys | current_keys
        key_mismatch = (len(added) + len(removed)) / max(len(all_keys), 1)

        # Type drift
        baseline_types = baseline.get("key_types", {})
        current_types = current_snapshot.get("key_types", {})
        type_mismatches = [
            k
            for k in baseline_keys & current_keys
            if baseline_types.get(k) != current_types.get(k)
        ]
        type_mismatch = len(type_mismatches) / max(len(baseline_keys), 1)

        mismatch = max(key_mismatch, type_mismatch)
        is_changed = mismatch >= self._threshold

        details = {
            "added_keys": sorted(added),
            "removed_keys": sorted(removed),
            "type_mismatch_keys": type_mismatches,
            "key_mismatch_fraction": round(key_mismatch, 4),
            "type_mismatch_fraction": round(type_mismatch, 4),
        }
        return SchemaCheckResult(
            is_changed=is_changed,
            mismatch_fraction=round(mismatch, 4),
            details=details,
            new_snapshot=current_snapshot,
        )

    # ------------------------------------------------------------------
    # Private snapshot builders
    # ------------------------------------------------------------------

    @staticmethod
    def _html_snapshot(soup: Any) -> dict:
        """Build a compact fingerprint of an HTML document."""
        tags: dict[str, int] = {}
        total_depth = 0
        node_count = 0
        for tag in soup.find_all(True):
            name = tag.name
            tags[name] = tags.get(name, 0) + 1
            # Estimate depth by counting ancestor tags
            depth = len(list(tag.parents))
            total_depth += depth
            node_count += 1
        avg_depth = round(total_depth / max(node_count, 1), 2)
        text_hash = hashlib.md5(soup.get_text().encode("utf-8", "replace")).hexdigest()
        return {
            "tag_freq": tags,
            "avg_depth": avg_depth,
            "node_count": node_count,
            "content_hash": text_hash,
        }

    @staticmethod
    def _json_snapshot(record: dict) -> dict:
        """Build a key-set + type-map fingerprint for a dict."""
        key_types = {k: type(v).__name__ for k, v in record.items()}
        return {
            "keys": sorted(record.keys()),
            "key_types": key_types,
        }
