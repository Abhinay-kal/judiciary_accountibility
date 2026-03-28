# Judiciary Tracker: Complete Data Population & Integration Guide

## Overview

The judiciary tracker system processes data from **33 verified official Indian judiciary sources** and displays them through a unified web interface. This guide covers the complete data flow from ingestion to display.

## Architecture

```
┌─────────────────────────────────────────────┐
│ 33 Data Sources                             │
│ • 25 High Courts (all states)               │
│ • 4 National Tribunals (NCLT, NCLAT, etc)  │
│ • 4 National APIs (NJDG, eCourts, etc)      │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Ingestion Pipeline (Celery workers)         │
│ • Fetch from each source                    │
│ • Parse HTML/JSON/API responses             │
│ • Normalize case/hearing/judge data         │
│ • Insert into PostgreSQL                    │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ PostgreSQL Database                         │
│ • cases (case metadata)                     │
│ • hearings (hearing dates/outcomes)         │
│ • judges (judge assignments)                │
│ • courts (court definitions)                │
│ • ingestion_sources (source registry)       │
│ • population_runs (orchestration tracking)  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ FastAPI Backend                             │
│ • /api/v1/cases - case queries              │
│ • /api/v1/stats/court - court statistics    │
│ • /api/v1/judges - judge list               │
│ • /api/v1/admin/population/runs - tracking  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Next.js Frontend                            │
│ • /hub - unified interface                  │
│ • /search - case search                     │
│ • /cases/[id] - case detail                 │
│ • /judges - judge analytics                 │
└─────────────────────────────────────────────┘
```

## Current Status

✅ **Backend Configuration:**
- 33 verified sources defined in `app/ingestion/source_specs.py`
- 35 scrapers registered (includes legacy aliases)
- Dynamic HTML scraper generation for structurally similar courts
- All sources with correct priorities and metadata

✅ **Database Seeding:**
- All 33 sources inserted into `ingestion_sources` table
- Dedup-safe with `get_or_create` semantics
- Priority distribution: P1=1 (NJDG), P2=2 (eCourts/Supreme), P3=26 (High Courts), P4=4 (Tribunals)

✅ **Population Orchestration:**
- Celery-based fan-out to all 33 sources in parallel
- Population run (20260327-81d95283) active
- All 33 source-runs created and assigned to workers
- Monitoring API endpoints available

✅ **Frontend Integration:**
- Hub interface wired to `/stats/court`, `/judges`, `/flags`, `/datasets`
- Search page connected to `/cases` endpoint
- Case detail pages fetch full enrichments including impact/dormancy
- Population monitor shows run progress

## Files & Components

### Backend

| Component | Location | Purpose |
|-----------|----------|---------|
| Source Catalog | `backend/app/ingestion/source_specs.py` | 33 verified source specs (URLs, priorities, metadata) |
| Dynamic Scrapers | `backend/app/scrapers/sources/india_sources.py` | Generic HTML scraper generation for similar court structures |
| Scraper Registry | `backend/app/ingestion/pipeline.py` | Maps source names to scraper classes |
| Seeding Script | `backend/scripts/seed.py` | Populates `ingestion_sources` DB table |
| Population Orchestration | `backend/app/tasks/population.py` | Celery fan-out task that creates source-runs |
| Case API | `backend/app/api/routes/cases.py` | `/api/v1/cases` - queries with filters |
| Stats API | `backend/app/api/routes/stats.py` | `/api/v1/stats/court` - aggregated statistics |
| Status API | `backend/app/api/routes/status.py` | `/api/v1/status/integration-ready` - system readiness check |

### Frontend

| Page | Location | Purpose |
|------|----------|---------|
| Hub | `frontend/app/hub/page.tsx` | Unified interface with Overview/Search/Judges/Population sections |
| Search | `frontend/app/search/page.tsx` | Case search by court/party name |
| Case Detail | `frontend/app/cases/[id]/page.tsx` | Full case with timeline/summary/impact/provenance |
| Population Monitor | Embedded in hub | Tracks population run progress |

## How Data Flows

### 1. Ingestion Trigger
```
Admin clicks "Trigger Population" in Hub
  → FastAPI /admin/population/runs/trigger
    → Celery task start_population_run
      → Create PopulationRun record
      → Query all is_active=TRUE sources (33)
      → Create PopulationSourceRun for each
      → Schedule run_population_source tasks
```

### 2. Source Processing (Parallel)
```
For each of 33 sources in parallel:
  1. ResilientIngestionPipeline.run(source)
     ├─ Fetch URL (with retries)
     ├─ Parse HTML/JSON using registered scraper
     ├─ Normalize to case/hearing schema
     ├─ Upsert into cases/hearings tables
     ├─ Store raw payload to disk
     └─ Update ingestion_runs table
  2. Update PopulationSourceRun status
  3. Aggregator updates PopulationRun totals
```

