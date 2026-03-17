from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Case, CaseMediaMention, CasePartyLink, Flag, ImportanceAuditLog, ImportanceConfig


@dataclass
class ImportanceScoreResult:
    score: float
    confidence: float
    components: dict[str, Any]
    provenance: dict[str, Any]
    explanation: str


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class CaseImportanceScorer:
    DEFAULT_WEIGHTS = {
        "w_politician": 0.30,
        "w_corruption": 0.20,
        "w_case_type": 0.15,
        "w_media": 0.15,
        "w_monetary": 0.10,
        "w_priority": 0.07,
        "w_historical": 0.03,
    }

    DEFAULT_CASE_TYPE_MAP = {
        "criminal_corruption": 1.0,
        "pil": 0.9,
        "criminal": 0.7,
        "civil_land": 0.2,
        "tax": 0.4,
        "default": 0.3,
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self._keywords = self._load_keywords()

    def score_case(self, case: Case, *, fast_pass: bool = False) -> ImportanceScoreResult:
        cfg = self._resolve_config()
        weights = cfg["weights"]
        case_type_map = cfg["case_type_map"]
        min_conf = cfg["min_confidence"]
        decay_lambda = cfg["media_decay_lambda"]
        monetary_cap = cfg["monetary_cap"]

        politician, politician_meta = self._politician_flag_score(case)
        corruption, corruption_meta = self._corruption_text_score(case)
        case_type_score = self._case_type_score(case, case_type_map)
        monetary, monetary_meta = self._monetary_value_score(case, monetary_cap)
        priority = self._judicial_priority_score(case)
        historical, historical_meta = self._historical_public_interest_score(case)

        media = 0.0
        media_meta: dict[str, Any] = {"used": False}
        if not fast_pass:
            media, media_meta = self._media_mentions_score(case, decay_lambda)

        components = {
            "politician_flag_score": politician,
            "corruption_text_score": corruption,
            "case_type_score": case_type_score,
            "media_mentions_score": media,
            "monetary_value_score": monetary,
            "judicial_priority_score": priority,
            "historical_public_interest_score": historical,
            "weights": weights,
            "fast_pass": fast_pass,
        }

        raw = (
            weights["w_politician"] * politician
            + weights["w_corruption"] * corruption
            + weights["w_case_type"] * case_type_score
            + weights["w_media"] * media
            + weights["w_monetary"] * monetary
            + weights["w_priority"] * priority
            + weights["w_historical"] * historical
        )

        # Sigmoid-like smoothing around 0.5 to prevent extreme one-feature jumps.
        score = _clamp01(1.0 / (1.0 + math.exp(-6.0 * (raw - 0.5))))

        confidence = self._confidence_score(
            case,
            components,
            min_confidence=min_conf,
            media_meta=media_meta,
            corruption_meta=corruption_meta,
            monetary_meta=monetary_meta,
        )

        provenance = {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "fast_pass": fast_pass,
            "politician": politician_meta,
            "corruption": corruption_meta,
            "media": media_meta,
            "monetary": monetary_meta,
            "historical": historical_meta,
            "min_confidence": min_conf,
        }

        if case.importance_override and case.importance_override.get("score") is not None:
            score = _clamp01(float(case.importance_override["score"]))
            components["override_applied"] = True
        else:
            components["override_applied"] = False

        explanation = self._build_explanation(score, components)

        return ImportanceScoreResult(
            score=score,
            confidence=confidence,
            components=components,
            provenance=provenance,
            explanation=explanation,
        )

    def score_and_persist_case(self, case: Case, *, fast_pass: bool = False) -> ImportanceScoreResult:
        result = self.score_case(case, fast_pass=fast_pass)
        case.importance_score = result.score
        case.importance_confidence = result.confidence
        case.importance_components = result.components
        case.last_scored_at = datetime.now(timezone.utc)
        source_fields = dict(case.source_fields or {})
        source_fields["importance_explanation"] = result.explanation
        source_fields["importance_provenance"] = result.provenance
        case.source_fields = source_fields
        self.db.flush()
        return result

    def override_case_importance(
        self,
        *,
        case: Case,
        score: float,
        reason: str,
        admin_id: int,
    ) -> None:
        old = dict(case.importance_override or {})
        new_payload = {
            "score": _clamp01(score),
            "reason": reason,
            "admin_id": admin_id,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        case.importance_override = new_payload
        self.db.add(
            ImportanceAuditLog(
                case_id=case.id,
                action="override",
                admin_id=admin_id,
                reason=reason,
                old_value=old,
                new_value=new_payload,
                provenance={"source": "admin_api"},
            )
        )
        self.db.flush()

    def get_or_create_config(self) -> ImportanceConfig:
        row = self.db.query(ImportanceConfig).filter(ImportanceConfig.name == "default", ImportanceConfig.is_deleted.is_(False)).one_or_none()
        if row:
            return row
        row = ImportanceConfig(
            name="default",
            weights_json=self.DEFAULT_WEIGHTS,
            case_type_map_json=self.DEFAULT_CASE_TYPE_MAP,
            min_confidence=0.2,
            media_decay_lambda=0.05,
            monetary_cap=50_000_000.0,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def update_config(
        self,
        *,
        weights_json: dict[str, float],
        case_type_map_json: dict[str, float],
        min_confidence: float,
        media_decay_lambda: float,
        monetary_cap: float,
        admin_id: int,
    ) -> ImportanceConfig:
        row = self.get_or_create_config()
        old = {
            "weights_json": row.weights_json,
            "case_type_map_json": row.case_type_map_json,
            "min_confidence": row.min_confidence,
            "media_decay_lambda": row.media_decay_lambda,
            "monetary_cap": row.monetary_cap,
        }
        row.weights_json = weights_json
        row.case_type_map_json = case_type_map_json
        row.min_confidence = min_confidence
        row.media_decay_lambda = media_decay_lambda
        row.monetary_cap = monetary_cap
        row.updated_by_admin_id = admin_id
        self.db.add(
            ImportanceAuditLog(
                case_id=0,
                action="config_update",
                admin_id=admin_id,
                reason="importance config updated",
                old_value=old,
                new_value={
                    "weights_json": weights_json,
                    "case_type_map_json": case_type_map_json,
                    "min_confidence": min_confidence,
                    "media_decay_lambda": media_decay_lambda,
                    "monetary_cap": monetary_cap,
                },
                provenance={"source": "admin_api"},
            )
        )
        self.db.flush()
        return row

    def _resolve_config(self) -> dict[str, Any]:
        row = self.db.query(ImportanceConfig).filter(ImportanceConfig.name == "default", ImportanceConfig.is_deleted.is_(False)).one_or_none()

        env_weights = self._safe_json(self.settings.importance_weights_json)
        if row is None:
            return {
                "weights": env_weights or dict(self.DEFAULT_WEIGHTS),
                "case_type_map": dict(self.DEFAULT_CASE_TYPE_MAP),
                "min_confidence": self.settings.importance_min_confidence,
                "media_decay_lambda": self.settings.importance_media_decay_lambda,
                "monetary_cap": self.settings.importance_monetary_cap,
            }

        return {
            "weights": row.weights_json or env_weights or dict(self.DEFAULT_WEIGHTS),
            "case_type_map": row.case_type_map_json or dict(self.DEFAULT_CASE_TYPE_MAP),
            "min_confidence": row.min_confidence,
            "media_decay_lambda": row.media_decay_lambda,
            "monetary_cap": row.monetary_cap,
        }

    def _politician_flag_score(self, case: Case) -> tuple[float, dict[str, Any]]:
        links = (
            self.db.query(CasePartyLink)
            .filter(CasePartyLink.case_id == case.id, CasePartyLink.is_deleted.is_(False), CasePartyLink.official_id.isnot(None))
            .all()
        )
        if not links:
            return 0.0, {"matched": 0}
        best = max((link.match_confidence or 0.0) for link in links)
        verified = any(link.is_verified for link in links)
        if verified:
            return 1.0, {"matched": len(links), "verified": True, "best_match_confidence": best}
        return _clamp01(0.6 + (0.4 * best)), {"matched": len(links), "verified": False, "best_match_confidence": best}

    def _corruption_text_score(self, case: Case) -> tuple[float, dict[str, Any]]:
        text_parts = [case.judges_text or "", case.case_type or "", json.dumps(case.source_fields or {})]
        text = " ".join(text_parts).lower()
        words = [w for w in text.split() if w.strip()]
        total_words = max(len(words), 1)
        hits = []
        for keyword in self._keywords:
            count = text.count(keyword.lower())
            if count > 0:
                hits.append((keyword, count))
        total_hits = sum(count for _, count in hits)
        density = total_hits / total_words
        # Normalize density with cap to reduce text stuffing impact.
        score = _clamp01(min(1.0, density * 250.0))
        return score, {
            "keyword_hits": hits,
            "total_hits": total_hits,
            "total_words": total_words,
            "density": round(density, 6),
        }

    def _case_type_score(self, case: Case, case_type_map: dict[str, float]) -> float:
        ctype = (case.case_type or "").strip().lower().replace(" ", "_")
        if not ctype:
            return float(case_type_map.get("default", 0.3))
        return _clamp01(float(case_type_map.get(ctype, case_type_map.get("default", 0.3))))

    def _media_mentions_score(self, case: Case, decay_lambda: float) -> tuple[float, dict[str, Any]]:
        mentions = (
            self.db.query(CaseMediaMention)
            .filter(CaseMediaMention.case_id == case.id, CaseMediaMention.is_deleted.is_(False))
            .all()
        )
        if not mentions:
            return 0.0, {"used": False, "count": 0}

        now = datetime.now(timezone.utc)
        weighted = 0.0
        low_cred_recent = 0
        for item in mentions:
            published = item.published_at
            if published is None:
                days_old = 90.0
            else:
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                days_old = max(0.0, (now - published).total_seconds() / 86400.0)
            decay = math.exp(-decay_lambda * days_old)
            credibility = _clamp01(item.credibility_score)
            contrib = credibility * decay
            if credibility < 0.3 and days_old <= 2:
                low_cred_recent += 1
            weighted += contrib

        anti_gaming_cap_applied = False
        if low_cred_recent >= 6:
            weighted = min(weighted, 1.5)
            anti_gaming_cap_applied = True

        score = _clamp01(math.log1p(weighted) / math.log1p(5.0))
        return score, {
            "used": True,
            "count": len(mentions),
            "weighted_count": round(weighted, 4),
            "low_cred_recent": low_cred_recent,
            "anti_gaming_cap_applied": anti_gaming_cap_applied,
        }

    def _monetary_value_score(self, case: Case, monetary_cap: float) -> tuple[float, dict[str, Any]]:
        fields = case.source_fields or {}
        amount = fields.get("monetary_value") or fields.get("claim_amount") or fields.get("amount")
        if amount is None:
            return 0.0, {"present": False}
        try:
            amount_val = float(amount)
        except (TypeError, ValueError):
            return 0.0, {"present": False, "parse_error": True}

        bounded = max(0.0, min(amount_val, monetary_cap))
        if monetary_cap <= 0:
            return 0.0, {"present": True, "bounded": bounded}
        score = _clamp01(math.log1p(bounded) / math.log1p(monetary_cap))
        return score, {"present": True, "amount": amount_val, "bounded": bounded, "cap": monetary_cap}

    def _judicial_priority_score(self, case: Case) -> float:
        ctype = (case.case_type or "").lower()
        fields = case.source_fields or {}
        urgent = bool(fields.get("urgent") or fields.get("priority_listing"))
        pil = "pil" in ctype or "public interest" in ctype
        supreme = (case.court_level or "").lower() == "supreme"
        return 1.0 if urgent or pil or supreme else 0.0

    def _historical_public_interest_score(self, case: Case) -> tuple[float, dict[str, Any]]:
        fields = case.source_fields or {}
        views = float(fields.get("views") or 0)
        downloads = float(fields.get("downloads") or 0)
        flag_count = self.db.query(Flag).filter(Flag.case_id == case.id, Flag.is_deleted.is_(False)).count()
        aggregate = max(0.0, views + downloads + (2.0 * flag_count))
        score = _clamp01(math.log1p(aggregate) / math.log1p(10000.0))
        return score, {"views": views, "downloads": downloads, "flag_count": flag_count, "aggregate": aggregate}

    def _confidence_score(
        self,
        case: Case,
        components: dict[str, Any],
        *,
        min_confidence: float,
        media_meta: dict[str, Any],
        corruption_meta: dict[str, Any],
        monetary_meta: dict[str, Any],
    ) -> float:
        independent_signals = 0
        if components["politician_flag_score"] > 0:
            independent_signals += 1
        if corruption_meta.get("total_hits", 0) > 0:
            independent_signals += 1
        if media_meta.get("count", 0) > 0:
            independent_signals += 1
        if monetary_meta.get("present"):
            independent_signals += 1

        signal_score = independent_signals / 4.0

        if case.last_source_updated_at is None:
            freshness = 0.5
        else:
            last = case.last_source_updated_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (datetime.now(timezone.utc) - last).total_seconds() / 86400.0)
            freshness = math.exp(-age_days / 180.0)

        confidence = (0.75 * signal_score) + (0.25 * freshness)

        if media_meta.get("anti_gaming_cap_applied"):
            confidence *= 0.85

        if independent_signals < self.settings.importance_min_case_signals:
            confidence *= 0.5

        return _clamp01(max(min_confidence, confidence))

    @staticmethod
    def _build_explanation(score: float, components: dict[str, Any]) -> str:
        weighted = [
            ("politician", components["weights"]["w_politician"] * components["politician_flag_score"]),
            ("corruption text", components["weights"]["w_corruption"] * components["corruption_text_score"]),
            ("case type", components["weights"]["w_case_type"] * components["case_type_score"]),
            ("media mentions", components["weights"]["w_media"] * components["media_mentions_score"]),
            ("monetary value", components["weights"]["w_monetary"] * components["monetary_value_score"]),
            ("judicial priority", components["weights"]["w_priority"] * components["judicial_priority_score"]),
            (
                "historical public interest",
                components["weights"]["w_historical"] * components["historical_public_interest_score"],
            ),
        ]
        top = sorted(weighted, key=lambda item: item[1], reverse=True)[:3]
        top_text = ", ".join(f"{name} ({value:.2f})" for name, value in top)
        return f"Score {score:.2f}: high because of {top_text}."

    @staticmethod
    def _safe_json(raw: str | None) -> Optional[dict[str, float]]:
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        return {str(key): float(value) for key, value in parsed.items()}

    @staticmethod
    def _load_keywords() -> list[str]:
        path = Path(__file__).resolve().parent / "keywords" / "corruption_keywords.yml"
        if not path.exists():
            return []
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        kws = payload.get("keywords", [])
        return [str(item).strip().lower() for item in kws if str(item).strip()]
