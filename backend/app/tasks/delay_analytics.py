from __future__ import annotations

from datetime import datetime, timezone

from app.analytics.delay.baselines import build_and_store_delay_baselines, compute_case_delay_days
from app.analytics.delay.normalization import normalize_case_delay
from app.celery_app import celery_app
from app.core.config import get_settings
from app.core.cache import invalidate_for_event
from app.db.session import SessionLocal
from app.explanations.generator import generate_and_store_case_summary
from app.impact.narratives import generate_and_store_case_impact
from app.models import Case, DelayBaseline, Flag


@celery_app.task(name="app.tasks.delay_analytics.recompute_delay_baselines")
def recompute_delay_baselines() -> dict:
    settings = get_settings()
    db = SessionLocal()
    try:
        summary = build_and_store_delay_baselines(
            db,
            window_years=settings.delay_baseline_window_years,
            use_time_weighted=settings.delay_use_time_weighted_baseline,
            half_life_days=settings.delay_half_life_days,
        )
        return summary
    finally:
        db.close()


@celery_app.task(name="app.tasks.delay_analytics.update_case_delay_analytics")
def update_case_delay_analytics(batch_size: int | None = None) -> dict:
    settings = get_settings()
    size = batch_size or settings.delay_update_batch_size

    db = SessionLocal()
    updated = 0
    anomalous = 0
    try:
        rows = db.query(DelayBaseline).all()
        baseline_index = {
            (item.baseline_level, item.court_id, item.state, item.case_type): item
            for item in rows
        }

        cases = (
            db.query(Case)
            .filter(Case.is_deleted.is_(False))
            .order_by(Case.id.asc())
            .limit(size)
            .all()
        )

        for case in cases:
            delay_days = compute_case_delay_days(case)
            metrics, choice, confidence = normalize_case_delay(
                case=case,
                case_delay_days=delay_days,
                baseline_index=baseline_index,
                min_sample_size=settings.delay_min_group_sample_size,
                moderate_threshold=settings.delay_ratio_moderate_threshold,
                high_threshold=settings.delay_ratio_high_threshold,
                extreme_threshold=settings.delay_ratio_extreme_threshold,
            )
            if metrics is None:
                continue

            case.normalized_delay = metrics.normalized_delay
            case.delay_percentile = metrics.delay_percentile
            case.robust_z_score = metrics.robust_z_score
            case.delay_severity = metrics.delay_severity
            case.baseline_level_used = choice.baseline.baseline_level if choice.baseline else None
            case.baseline_sample_size = choice.baseline.sample_size if choice.baseline else None
            case.baseline_confidence = confidence
            case.last_baseline_update = datetime.now(timezone.utc)
            generate_and_store_case_summary(db, case)
            generate_and_store_case_impact(db, case)
            updated += 1

            is_anomaly = (
                (metrics.normalized_delay or 0.0) >= settings.delay_ratio_moderate_threshold
                or (metrics.delay_percentile or 0.0) >= settings.delay_percentile_anomaly_threshold
                or (metrics.robust_z_score or 0.0) >= settings.delay_robust_z_anomaly_threshold
            )
            if is_anomaly:
                anomalous += 1
                existing = (
                    db.query(Flag)
                    .filter(
                        Flag.case_id == case.id,
                        Flag.flag_type == "baseline_delay_anomaly",
                        Flag.is_deleted.is_(False),
                    )
                    .first()
                )
                details = {
                    "normalized_delay": metrics.normalized_delay,
                    "delay_percentile": metrics.delay_percentile,
                    "robust_z_score": metrics.robust_z_score,
                    "baseline_level_used": case.baseline_level_used,
                    "baseline_confidence": confidence,
                }
                if existing:
                    existing.score = metrics.normalized_delay
                    existing.details = details
                    existing.is_active = True
                else:
                    db.add(
                        Flag(
                            case_id=case.id,
                            flag_type="baseline_delay_anomaly",
                            score=metrics.normalized_delay,
                            details=details,
                            is_active=True,
                        )
                    )

        db.commit()
        invalidate_for_event("ANALYTICS_RECOMPUTED")
        return {
            "updated": updated,
            "anomalous": anomalous,
            "baselines_loaded": len(rows),
            "batch_size": size,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.delay_analytics.run_delay_analytics_pipeline")
def run_delay_analytics_pipeline() -> dict:
    baseline_summary = recompute_delay_baselines()
    case_summary = update_case_delay_analytics()
    return {"baselines": baseline_summary, "cases": case_summary}
