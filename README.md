# Court Case Delay & Justice Tracker - India

Public accountability MVP for tracking court timelines, adjournments, delay patterns, disposal rates, and potential public-official involvement in Indian court cases.

## Legal Disclaimer

Data aggregated from public judicial sources. Verify with official records.

## Project Structure

```text
judiciary_accountibility/
  backend/
    alembic/
      versions/0001_initial.py
    app/
      api/routes/
      core/
      db/
      models/
      schemas/
      scrapers/sources/
      services/
      tasks/
      utils/
      main.py
      celery_app.py
    scripts/seed.py
    tests/
    requirements.txt
    Dockerfile
  frontend/
    app/
      cases/[id]/page.tsx
      judges/[id]/page.tsx
      heatmap/page.tsx
      search/page.tsx
      layout.tsx
      page.tsx
      globals.css
    components/
    package.json
    Dockerfile
  docker-compose.yml
  .env.example
  Makefile
```

## Backend Overview

- Python 3.11 + FastAPI + SQLAlchemy 2.0
- PostgreSQL + Alembic migrations
- Celery + Redis for daily ingestion jobs
- Scrapers implemented for:
  - NJDG
  - eCourts Services
  - High Court cause lists (HTML + PDF parser integration)
  - Supreme Court cause lists
- Raw response storage under `backend/raw_data/` for auditability
- Idempotent normalization/upsert pipeline
- Delay metrics and anomaly flags
- Public-official CSV import + fuzzy matching (RapidFuzz)

### Required Tables

Implemented via SQLAlchemy models and migration:

- `courts`
- `judges`
- `cases`
- `hearings`
- `adjournments`
- `orders`
- `flags`
- `public_officials`
- `case_party_links`
- `ingestion_logs`

Includes indexes and soft-delete columns (`is_deleted`, `deleted_at`).

## API Endpoints

Base prefix: `/api/v1`

- `GET /courts`
- `GET /cases`
- `GET /cases/{id}`
- `GET /cases/{id}/timeline`
- `GET /judges`
- `GET /judges/{id}`
- `GET /judges/{id}/stats`
- `GET /stats/court`
- `GET /stats/judge`
- `GET /flags`
- `GET /disclaimer`
- `GET /health`

`GET /cases` supports filtering with:

- `court`
- `state`
- `case_type`
- `party_name`
- `start_date`, `end_date`
- `flagged_only`
- `politician_only`
- `page`, `page_size`

## Delay Metrics Engine

Implemented metrics:

- Time to disposal
- Time between hearings
- Adjournment rate per case
- Adjournment rate per judge
- Court backlog indicators

Anomaly flags created where:

- Time between hearings > 2x court median
- Adjournment rate > mean + 2 standard deviations

## Local Development

### 1. Configure env

```bash
cp .env.example .env
```

### 2. Start stack

```bash
make up
```

### 3. Apply migrations

```bash
make migrate
```

### 4. Seed sample data

```bash
make seed
```

### 5. Run tests

```bash
make test
```

Frontend: http://localhost:3000  
Backend API docs: http://localhost:8000/docs

## Daily Scheduler

Celery Beat triggers daily ingestion task:

- Task: `app.tasks.ingestion.run_daily_ingestion`
- Schedule: daily at 02:00 UTC

## Security and Data Safety Notes

- No write-back to court systems.
- Ingestion is read-only.
- Raw payload references are retained for audits.
- Soft-delete strategy preserves historical records.
- No hardcoded secrets; env-driven config.

## Known MVP Limits

- Source parser rules are initial adapters and need source-specific hardening for production anti-bot and schema drift.
- eCourts/NJDG may require captcha-aware or API-backed ingestion in real deployments.
- Frontend heatmap currently uses card-based intensity rendering; geo-map integration can be added with Leaflet in next iteration.
