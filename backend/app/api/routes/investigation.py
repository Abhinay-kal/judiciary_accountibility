from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.cache import get_or_set_json_meta
from app.db.session import get_db
from app.investigation import (
    InvestigationBuilder,
    SnapshotService,
    build_share_metadata,
    export_json_package,
    export_offline_archive,
    export_pdf_bytes,
    export_printable_html,
)
from app.models import Case

router = APIRouter(prefix="/investigation", tags=["investigation"])


def _canonical(case_id: int, version_number: int | None = None) -> str:
    if version_number is None:
        return f"/investigation/{case_id}"
    return f"/investigation/{case_id}/v/{version_number}"


def _hydrate_snapshot(db: Session, case_id: int) -> tuple[dict, dict]:
    builder = InvestigationBuilder(db)
    snapshots = SnapshotService(db)
    report = builder.build(case_id).to_dict()
    snap = snapshots.create_snapshot_if_changed(
        case_id=case_id,
        report=report,
        data_cutoff_date=datetime.now(timezone.utc).date(),
    )
    snapshot_meta = {
        "snapshot_id": snap.snapshot_id,
        "version_number": snap.version_number,
        "content_hash": snap.content_hash,
        "generated_at": snap.generated_at,
        "data_cutoff_date": snap.data_cutoff_date,
        "is_current": snap.is_current,
    }
    return snap.snapshot_data, snapshot_meta


