# Multi-Queue Task Architecture

This document describes the Celery multi-queue implementation for workload isolation in the Court Case Delay & Justice Tracker backend.

## 1) Celery Configuration

Configured in `app/celery_app.py` and `app/queue/config.py`:

- Broker/result backend: Redis
- Deterministic queue routing enabled via custom route function
- Global reliability defaults:
  - `acks_late=true`
  - `reject_on_worker_lost=true`
  - `worker_prefetch_multiplier=1`
  - JSON serialization only

Environment controls:

- `INGESTION_WORKER_COUNT`
- `PARSING_WORKER_COUNT`
- `ANALYTICS_WORKER_COUNT`
- `NOTIFICATION_WORKER_COUNT`
- `QUEUE_PRIORITY_ENABLED`

## 2) Queue Definitions

Declared in `app/queue/config.py`:

- `ingestion`: scraper/network I/O
- `parsing`: extraction/normalization workloads
- `analytics`: CPU-heavy computations
- `notifications`: latency-sensitive alerts/webhooks

Each queue is configured with priority support (`x-max-priority=10`).

## 3) Routing Rules

Declared in `app/queue/routing.py`:

- `app.tasks.ingestion.*`, `app.tasks.ingestion_tasks.*` -> `ingestion`
- `app.tasks.reprocess.*`, `app.tasks.hearing_outcomes.*`, `app.tasks.judge_reconcile.*` -> `parsing`
- `app.tasks.delay_analytics.*`, `app.tasks.survival_analytics.*`, `app.tasks.ml_train.*`, `app.tasks.importance_recompute.*`, `app.tasks.cache_tasks.*` -> `analytics`
- `app.tasks.notifications.*` -> `notifications`

## 4) Worker Setup

Worker profiles in `app/queue/workers.py` set queue-specialized resource behavior:

- ingestion: high concurrency, high prefetch
- parsing: moderate concurrency and memory churn controls
- analytics: low concurrency, low prefetch, longer limits
- notifications: high responsiveness, short limits

Utility `worker_command(queue)` returns production-ready queue-specific worker launch command.

## 5) Retry Logic

Queue-specific retry policy in `app/queue/retry.py`:

- ingestion: exponential backoff (network failures)
- parsing: limited retries
- analytics: no auto-retry by default (manual review posture)
- notifications: fast retry

`retry_countdown(queue, retries)` provides deterministic backoff + bounded jitter.

## 6) Monitoring Utilities

`app/queue/monitoring.py` provides:

- Queue depth probes
- Consumer counts via Celery inspect
- Prometheus counters/histograms for processed/failed/latency/depth
- Ingestion pause flag in Redis for operational controls
- Backpressure hook: `apply_ingestion_backpressure`

## 7) API Tools

Admin endpoints in `app/api/routes/queue_admin.py`:

- `GET /api/v1/admin/queues/status` -> queue depth/consumers/profiles
- `POST /api/v1/admin/queues/ingestion/pause`
- `POST /api/v1/admin/queues/ingestion/resume`
- `POST /api/v1/admin/queues/jobs/trigger` -> allowlisted manual jobs
- `POST /api/v1/admin/queues/jobs/pipeline` -> orchestration chain trigger

## 8) Pipeline Orchestration

`pipeline_signature` in `app/queue/workers.py` builds ordered chain:

1. ingestion
2. parsing
3. analytics
4. notifications

Downstream stages execute only after upstream success.

## 9) Idempotency and Safety

`IdempotencyGuard` in `app/queue/retry.py` supports safe re-execution using Redis `SET NX EX` (with in-process fallback). Notification tasks use idempotency keys to prevent duplicate side effects.

Input validation for manual task triggers is enforced using Pydantic request models in admin queue endpoints.

## 10) Backpressure and Failure Isolation

Ingestion scheduler (`app.tasks.ingestion_tasks.run_ingestion_scheduler`) now:

- checks queue depth
- auto-pauses ingestion when threshold exceeded
- respects manual pause state

Analytics queue backlog does not block ingestion/parsing/notification workers due to separate queues and worker pools.

## 11) Testing

`tests/test_multi_queue_architecture.py` covers:

- routing correctness
- retry behavior
- failure isolation at routing level
- pipeline stage order
- idempotency guard semantics
