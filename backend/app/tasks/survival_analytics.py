from __future__ import annotations

from app.analytics.survival.confidence import curve_confidence
from app.analytics.survival.dataset import build_survival_dataset, sync_case_survival_fields
from app.analytics.survival.prediction import case_survival_prediction
from app.analytics.survival.stratified import StratifiedCurve, compute_stratified_curves
from app.celery_app import celery_app
from app.core.cache import invalidate_namespace
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Case, Flag, SurvivalCurve


def _persist_curve(db, curve: StratifiedCurve) -> None:
    km = curve.km
    row = SurvivalCurve(
        grouping_type=curve.grouping_type,
        grouping_value=curve.grouping_value,
        case_type=curve.case_type,
        time_points=km.time_points,
        survival_probabilities=km.survival,
        lower_ci=km.lower_ci,
        upper_ci=km.upper_ci,
        hazard_rates=curve.hazard,
        median_time=km.median_time,
        sample_size=km.sample_size,
        event_count=km.event_count,
    )
    db.add(row)


@celery_app.task(name="app.tasks.survival_analytics.recompute_survival_curves")
def recompute_survival_curves() -> dict:
    settings = get_settings()
    db = SessionLocal()
    try:
        sync_case_survival_fields(db, window_years=settings.survival_window_years)
        rows = build_survival_dataset(db, window_years=settings.survival_window_years)

        db.query(SurvivalCurve).delete()

        written = 0
        groupings = [
            ("national", False),
            ("court", False),
            ("court", True),
            ("state", False),
            ("state", True),
            ("case_type", False),
            ("judge", False),
        ]

        for grouping, include_case_type in groupings:
            curves = compute_stratified_curves(
                rows,
                grouping_type=grouping,
                include_case_type=include_case_type,
                min_sample_size=settings.survival_min_sample_size,
            )
            for curve in curves:
                if include_case_type and grouping in {"court", "state"}:
                    curve.grouping_type = f"{grouping}_case_type"
                _persist_curve(db, curve)
                written += 1

        db.commit()
        invalidate_namespace("survival_curves")
        return {"rows": len(rows), "curves_written": written}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.survival_analytics.flag_survival_anomalies")
def flag_survival_anomalies(batch_size: int | None = None) -> dict:
    settings = get_settings()
    db = SessionLocal()
    try:
        size = batch_size or settings.survival_recompute_batch_size
        curves = db.query(SurvivalCurve).all()
        curve_map = {(curve.grouping_type, curve.grouping_value, curve.case_type): curve for curve in curves}

        cases = (
            db.query(Case)
            .filter(Case.is_deleted.is_(False), Case.case_duration_days.is_not(None))
            .order_by(Case.id.asc())
            .limit(size)
            .all()
        )

        flagged = 0
        for case in cases:
            case_type = (case.case_type or "unknown").strip().lower() or "unknown"
            candidates = [
                curve_map.get(("court_case_type", str(case.court_id), case_type)),
                curve_map.get(("court", str(case.court_id), None)),
                curve_map.get(("state_case_type", case.state or "unknown", case_type)),
                curve_map.get(("state", case.state or "unknown", None)),
                curve_map.get(("national", "all", case_type)),
                curve_map.get(("national", "all", None)),
            ]
            curve = next((item for item in candidates if item is not None), None)
            if curve is None:
                continue

            from app.analytics.survival.km import KaplanMeierResult

            km = KaplanMeierResult(
                time_points=list(curve.time_points or []),
                survival=list(curve.survival_probabilities or []),
                lower_ci=list(curve.lower_ci or []),
                upper_ci=list(curve.upper_ci or []),
                median_time=curve.median_time,
                q75_disposal_time=None,
                event_count=curve.event_count,
                sample_size=curve.sample_size,
            )
            pred = case_survival_prediction(
                curve=km,
                case_age_days=float(case.case_duration_days or 0.0),
                additional_days=float(settings.survival_prediction_horizon_days),
                percentile_threshold=settings.survival_unusual_percentile_threshold,
            )

            is_anomaly = pred.unusual_delay or pred.survival_at_case_age < settings.survival_low_probability_threshold
            if not is_anomaly:
                continue

            existing = (
                db.query(Flag)
                .filter(Flag.case_id == case.id, Flag.flag_type == "survival_delay_anomaly", Flag.is_deleted.is_(False))
                .first()
            )
            details = {
                "percentile_rank": pred.percentile_rank,
                "survival_at_case_age": pred.survival_at_case_age,
                "survival_after_horizon": pred.survival_after_additional_days,
                "grouping_type": curve.grouping_type,
                "grouping_value": curve.grouping_value,
                "case_type": curve.case_type,
            }
            if existing:
                existing.score = pred.percentile_rank
                existing.details = details
                existing.is_active = True
            else:
                db.add(
                    Flag(
                        case_id=case.id,
                        flag_type="survival_delay_anomaly",
                        score=pred.percentile_rank,
                        details=details,
                        is_active=True,
                    )
                )
            flagged += 1

        db.commit()
        invalidate_namespace("cases")
        invalidate_namespace("case")
        return {"processed": len(cases), "flagged": flagged}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.survival_analytics.run_survival_pipeline")
def run_survival_pipeline() -> dict:
    return {
        "curves": recompute_survival_curves(),
        "anomalies": flag_survival_anomalies(),
    }