@router.get("/search")
def search_investigations(
    importance_score_min: float | None = Query(default=None),
    delay_severity: str | None = Query(default=None),
    court: str | None = Query(default=None),
    state: str | None = Query(default=None),
    case_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Case).filter(Case.is_deleted.is_(False))
    if importance_score_min is not None:
        query = query.filter(Case.importance_score >= importance_score_min)
    if delay_severity:
        query = query.filter(Case.delay_severity == delay_severity)
    if court:
        query = query.join(Case.court).filter_by(name=court)
    if state:
        query = query.filter(Case.state == state)
    if case_type:
        query = query.filter(Case.case_type == case_type)

    total = query.count()
    rows = (
        query.order_by(Case.importance_score.desc().nullslast(), Case.case_duration_days.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "case_id": row.id,
                "case_uid": row.case_uid,
                "case_number": row.case_number,
                "court": row.court.name if row.court else None,
                "state": row.state,
                "case_type": row.case_type,
                "importance_score": row.importance_score,
                "delay_severity": row.delay_severity,
                "investigation_url": _canonical(row.id),
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{case_id}")
def get_investigation_page(
    case_id: int,
    format: str = Query(default="json", pattern="^(json|html)$"),
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    if db.query(Case).filter(Case.id == case_id, Case.is_deleted.is_(False)).one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")

    cache_key = f"{case_id}:current"

    def _produce() -> dict:
        report, snapshot_meta = _hydrate_snapshot(db, case_id)
        metadata = build_share_metadata(report, canonical_url=_canonical(case_id))
        return {
            "canonical_url": _canonical(case_id),
            "report": report,
            "metadata": metadata,
            "snapshot": snapshot_meta,
        }

    if refresh:
        payload = _produce()
        payload["cache_meta"] = {"cache_status": "BYPASS", "source": "live"}
    else:
        payload, cache_meta = get_or_set_json_meta("investigation_page", cache_key, _produce)
        payload["cache_meta"] = cache_meta
    if format == "html":
        html = export_printable_html(
            payload["report"],
            canonical_url=payload["canonical_url"],
            version_number=payload["snapshot"]["version_number"],
        )
        return Response(content=html, media_type="text/html")
    return payload


@router.get("/{case_id}/v/{version_number}")
def get_investigation_version(
    case_id: int,
    version_number: int,
    format: str = Query(default="json", pattern="^(json|html)$"),
    db: Session = Depends(get_db),
):
    snapshots = SnapshotService(db)
    row = snapshots.get_version(case_id, version_number)
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation snapshot version not found")

    report = row.snapshot_data
    canonical_url = _canonical(case_id, version_number)
    payload = {
        "canonical_url": canonical_url,
        "report": report,
        "metadata": build_share_metadata(report, canonical_url=canonical_url),
        "snapshot": {
            "snapshot_id": row.snapshot_id,
            "version_number": row.version_number,
            "content_hash": row.content_hash,
            "generated_at": row.generated_at,
            "data_cutoff_date": row.data_cutoff_date,
            "is_current": row.is_current,
        },
    }
    if format == "html":
        return Response(
            content=export_printable_html(report, canonical_url=canonical_url, version_number=row.version_number),
            media_type="text/html",
        )
    return payload


@router.get("/{case_id}/versions")
def list_investigation_versions(case_id: int, db: Session = Depends(get_db)) -> dict:
    snapshots = SnapshotService(db)
    return {
        "case_id": case_id,
        "versions": snapshots.list_versions(case_id),
    }


@router.get("/{case_id}/export/json")
def export_investigation_json(case_id: int, db: Session = Depends(get_db)) -> dict:
    report, snapshot_meta = _hydrate_snapshot(db, case_id)
    return export_json_package(report, snapshot_meta=snapshot_meta)


@router.get("/{case_id}/export/pdf")
def export_investigation_pdf(case_id: int, db: Session = Depends(get_db)) -> Response:
    report, snapshot_meta = _hydrate_snapshot(db, case_id)
    payload = export_pdf_bytes(report, snapshot_meta=snapshot_meta)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=investigation-{case_id}-v{snapshot_meta['version_number']}.pdf"},
    )


@router.get("/{case_id}/export/archive")
def export_investigation_archive(case_id: int, db: Session = Depends(get_db)) -> Response:
    report, snapshot_meta = _hydrate_snapshot(db, case_id)
    payload = export_offline_archive(
        report,
        canonical_url=_canonical(case_id),
        version_number=snapshot_meta["version_number"],
        snapshot_meta=snapshot_meta,
    )
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=investigation-{case_id}-archive.zip"},
    )


# ACCOUNTABILITY ANALYSIS ENDPOINTS
# New endpoints for tactic detection and advocate attribution

@router.get("/{case_id}/accountability/attributions")
def get_delay_attributions(
    case_id: int,
    min_confidence: float = Query(default=0.50, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    """
    Get delay attributions for a case.
    
    Analyzes all adjournments and interim applications in a case to determine
    which advocates are responsible for delays, with confidence scores.
    
    Args:
        case_id: Case ID
        min_confidence: Minimum confidence threshold (0-1) for attributions to return
    
    Returns:
        List of DelayAttribution objects with:
        - advocate_id: Responsible advocate
        - responsibility_percentage: 0-100
        - confidence_score: 0-1
        - attribution_type: Type of tactic (adjournment_tactic, frivolous_interim_app, pattern_based)
        - impacted_days: Estimated days of delay caused
        - reasoning: Explanation of attribution
    """
    from app.services.advocate_attribution_engine import AdvocateAttributionEngine
    
    case = db.query(Case).filter(Case.id == case_id, Case.deleted_at.is_(None)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    attributions = AdvocateAttributionEngine.attribute_case_delays(
        db, case, min_confidence=min_confidence
    )
    
    return {
        "case_id": case_id,
        "total_attributions": len(attributions),
        "attributions": [attr.to_dict() for attr in attributions],
    }


@router.get("/{case_id}/accountability/adjournments")
def get_adjournment_analysis(
    case_id: int,
    db: Session = Depends(get_db),
):
    """
    Get tactic classification for all adjournments in a case.
    
    Analyzes each adjournment to classify it on the tactic spectrum:
    - LIKELY_DELAY_TACTIC: High confidence (75-100%) it's a tactic
    - POSSIBLE_DELAY_TACTIC: Medium confidence (60-75%)
    - AMBIGUOUS: Uncertain (40-60%)
    - LIKELY_LEGITIMATE: Probably justified (20-40%)
    - CLEARLY_NECESSARY: Clearly justified (0-20%)
    """
    from app.models.entities import Adjournment, Advocate, Hearing
    from app.services.adjournment_classifier import AdjournmentClassifier
    
    case = db.query(Case).filter(Case.id == case_id, Case.deleted_at.is_(None)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    adjournments = db.query(Adjournment).filter(
        Adjournment.case_id == case_id,
        Adjournment.deleted_at.is_(None),
    ).all()
    
    classifications = []
    for adj in adjournments:
        advocate = None
        if adj.requested_by:
            advocate = db.query(Advocate).filter(
                Advocate.id == adj.requested_by
            ).first()
        
        hearing_date = None
        if adj.hearing_id:
            hearing = db.query(Hearing).filter(Hearing.id == adj.hearing_id).first()
            hearing_date = hearing.date if hearing else None
        
        classification = AdjournmentClassifier.classify(adj, case, advocate)
        classifications.append({
            "adjournment_id": adj.id,
            "hearing_date": hearing_date,
            **classification.to_dict(),
        })
    
    # Group by tactic type
    by_type = {}
    for c in classifications:
        tactic_type = c["tactic_type"]
        if tactic_type not in by_type:
            by_type[tactic_type] = []
        by_type[tactic_type].append(c)
    
    return {
        "case_id": case_id,
        "total_adjournments": len(classifications),
        "by_tactic_type": by_type,
        "classifications": classifications,
    }


@router.get("/{case_id}/accountability/interim-apps")
def get_interim_app_analysis(
    case_id: int,
    db: Session = Depends(get_db),
):
    """
    Get frivolity assessment for all interim applications in a case.
    
    Analyzes each interim petition (bail, stay, injunction, etc.) to assess
    likelihood of frivolity (filed to delay rather than for legitimate grounds).
    
    Frivolity levels:
    - CLEARLY_FRIVOLOUS: 80-100% score (strong evidence of frivolity)
    - LIKELY_FRIVOLOUS: 65-80%
    - POSSIBLY_FRIVOLOUS: 50-65%
    - AMBIGUOUS: 35-50%
    - LIKELY_LEGITIMATE: 20-35%
    - CLEARLY_LEGITIMATE: 0-20%
    """
    from app.models.entities import InterimApplication, Advocate
    from app.services.interim_app_frivolity_detector import InterimApplicationFrivolityDetector
    
    case = db.query(Case).filter(Case.id == case_id, Case.deleted_at.is_(None)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    interim_apps = db.query(InterimApplication).filter(
        InterimApplication.case_id == case_id,
        InterimApplication.deleted_at.is_(None),
    ).all()
    
    assessments = []
    for app in interim_apps:
        applicant = None
        if app.applicant_advocate_id:
            applicant = db.query(Advocate).filter(
                Advocate.id == app.applicant_advocate_id
            ).first()
        
        assessment = InterimApplicationFrivolityDetector.assess(app, case, applicant)
        assessments.append({
            "interim_app_id": app.id,
            "filing_date": app.filing_date,
            "decision_date": app.decision_date,
            **assessment.to_dict(),
        })
    
    # Group by frivolity level
    by_level = {}
    for a in assessments:
        level = a["frivolity_level"]
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(a)
    
    return {
        "case_id": case_id,
        "total_interim_applications": len(assessments),
        "by_frivolity_level": by_level,
        "assessments": assessments,
    }


@router.get("/advocates/{advocate_id}/performance")
def get_advocate_performance(
    advocate_id: int,
    db: Session = Depends(get_db),
):
    """
    Get advocate performance scorecard from materialized view.
    
    Returns pre-computed statistics on:
    - Total cases and disposal rate
    - Adjournment request patterns
    - Interim application filing patterns
    - Court specialization
    - Average case duration
    """
    from sqlalchemy import text
    
    result = db.execute(
        text("""
        SELECT advocate_id, canonical_name, total_cases_involved, active_cases,
               disposed_cases, case_disposal_rate, total_adjournments_in_cases,
               adjournments_requested, pct_requested_by_advocate, interim_apps_filed,
               interim_grant_rate, courts_practicing_in, case_types_handled,
               avg_case_duration_days
        FROM advocate_performance_summary
        WHERE advocate_id = :advocate_id
        """),
        {"advocate_id": advocate_id}
    ).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Advocate not found")
    
    columns = [
        "advocate_id", "canonical_name", "total_cases_involved", "active_cases",
        "disposed_cases", "case_disposal_rate", "total_adjournments_in_cases",
        "adjournments_requested", "pct_requested_by_advocate", "interim_apps_filed",
        "interim_grant_rate", "courts_practicing_in", "case_types_handled",
        "avg_case_duration_days"
    ]
    
    return {
        "advocate_id": advocate_id,
        "performance": dict(zip(columns, result)),
    }


@router.get("/advocates/{advocate_id}/adjournment-stats")
def get_advocate_adjournment_stats(
    advocate_id: int,
    db: Session = Depends(get_db),
):
    """
    Get adjournment statistics for an advocate from materialized view.
    
    Shows:
    - Cases involving adjournments
    - Total adjournment events
    - Adjournments requested by this advocate
    - On-request count and contested count
    - Percentage of adjournments requested
    """
    from sqlalchemy import text
    
    result = db.execute(
        text("""
        SELECT advocate_id, canonical_name, cases_with_adjournments,
               total_adjournment_events, requested_by_advocate, on_request_count,
               contested_count, percentage_requested_by_advocate, total_adjournment_requests,
               avg_adjournment_rate, total_cases_involved
        FROM advocate_adjournment_stats
        WHERE advocate_id = :advocate_id
        """),
        {"advocate_id": advocate_id}
    ).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Advocate not found")
    
    columns = [
        "advocate_id", "canonical_name", "cases_with_adjournments",
        "total_adjournment_events", "requested_by_advocate", "on_request_count",
        "contested_count", "percentage_requested_by_advocate", "total_adjournment_requests",
        "avg_adjournment_rate", "total_cases_involved"
    ]
    
    return {
        "advocate_id": advocate_id,
        "adjournment_stats": dict(zip(columns, result)),
    }


@router.get("/advocates/{advocate_id}/interim-app-activity")
def get_advocate_interim_app_activity(
    advocate_id: int,
    db: Session = Depends(get_db),
):
    """
    Get interim application filing patterns for an advocate.
    
    Shows by application type:
    - Applications filed
    - Grant/rejection/dismissal rates
    - Frivolous flagging percentage
    - Total delay caused
    """
    from sqlalchemy import text
    
    results = db.execute(
        text("""
        SELECT advocate_id, canonical_name, application_type, applications_filed,
               granted_count, rejected_count, dismissed_count, grant_percentage,
               flagged_frivolous_percentage, avg_delay_caused_days, total_delay_caused_days
        FROM advocate_interim_app_activity
        WHERE advocate_id = :advocate_id
        ORDER BY applications_filed DESC
        """),
        {"advocate_id": advocate_id}
    ).fetchall()
    
    if not results:
        raise HTTPException(status_code=404, detail="Advocate not found or no interim app activity")
    
    columns = [
        "advocate_id", "canonical_name", "application_type", "applications_filed",
        "granted_count", "rejected_count", "dismissed_count", "grant_percentage",
        "flagged_frivolous_percentage", "avg_delay_caused_days", "total_delay_caused_days"
    ]
    
    activity_by_type = [dict(zip(columns, row)) for row in results]
    
    return {
        "advocate_id": advocate_id,
        "interim_app_activity": activity_by_type,
    }

