from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.cache import get_or_set_json, get_or_set_json_meta, invalidate_for_event
from app.db.session import get_db
from app.evidence.hearings import build_hearing_evidence_bundle
from app.explanations.generator import generate_case_summary
from app.impact.narratives import generate_and_store_case_impact, generate_case_impact
from app.core.config import get_settings
from app.analytics.delay.metrics import build_delay_summary_text
from app.analytics.dormancy import (
    DormancyThresholds,
    compute_baselines,
    compute_dormancy_score,
    evaluate_dormancy_rules,
    extract_case_features,
    generate_dormancy_explanation,
    normalized_inactivity,
    select_baseline,
)
from app.analytics.survival.dataset import compute_duration_and_event
from app.analytics.survival.km import KaplanMeierResult
from app.analytics.survival.prediction import case_survival_prediction
from app.moderation.renderer import render_public_text
from app.models import Case, Hearing, SurvivalCurve
from app.provenance.conflict import find_field_conflicts
from app.provenance.queries import get_entity_provenance, get_primary_for_field
from app.schemas.common import CaseOut, HearingOut
from app.schemas.query import CaseQuery
from app.services.query import apply_case_filters, paginate

router = APIRouter(prefix="/cases")
settings = get_settings()


def _serialize_case(case: Case, db: Session) -> dict:
    payload = CaseOut.model_validate(case).model_dump()
    source_fields = case.source_fields or {}
    labels = [str(source_fields.get("defamation_label") or settings.defamation_default_label)]
    parser_conf = source_fields.get("parser_confidence")
    payload["importance_explanation"] = source_fields.get("importance_explanation")
    payload["importance_provenance"] = source_fields.get("importance_provenance")
    delay_summary = build_delay_summary_text(
        normalized_delay=case.normalized_delay,
        delay_percentile=case.delay_percentile,
        baseline_label=case.baseline_level_used,
    )
    rendered_delay, render_meta = render_public_text(
        delay_summary,
        labels,
        parser_confidence=parser_conf,
        source_links=source_fields.get("source_links") or [case.source_url],
    )
    payload["delay_summary"] = rendered_delay
    payload["public_note"] = case.public_note
    if case.public_note:
        rendered_note, _ = render_public_text(
            case.public_note,
            labels,
            parser_confidence=parser_conf,
            source_links=source_fields.get("source_links") or [case.source_url],
        )
        payload["public_note"] = rendered_note
    payload["moderation_render_meta"] = render_meta

    summary = generate_case_summary(db, case).to_dict()
    payload["plain_summary"] = summary
    payload["plain_summary_short"] = case.plain_summary_short or summary["short_summary"]
    payload["plain_summary_detailed"] = case.plain_summary_detailed or summary["detailed_summary"]
    payload["summary_confidence"] = case.summary_confidence or summary["summary_confidence"]
    payload["last_summary_update"] = case.last_summary_update

    impact = generate_case_impact(db, case).to_dict()
    payload["impact_content"] = impact
    payload["impact_headline"] = case.impact_headline or impact["headline"]
    payload["impact_summary"] = case.impact_summary or impact["executive_summary"]
    payload["impact_confidence"] = case.impact_confidence or impact["impact_confidence"]
    payload["impact_last_updated"] = case.impact_last_updated
    payload["dormancy_status"] = case.dormancy_status
    payload["dormancy_score"] = case.dormancy_score
    payload["days_since_last_activity"] = case.days_since_last_activity
    payload["last_activity_date"] = case.last_activity_date
    payload["dormancy_last_updated"] = case.dormancy_last_updated
    return payload


