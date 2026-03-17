from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Case, CaseFeedback, DelayBaseline, Flag, Hearing, Order, SurvivalCurve
from app.models.entities import FeedbackPublicStatus

try:
    from app.evidence.hearings import build_hearing_evidence_bundle
except Exception:  # pragma: no cover - fallback for minimal runtime/test envs
    def build_hearing_evidence_bundle(db: Session, hearing: Hearing) -> dict:
        source_url = hearing.case.source_url if getattr(hearing, "case", None) else None
        return {
            "source_links": [item for item in [source_url] if item],
            "judge_attribution": [],
        }


@dataclass
class InvestigationReport:
    case_id: int
    summary: dict[str, Any]
    timeline: list[dict[str, Any]]
    metrics: dict[str, Any]
    anomalies: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    methodology: dict[str, Any]
    confidence: dict[str, Any]
    right_to_respond: dict[str, Any]
    last_updated: str
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InvestigationBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.cfg = get_settings()

    def build(self, case_id: int) -> InvestigationReport:
        case = self.db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none()
        if case is None:
            raise ValueError("Case not found")

        hearings = (
            self.db.query(Hearing)
            .filter(Hearing.case_id == case_id, Hearing.is_deleted.is_(False))
            .order_by(Hearing.date.asc())
            .all()
        )
        orders = (
            self.db.query(Order)
            .filter(Order.case_id == case_id, Order.is_deleted.is_(False))
            .order_by(Order.order_date.asc())
            .all()
        )
        flags = (
            self.db.query(Flag)
            .filter(Flag.case_id == case_id, Flag.is_deleted.is_(False), Flag.is_active.is_(True))
            .order_by(Flag.score.desc().nullslast())
            .all()
        )

        summary = self._build_summary(case)
        timeline = self._build_timeline(case, hearings, orders)
        metrics = self._build_metrics(case)
        anomalies = self._build_anomalies(flags, metrics)
        evidence = self._build_evidence(case, hearings, orders)
        methodology = self._build_methodology(case)
        confidence = self._build_confidence(case, hearings, orders)
        rtr = self._build_right_to_respond(case_id)

        return InvestigationReport(
            case_id=case.id,
            summary=summary,
            timeline=timeline,
            metrics=metrics,
            anomalies=anomalies,
            evidence=evidence,
            methodology=methodology,
            confidence=confidence,
            right_to_respond=rtr,
            last_updated=datetime.now(timezone.utc).isoformat(),
            disclaimer=(
                "This report is generated from court records and related public data. "
                "It is intended for public-interest analysis and does not by itself establish wrongdoing."
            ),
        )

    def _build_summary(self, case: Case) -> dict[str, Any]:
        percentile = float(case.delay_percentile or 0.0)
        years = float(case.case_duration_days or 0.0) / 365.0
        narrative = (
            f"This case has been pending for {years:.1f} years, which is longer than {percentile:.0f}% "
            "of similar cases in this court."
            if case.case_duration_days and case.delay_percentile is not None
            else "Delay benchmarking is currently limited due to incomplete comparable baseline coverage."
        )
        return {
            "headline": f"Investigation: Case {case.case_number}",
            "case_number": case.case_number,
            "case_uid": case.case_uid,
            "court": case.court.name if getattr(case, "court", None) else None,
            "court_level": case.court_level,
            "state": case.state,
            "status": case.status,
            "filing_date": case.filing_date.isoformat() if case.filing_date else None,
            "next_hearing_date": case.next_hearing_date.isoformat() if case.next_hearing_date else None,
            "narrative": narrative,
        }

    def _build_timeline(self, case: Case, hearings: list[Hearing], orders: list[Order]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if case.filing_date:
            events.append(
                {
                    "event_type": "FILING",
                    "date": case.filing_date.isoformat(),
                    "title": "Case filing",
                    "details": "Initial filing date from source record.",
                    "evidence_links": [case.source_url],
                }
            )

        previous_judge_id = None
        for hearing in hearings:
            bundle = build_hearing_evidence_bundle(self.db, hearing)
            outcome = hearing.outcome_type.value if hearing.outcome_type else "HEARING"
            if outcome == "ADJOURNED":
                event_type = "ADJOURNMENT"
            elif outcome == "DISPOSED":
                event_type = "DISPOSAL"
            elif "BAIL" in (hearing.outcome_text or "").upper():
                event_type = "BAIL_EVENT"
            else:
                event_type = "HEARING"

            events.append(
                {
                    "event_type": event_type,
                    "date": hearing.date.isoformat(),
                    "title": hearing.listing_type or "Hearing",
                    "details": hearing.outcome_text,
                    "evidence_links": bundle.get("source_links", []),
                    "source_bundle": bundle,
                }
            )

            if hearing.judge_id and previous_judge_id and hearing.judge_id != previous_judge_id:
                events.append(
                    {
                        "event_type": "JUDGE_CHANGE",
                        "date": hearing.date.isoformat(),
                        "title": "Bench composition change",
                        "details": "Judge assignment changed between hearing dates.",
                        "evidence_links": [case.source_url],
                    }
                )
            if hearing.judge_id:
                previous_judge_id = hearing.judge_id

        for order in orders:
            events.append(
                {
                    "event_type": "ORDER",
                    "date": order.order_date.isoformat() if order.order_date else None,
                    "title": "Court order",
                    "details": order.raw_reference,
                    "evidence_links": [order.order_link],
                }
            )

        events = [item for item in events if item.get("date")]
        events.sort(key=lambda item: item["date"])
        return events

    def _build_metrics(self, case: Case) -> dict[str, Any]:
        duration_days = self._compute_case_duration_days(case)
        survival = self._get_survival(case, duration_days)
        baseline = self._select_baseline(case)

        comparisons = {}
        if baseline is not None:
            comparisons = {
                "baseline_level": baseline.baseline_level,
                "median_delay_days": baseline.median_delay,
                "p75_delay_days": baseline.p75_delay,
                "sample_size": baseline.sample_size,
            }

        return {
            "total_duration_days": round(duration_days, 2),
            "total_duration_years": round(duration_days / 365.0, 2),
            "normalized_delay": case.normalized_delay,
            "percentile_ranking": case.delay_percentile,
            "strategic_delay_score": case.importance_score,
            "survival_probability": survival.get("survival_at_case_age"),
            "survival_summary": survival,
            "baseline_comparisons": comparisons,
        }

    def _build_anomalies(self, flags: list[Flag], metrics: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for flag in flags:
            items.append(
                {
                    "title": flag.flag_type.replace("_", " ").title(),
                    "severity": flag.score,
                    "details": flag.details,
                }
            )

        if metrics.get("survival_summary", {}).get("unusual_delay"):
            items.append(
                {
                    "title": "Unusual delay profile",
                    "severity": metrics.get("percentile_ranking"),
                    "details": "Current duration appears unusually long compared to similar cases.",
                }
            )
        return items

    def _build_evidence(self, case: Case, hearings: list[Hearing], orders: list[Order]) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = [
            {
                "source_type": "official_record",
                "label": "Primary case record",
                "source_url": case.source_url,
                "archived_copy": case.source_url,
            }
        ]

        for order in orders:
            evidence.append(
                {
                    "source_type": "court_order",
                    "label": f"Order {order.id}",
                    "source_url": order.order_link,
                    "archived_copy": order.order_link,
                }
            )

        for hearing in hearings:
            bundle = build_hearing_evidence_bundle(self.db, hearing)
            for link in bundle.get("source_links", []):
                evidence.append(
                    {
                        "source_type": "hearing_record",
                        "label": f"Hearing {hearing.id}",
                        "source_url": link,
                        "archived_copy": link,
                    }
                )

        dedup: dict[str, dict[str, Any]] = {}
        for item in evidence:
            dedup[item["source_url"]] = item
        return list(dedup.values())

    def _build_methodology(self, case: Case) -> dict[str, Any]:
        return {
            "data_sources": [
                "court case registry records",
                "hearing timeline entries",
                "court order links",
                "moderated official response records",
            ],
            "algorithms": [
                "delay normalization against rolling baselines",
                "percentile estimation against comparable cohort",
                "kaplan-meier survival estimation for pending probability",
                "rule-based anomaly flags",
            ],
            "limitations": [
                "some hearing outcomes may need manual verification",
                "missing source records can lower confidence",
                "cross-court baseline coverage varies by case type",
            ],
            "update_frequency": "on ingestion updates and first investigation-page request",
            "case_type": case.case_type,
        }

    def _build_confidence(self, case: Case, hearings: list[Hearing], orders: list[Order]) -> dict[str, Any]:
        components = {
            "baseline_confidence": float(case.baseline_confidence or 0.0),
            "importance_confidence": float(case.importance_confidence or 0.0),
            "hearing_coverage": min(1.0, len(hearings) / 20.0),
            "order_coverage": min(1.0, len(orders) / 10.0),
        }
        score = round(sum(components.values()) / len(components), 3)
        return {
            "score": score,
            "components": components,
            "coverage_limitations": "Confidence decreases when hearings/orders are sparse or parser confidence is low.",
            "non_accusatory_disclaimer": (
                "Findings indicate data patterns, not legal conclusions or allegations of misconduct."
            ),
        }

    def _build_right_to_respond(self, case_id: int) -> dict[str, Any]:
        rows = (
            self.db.query(CaseFeedback)
            .filter(
                CaseFeedback.case_id == case_id,
                CaseFeedback.public_status.in_([FeedbackPublicStatus.PUBLISHED, FeedbackPublicStatus.LIMITED]),
            )
            .order_by(CaseFeedback.submitted_at.desc())
            .all()
        )
        responses = []
        for row in rows:
            responses.append(
                {
                    "label": row.display_label.value,
                    "statement": f"Official response submitted by {row.responder_affiliation or row.responder_name}",
                    "content": row.content if row.public_status == FeedbackPublicStatus.PUBLISHED else None,
                    "verification_status": row.responder_verification_method.value if row.responder_verification_method else "pending",
                    "public_status": row.public_status.value,
                    "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
                }
            )
        return {
            "present": bool(responses),
            "responses": responses,
        }

    def _select_baseline(self, case: Case) -> DelayBaseline | None:
        candidates = (
            self.db.query(DelayBaseline)
            .filter(
                DelayBaseline.baseline_level == (case.baseline_level_used or "state_case_type"),
                DelayBaseline.state == case.state,
            )
            .order_by(DelayBaseline.computed_at.desc())
            .all()
        )
        for row in candidates:
            if row.case_type == case.case_type or row.case_type is None:
                return row
        return candidates[0] if candidates else None

    def _get_survival(self, case: Case, age_days: float) -> dict[str, Any]:
        case_type = (case.case_type or "unknown").strip().lower() or "unknown"
        candidates = [
            ("court_case_type", str(case.court_id), case_type),
            ("court", str(case.court_id), None),
            ("state_case_type", case.state or "unknown", case_type),
            ("state", case.state or "unknown", None),
            ("national", "all", case_type),
            ("national", "all", None),
        ]

        selected = None
        for grouping_type, grouping_value, ctype in candidates:
            selected = (
                self.db.query(SurvivalCurve)
                .filter(
                    SurvivalCurve.grouping_type == grouping_type,
                    SurvivalCurve.grouping_value == grouping_value,
                    SurvivalCurve.case_type == ctype,
                )
                .one_or_none()
            )
            if selected is not None:
                break

        if selected is None:
            return {"available": False}

        time_points = [float(item) for item in (selected.time_points or [])]
        survival_probs = [float(item) for item in (selected.survival_probabilities or [])]

        def _survival_at(day: float) -> float:
            value = 1.0
            for t, s in zip(time_points, survival_probs):
                if day < t:
                    break
                value = s
            return max(0.0, min(1.0, value))

        survival_at_age = _survival_at(float(age_days))
        survival_after_horizon = _survival_at(float(age_days) + float(self.cfg.survival_prediction_horizon_days))
        percentile_rank = round((1.0 - survival_at_age) * 100.0, 2)
        unusual_delay = bool(percentile_rank >= float(self.cfg.survival_unusual_percentile_threshold))

        return {
            "available": True,
            "grouping_type": selected.grouping_type,
            "grouping_value": selected.grouping_value,
            "sample_size": selected.sample_size,
            "survival_at_case_age": survival_at_age,
            "survival_after_additional_days": survival_after_horizon,
            "percentile_rank": percentile_rank,
            "unusual_delay": unusual_delay,
        }

    def _compute_case_duration_days(self, case: Case) -> float:
        if case.case_duration_days is not None:
            return float(case.case_duration_days)
        if case.filing_date is None:
            return 0.0
        return float((date.today() - case.filing_date).days)
