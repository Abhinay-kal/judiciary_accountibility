from __future__ import annotations

from datetime import datetime, timezone

from app.analytics.dormancy import (
    DormancyThresholds,
    compute_baselines,
    compute_dormancy_score,
    evaluate_dormancy_rules,
    extract_case_features,
    generate_dormancy_explanation,
    normalized_inactivity,
    select_baseline,
    should_keep_flag,
)
from app.celery_app import celery_app
from app.core.cache import invalidate_for_event
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Case, Flag


def _thresholds(settings) -> DormancyThresholds:
    return DormancyThresholds(
        min_days_default=settings.dormancy_min_days_default,
        normalized_threshold=settings.dormancy_normalized_threshold,
        severe_normalized_threshold=settings.dormancy_severe_normalized_threshold,
        min_days_by_case_type={
            "criminal": 180,
            "civil": 270,
            "writ": 365,
            "service": 240,
        },
    )


@celery_app.task(name="app.tasks.dormancy_analytics.recompute_case_dormancy")
def recompute_case_dormancy(batch_size: int | None = None) -> dict:
    settings = get_settings()
    size = batch_size or settings.dormancy_batch_size
    db = SessionLocal()

    try:
        cases = (
            db.query(Case)
            .filter(Case.is_deleted.is_(False))
            .order_by(Case.id.asc())
            .limit(size)
            .all()
        )
        feature_rows = [
            extract_case_features(
                db,
                case,
                future_listing_horizon_days=settings.dormancy_future_listing_horizon_days,
            )
            for case in cases
        ]
        baseline_index = compute_baselines(feature_rows, min_samples=settings.dormancy_baseline_min_samples)

        thresholds = _thresholds(settings)
        dormant_count = 0
        reactivated_count = 0
        excluded_count = 0

        for case, features in zip(cases, feature_rows):
            selected = select_baseline(features, baseline_index, min_samples=settings.dormancy_baseline_min_samples)
            normalized = normalized_inactivity(features, selected)
            rules = evaluate_dormancy_rules(
                features,
                selected,
                normalized,
                thresholds,
                future_listing_exclusion_days=settings.dormancy_future_listing_horizon_days,
                min_data_confidence=settings.dormancy_min_data_confidence,
            )
            score = compute_dormancy_score(
                features,
                rules,
                normalized_inactivity=normalized,
                case_importance=case.importance_score,
            )
            explanation = generate_dormancy_explanation(
                features=features,
                baseline=selected,
                rules=rules,
                score=score,
            )

            case.days_since_last_activity = features.days_since_last_activity
            case.last_activity_date = features.last_activity_date
            case.dormancy_score = score.score
            case.dormancy_last_updated = datetime.now(timezone.utc)

            if rules.excluded:
                case.dormancy_status = "excluded"
                excluded_count += 1
            elif score.status == "dormant" and should_keep_flag(score.score, rules.is_candidate):
                case.dormancy_status = score.severity
                dormant_count += 1
                marker = (
                    f"Case entered dormant state on {case.last_activity_date.isoformat()}"
                    if case.last_activity_date is not None
                    else None
                )
                details = {
                    "summary": explanation.summary,
                    "dormancy": explanation.details,
                    "timeline_marker": marker,
                }
                existing = (
                    db.query(Flag)
                    .filter(
                        Flag.case_id == case.id,
                        Flag.flag_type == "dormant_case",
                        Flag.is_deleted.is_(False),
                    )
                    .first()
                )
                if existing is not None:
                    existing.score = score.score
                    existing.details = details
                    existing.is_active = True
                else:
                    db.add(
                        Flag(
                            case_id=case.id,
                            flag_type="dormant_case",
                            score=score.score,
                            details=details,
                            is_active=True,
                        )
                    )
            else:
                # Reactivation / downgrade path
                case.dormancy_status = "active_watch"
                reactivated_count += 1
                existing = (
                    db.query(Flag)
                    .filter(
                        Flag.case_id == case.id,
                        Flag.flag_type == "dormant_case",
                        Flag.is_deleted.is_(False),
                    )
                    .first()
                )
                if existing is not None:
                    existing.is_active = False
                    existing.details = {
                        "summary": "Dormancy flag downgraded after new activity or threshold recovery.",
                        "reactivated_at": datetime.now(timezone.utc).isoformat(),
                    }

        db.commit()
        invalidate_for_event("ANALYTICS_RECOMPUTED")
        return {
            "processed": len(cases),
            "dormant": dormant_count,
            "reactivated_or_downgraded": reactivated_count,
            "excluded": excluded_count,
            "baselines": len(baseline_index),
            "batch_size": size,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