def _compute_case_dormancy(case: Case, db: Session) -> dict:
    feature = extract_case_features(
        db,
        case,
        future_listing_horizon_days=settings.dormancy_future_listing_horizon_days,
    )

    peer_cases = (
        db.query(Case)
        .filter(Case.is_deleted.is_(False), Case.status.ilike("%pending%"))
        .order_by(Case.id.desc())
        .limit(1000)
        .all()
    )
    peer_features = [
        extract_case_features(
            db,
            row,
            future_listing_horizon_days=settings.dormancy_future_listing_horizon_days,
        )
        for row in peer_cases
    ]
    baseline_index = compute_baselines(peer_features, min_samples=settings.dormancy_baseline_min_samples)
    selected = select_baseline(feature, baseline_index, min_samples=settings.dormancy_baseline_min_samples)
    normalized = normalized_inactivity(feature, selected)
    thresholds = DormancyThresholds(
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
    rule_result = evaluate_dormancy_rules(
        feature,
        selected,
        normalized,
        thresholds,
        future_listing_exclusion_days=settings.dormancy_future_listing_horizon_days,
        min_data_confidence=settings.dormancy_min_data_confidence,
    )
    score = compute_dormancy_score(
        feature,
        rule_result,
        normalized_inactivity=normalized,
        case_importance=case.importance_score,
    )
    explanation = generate_dormancy_explanation(
        features=feature,
        baseline=selected,
        rules=rule_result,
        score=score,
    )
    timeline_marker = explanation.details.get("timeline_marker")

    return {
        "case_id": case.id,
        "status": score.status,
        "severity": score.severity,
        "dormancy_score": score.score,
        "confidence": score.confidence,
        "days_since_last_hearing": feature.days_since_last_hearing,
        "days_since_last_order": feature.days_since_last_order,
        "days_since_last_listing": feature.days_since_last_listing,
        "days_since_last_activity": feature.days_since_last_activity,
        "last_activity_date": feature.last_activity_date,
        "future_listing_exists": feature.future_listing_exists,
        "baseline_level": selected.level,
        "baseline_sample_size": selected.baseline.sample_size if selected.baseline else None,
        "normalized_inactivity": normalized,
        "exclusion_reason": rule_result.exclusion_reason,
        "explanation": explanation.summary,
        "explanation_details": explanation.details,
        "timeline_marker": timeline_marker,
    }


@router.get("", response_model=dict)
def list_cases(
    court: Optional[str] = None,
    state: Optional[str] = None,
    case_type: Optional[str] = None,
    party_name: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    flagged_only: bool = False,
    politician_only: bool = False,
    min_importance: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    min_normalized_delay: Optional[float] = Query(default=None, ge=0.0),
    delay_severity: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    cache_key = (
        f"court={court}|state={state}|case_type={case_type}|party_name={party_name}|"
        f"start={start_date}|end={end_date}|flagged={flagged_only}|politician={politician_only}|"
        f"min_importance={min_importance}|min_normalized_delay={min_normalized_delay}|delay_severity={delay_severity}|"
        f"page={page}|page_size={page_size}"
    )

    def _produce() -> dict:
        filters = CaseQuery(
            court=court,
            state=state,
            case_type=case_type,
            party_name=party_name,
            start_date=start_date,
            end_date=end_date,
            flagged_only=flagged_only,
            politician_only=politician_only,
            min_importance=min_importance,
            min_normalized_delay=min_normalized_delay,
            delay_severity=delay_severity,
            page=page,
            page_size=page_size,
        )

        query = db.query(Case).filter(Case.is_deleted.is_(False))
        query = apply_case_filters(query, filters)
        items, total = paginate(query, page, page_size)

        return {
            "items": [_serialize_case(item, db) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    payload, cache_meta = get_or_set_json_meta("cases", cache_key, _produce)
    payload["cache_meta"] = cache_meta
    return payload


@router.get("/dormant", response_model=dict)
def list_dormant_cases(
    severity: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    case_type: Optional[str] = Query(default=None),
    court_id: Optional[int] = Query(default=None),
    min_score: Optional[float] = Query(default=0.45, ge=0.0, le=1.0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Case).filter(Case.is_deleted.is_(False), Case.dormancy_score.is_not(None))

    if severity:
        query = query.filter(Case.dormancy_status == severity)
    else:
        query = query.filter(
            Case.dormancy_status.in_(
                [
                    "mild_dormancy",
                    "significant_dormancy",
                    "severe_dormancy",
                    "extreme_inactivity",
                ]
            )
        )
    if min_score is not None:
        query = query.filter(Case.dormancy_score >= min_score)
    if state:
        query = query.filter(Case.state == state)
    if case_type:
        query = query.filter(Case.case_type == case_type)
    if court_id is not None:
        query = query.filter(Case.court_id == court_id)

    query = query.order_by(Case.dormancy_score.desc().nullslast(), Case.id.asc())
    items, total = paginate(query, page, page_size)
    return {
        "items": [_serialize_case(item, db) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{case_id}/dormancy", response_model=dict)
def get_case_dormancy(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    return _compute_case_dormancy(case, db)


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: int, db: Session = Depends(get_db)):
    def _produce() -> dict:
        case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return _serialize_case(case, db)

    return get_or_set_json("case", str(case_id), _produce)


@router.post("/{case_id}/impact/regenerate", response_model=dict)
def regenerate_case_impact(case_id: int, audience: Optional[str] = Query(default="general_public"), db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    result = generate_and_store_case_impact(db, case, audience=audience or "general_public")
    db.commit()
    invalidate_for_event("MANUAL_OVERRIDE")
    return {
        "case_id": case_id,
        "audience": audience or "general_public",
        "impact": result.to_dict(),
        "impact_headline": case.impact_headline,
        "impact_summary": case.impact_summary,
        "impact_confidence": case.impact_confidence,
        "impact_last_updated": case.impact_last_updated,
    }


@router.get("/{case_id}/timeline", response_model=list[HearingOut])
def get_case_timeline(case_id: int, db: Session = Depends(get_db)):
    def _produce() -> list[dict]:
        hearings = (
            db.query(Hearing)
            .filter(Hearing.case_id == case_id, Hearing.is_deleted.is_(False))
            .order_by(Hearing.date.asc())
            .all()
        )
        payload = []
        for item in hearings:
            serialized = HearingOut.model_validate(item).model_dump()
            evidence_bundle = build_hearing_evidence_bundle(db, item)
            serialized["outcome_type"] = item.outcome_type.value if item.outcome_type else None
            serialized["needs_verification"] = (
                item.outcome_type is None
                or item.outcome_type.value == "OTHER"
                or (item.outcome_confidence or 0.0) < settings.default_outcome_confidence_verify
            )
            serialized["evidence_bundle"] = evidence_bundle
            serialized["raw_bench"] = item.raw_bench
            serialized["judge_assignments"] = evidence_bundle.get("judge_attribution", [])
            payload.append(serialized)
        return payload

    return get_or_set_json("case_timeline", str(case_id), _produce)


@router.get("/{case_id}/provenance", response_model=dict)
def get_case_provenance(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    rows = get_entity_provenance(db, entity_type="CASE", entity_id=str(case_id))
    by_field: dict[str, list[dict]] = {}
    for row in rows:
        by_field.setdefault(row.field_name, []).append(
            {
                "provenance_id": row.provenance_id,
                "field_value_hash": row.field_value_hash,
                "source_name": row.source_name,
                "source_type": row.source_type,
                "source_url": row.source_url,
                "raw_payload_ref": row.raw_payload_ref,
                "fetch_time": row.fetch_time,
                "confidence_score": row.confidence_score,
                "is_primary_source": row.is_primary_source,
                "transformation_steps": row.transformation_steps,
                "created_at": row.created_at,
            }
        )

    primary_source_map = {}
    conflicts = {}
    for field in by_field:
        primary = get_primary_for_field(db, entity_type="CASE", entity_id=str(case_id), field_name=field)
        primary_source_map[field] = primary.provenance_id if primary is not None else None
        conflicts[field] = find_field_conflicts(db, entity_type="CASE", entity_id=str(case_id), field_name=field)

    return {
        "case_id": case_id,
        "fields": by_field,
        "primary_source_map": primary_source_map,
        "conflicts": conflicts,
    }


@router.get("/{case_id}/survival", response_model=dict)
def get_case_survival(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

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
            db.query(SurvivalCurve)
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
        raise HTTPException(status_code=404, detail="No survival curve available for this case")

    duration_days, _ = compute_duration_and_event(case)
    age = float(duration_days or 0.0)
    horizon_days = float(settings.survival_prediction_horizon_days)

    km = KaplanMeierResult(
        time_points=list(selected.time_points or []),
        survival=list(selected.survival_probabilities or []),
        lower_ci=list(selected.lower_ci or []),
        upper_ci=list(selected.upper_ci or []),
        median_time=selected.median_time,
        q75_disposal_time=None,
        event_count=selected.event_count,
        sample_size=selected.sample_size,
    )
    pred = case_survival_prediction(
        curve=km,
        case_age_days=age,
        additional_days=horizon_days,
        percentile_threshold=settings.survival_unusual_percentile_threshold,
    )

    return {
        "case_id": case.id,
        "case_age_days": age,
        "grouping_type": selected.grouping_type,
        "grouping_value": selected.grouping_value,
        "case_type": selected.case_type,
        "sample_size": selected.sample_size,
        "survival_at_case_age": pred.survival_at_case_age,
        "survival_after_additional_days": pred.survival_after_additional_days,
        "median_expected_duration_days": pred.median_expected_duration_days,
        "percentile_rank": pred.percentile_rank,
        "unusual_delay": pred.unusual_delay,
        "summary": (
            f"A case of this type and group has a {100.0 * pred.survival_after_additional_days:.1f}% "
            f"chance of still being pending after {int(horizon_days / 365)} years."
        ),
    }
