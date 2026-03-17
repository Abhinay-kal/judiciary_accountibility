from __future__ import annotations

from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.models import JudgeAttributionAudit, JudgeRegistry
from app.services.judge_resolution import suggest_registry_merges


@celery_app.task(name="app.tasks.judge_reconcile.reconcile_judges")
def reconcile_judges(limit: int = 200) -> dict:
    from app.core.config import get_settings

    settings = get_settings()
    db = SessionLocal()
    try:
        suggestions = suggest_registry_merges(db, limit=limit)
        for suggestion in suggestions:
            db.add(
                JudgeAttributionAudit(
                    action="merge_suggestion",
                    judge_registry_id=suggestion["target_judge_id"],
                    reason="Automatic duplicate suggestion",
                    old_value={"candidate": suggestion["candidate_judge_id"]},
                    new_value=suggestion,
                )
            )

        retention_cutoff = datetime.utcnow() - timedelta(days=settings.judge_provisional_retention_days)
        stale = (
            db.query(JudgeRegistry)
            .filter(
                JudgeRegistry.is_provisional.is_(True),
                JudgeRegistry.last_seen.isnot(None),
                JudgeRegistry.last_seen < retention_cutoff,
            )
            .all()
        )
        for entry in stale:
            entry.metadata_json = {
                **entry.metadata_json,
                "stale_provisional": True,
                "stale_marked_at": datetime.utcnow().isoformat(),
            }

        db.commit()
        return {
            "suggestions": len(suggestions),
            "stale_provisional_marked": len(stale),
        }
    finally:
        db.close()


@celery_app.task(name="app.tasks.judge_reconcile.seed_official_judge_registry")
def seed_official_judge_registry(seed_rows: list[dict] | None = None) -> dict:
    rows = seed_rows or []
    db = SessionLocal()
    created = 0
    try:
        for row in rows:
            canonical_name = (row.get("canonical_name") or "").strip()
            if not canonical_name:
                continue
            existing = db.query(JudgeRegistry).filter(JudgeRegistry.canonical_name == canonical_name).first()
            if existing:
                continue
            db.add(
                JudgeRegistry(
                    canonical_name=canonical_name,
                    name_variants={"variants": row.get("name_variants") or [canonical_name]},
                    phonetic_keys={"keys": row.get("phonetic_keys") or []},
                    service_number=row.get("service_number"),
                    court_id=row.get("court_id"),
                    known_designations={"values": row.get("known_designations") or []},
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                    metadata_json={"seed_source": row.get("seed_source") or "official_list"},
                    is_provisional=False,
                )
            )
            created += 1
        db.commit()
        return {"created": created, "provided": len(rows)}
    finally:
        db.close()
