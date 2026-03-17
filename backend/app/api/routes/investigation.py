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