### 3. Data Display
```
User opens /hub
  → Fetch /status/integration-ready (shows if ready)
  → Fetch /stats/court (shows backlog by court)
  → Fetch /flags (shows important cases)
  → Fetch /judges (judge list)
  
User searches cases
  → Query /cases?court=...&party_name=... 
  → Results from populated cases table
  
User clicks case detail
  → Query /cases/{id} (enriched: summary, impact, dormancy)
  → Query /cases/{id}/timeline (hearing history)
```

## Monitoring & Verification

### Check Population Progress
```bash
# Via monitoring script
docker exec -w /app justice-tracker-backend bash -c \
  "PYTHONPATH=/app python scripts/monitor_and_validate.py"
```

### Check Database Data
```bash
docker exec justice-tracker-db psql -U postgres -d justice_tracker -c "
SELECT COUNT(*) as case_count FROM cases WHERE is_deleted = FALSE;
SELECT COUNT(*) as source_count FROM ingestion_sources WHERE is_active = TRUE;
"
```

### Test Frontend Integration
```bash
# From workspace root
node frontend/scripts/test-integration.js
```

### View API Endpoints
```bash
# Swagger docs
open http://localhost:8000/docs

# Health check
curl http://localhost:8000/health

# Status endpoint
curl http://localhost:8000/api/v1/status/integration-ready | jq
```

## Interface Usage

### Hub (/hub)
1. **Overview**: Court statistics, backlog ratios, flagged cases
2. **Case Search**: Query by court, case number, party name
3. **Judges**: Judge list and adjournment rate analysis
4. **Heatmap**: Visual delay distribution by court
5. **Open Data**: Export datasets
6. **Corrections**: Submit case correction requests
7. **Feedback**: Moderate right-to-respond feedback
8. **Population**: Manual trigger and progress monitoring

### Search (/search)
- Query cases by keyword
- Results from live database
- Click to see full case detail

### Case Detail (/cases/[id])
- **Timeline**: Hearing history with outcomes
- **Summary**: AI-generated case summary
- **Impact**: Why this case matters
- **Dormancy**: Inactivity analysis
- **Provenance**: Data source tracking

## Operational Tasks

### Trigger a New Population Run
```bash
curl -X POST http://localhost:8000/api/v1/admin/population/runs/trigger \
  -H "Content-Type: application/json" \
  -d '{"admin_id": 1, "reason": "Regular refresh"}'
```

### Add a New Data Source
1. Add spec to `VERIFIED_INGESTION_SOURCES` in `source_specs.py`
2. Ensure scraper class exists (auto-generated or custom)
3. Re-run seed: `python scripts/seed.py`
4. Trigger population run

### View Scraper Registry
```bash
docker exec justice-tracker-backend python -c "
from app.ingestion.pipeline import ResilientIngestionPipeline
for key in sorted(ResilientIngestionPipeline._SCRAPER_REGISTRY.keys()):
    print(key)
"
```

## Troubleshooting

### No data appears in hub
1. Check population run status: `GET /admin/population/runs`
2. Verify database has cases: `SELECT COUNT(*) FROM cases`
3. Check scraper registry: Ensure all sources have registered scrapers
4. View logs: `docker logs justice-tracker-backend`

### Population sources failing
1. Check individual source health: `SELECT * FROM ingestion_sources`
2. Review ingestion runs: `SELECT * FROM ingestion_runs`
3. Check source URLs are reachable
4. Verify network connectivity from container

### Frontend not updating
1. Verify API endpoints: `node frontend/scripts/test-integration.js`
2. Check backend health: `curl http://localhost:8000/health`
3. Clear browser cache and refresh
4. Check NEXT_PUBLIC_API_BASE environment variable

## Performance Tuning

### Parallel Source Processing
- All 33 sources process simultaneously (23 high courts + 4 tribunals + 6 others)
- Typical ingestion: 2-15 minutes depending on source response times
- Implement backoff strategy for slow sources

### Database Optimization
- Indexes on cases(source_url), hearings(case_id)
- Batch inserts for upsert_case operations
- Cache court statistics in CourtStatsCache table

### Frontend Caching
- Deduped fetch requests (multiple identical requests in-flight = 1 query)
- Lazy loading for non-visible panels
- URL state persistence for deep linking

## Future Enhancements

- [ ] WebSocket updates for real-time population progress
- [ ] Machine learning predictions on case outcomes
- [ ] District courts ingestion (beyond high courts)
- [ ] Judge performance benchmarking
- [ ] Case similarity detection
- [ ] Automated impact narrative generation

## Support

For issues:
1. Check logs: `docker logs justice-tracker-backend`
2. Verify database: `docker exec justice-tracker-db psql ...`
3. Test APIs: `node frontend/scripts/test-integration.js`
4. Run monitoring: `python scripts/monitor_and_validate.py`
