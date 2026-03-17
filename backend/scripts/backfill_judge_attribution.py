from __future__ import annotations

import argparse
import json
from collections import Counter

from app.db.session import SessionLocal
from app.models import Hearing, JudgeAssignment
from app.services.judge_resolution import build_assignments_from_bench, raw_bench_snapshot_id


def run_backfill(*, dry_run: bool, limit: int) -> dict:
    db = SessionLocal()
    summary = Counter()
    try:
        hearings = (
            db.query(Hearing)
            .filter(Hearing.is_deleted.is_(False))
            .order_by(Hearing.id.asc())
            .limit(limit)
            .all()
        )
        for hearing in hearings:
            summary["hearings_scanned"] += 1
            payloads = build_assignments_from_bench(
                db,
                raw_bench=hearing.raw_bench or hearing.case.judges_text,
                court_id=hearing.case.court_id,
                source_name=hearing.source,
                hearing_date=hearing.date,
            )
            if not payloads:
                summary["ambiguous"] += 1
                continue

            for payload in payloads:
                summary["assignments_resolved"] += 1
                if payload.attribution_confidence < 0.6:
                    summary["low_confidence"] += 1
                if dry_run:
                    continue

                existing = (
                    db.query(JudgeAssignment)
                    .filter(
                        JudgeAssignment.hearing_id == hearing.id,
                        JudgeAssignment.judge_id == payload.judge_registry_id,
                        JudgeAssignment.sequence_index == payload.sequence_index,
                    )
                    .one_or_none()
                )
                if existing is not None:
                    summary["already_present"] += 1
                    continue

                db.add(
                    JudgeAssignment(
                        hearing_id=hearing.id,
                        judge_id=payload.judge_registry_id,
                        judge_name_raw=payload.judge_name_raw,
                        role=payload.role,
                        is_presiding=payload.is_presiding,
                        sequence_index=payload.sequence_index,
                        attribution_confidence=payload.attribution_confidence,
                        matched_on=payload.matched_on,
                        parser_version="judge-backfill-v1",
                        raw_bench_snapshot_id=raw_bench_snapshot_id(hearing.raw_bench),
                        metadata_json={"backfill": True, **payload.metadata_json},
                    )
                )
                summary["created"] += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()
        return dict(summary)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill judge assignments from existing hearing bench text")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing DB rows")
    parser.add_argument("--limit", type=int, default=5000, help="Maximum hearings to scan")
    args = parser.parse_args()
    summary = run_backfill(dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
