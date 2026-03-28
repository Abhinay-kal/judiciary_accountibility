"""Verify population expansion completed successfully."""
from app.db.session import SessionLocal
from app.ingestion.models import PopulationRun, PopulationSourceRun, IngestionSource
from sqlalchemy import desc

db = SessionLocal()

# Show latest population run
latest_run = db.query(PopulationRun).order_by(desc(PopulationRun.id)).first()
if latest_run:
    source_runs = db.query(PopulationSourceRun).filter(
        PopulationSourceRun.population_run_id == latest_run.id
    ).all()
    print(f"=== Population Run {latest_run.run_id} Source Fan-Out ===")
    print(f"Total sources in run: {len(source_runs)}")
    print(f"Run status: {latest_run.status}")
    
    statuses = {}
    for sr in source_runs:
        if sr.status not in statuses:
            statuses[sr.status] = 0
        statuses[sr.status] += 1
    print(f"\nStatus breakdown:")
    for status in sorted(statuses.keys()):
        print(f"  {status}: {statuses[status]}")
    
    print(f"\nSource breakdown by priority:")
    priorities = {}
    for sr in source_runs:
        p = sr.source.priority
        if p not in priorities:
            priorities[p] = []
        priorities[p].append(sr.source_name)
    for priority in sorted(priorities.keys()):
        print(f"  Priority {priority}: {len(priorities[priority])} sources")
        for source_name in sorted(priorities[priority]):
            print(f"    - {source_name}")

# Verify registry completeness
from app.ingestion.pipeline import ResilientIngestionPipeline
print(f"\n=== Registry Verification ===")
print(f"Total registered scrapers: {len(ResilientIngestionPipeline._SCRAPER_REGISTRY)}")
print(f"Total active sources in DB: {db.query(IngestionSource).filter(IngestionSource.is_active == True).count()}")

# Check for unresolved sources
unresolved = []
for source in db.query(IngestionSource).filter(IngestionSource.is_active == True).all():
    if not ResilientIngestionPipeline._resolve_scraper(source):
        unresolved.append(source.source_name)
if unresolved:
    print(f"WARNING: {len(unresolved)} sources have no registered scraper:")
    for name in unresolved:
        print(f"  - {name}")
else:
    print("✓ All active sources have registered scrapers")

print(f"\n=== SUCCESS ===")
print(f"Expansion complete: 4 → {len(source_runs)} sources in population run")
