from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

HTTP_REQUESTS_TOTAL = Counter(
    "justice_tracker_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "justice_tracker_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)
CACHE_HITS_TOTAL = Counter("justice_tracker_cache_hits_total", "Cache hits", ["namespace"])
CACHE_MISSES_TOTAL = Counter("justice_tracker_cache_misses_total", "Cache misses", ["namespace"])
SCRAPER_FETCH_TOTAL = Counter("justice_tracker_scraper_fetch_total", "Scraper fetch attempts", ["source", "result"])
INGESTION_RECORDS_TOTAL = Counter("justice_tracker_ingestion_records_total", "Ingestion processed records", ["source", "result"])
JUDGE_ATTRIBUTION_MISSING_TOTAL = Counter(
    "justice_tracker_judge_attribution_missing_total",
    "Hearings with no judge assignments",
    ["source"],
)
JUDGE_ATTRIBUTION_LOW_CONFIDENCE_TOTAL = Counter(
    "justice_tracker_judge_attribution_low_confidence_total",
    "Judge assignments with low attribution confidence",
    ["source"],
)
JUDGE_PROVISIONAL_CREATED_TOTAL = Counter(
    "justice_tracker_judge_provisional_created_total",
    "Provisional judge registry entries created",
    ["source"],
)
JUDGE_AMBIGUOUS_SOURCE_TOTAL = Counter(
    "justice_tracker_judge_ambiguous_source_total",
    "Ambiguous bench rows by source",
    ["source"],
)
CONTENT_LABELS_TOTAL = Counter(
    "justice_tracker_content_labels_total",
    "Content labels issued by moderation layer",
    ["label"],
)
CORRECTION_REQUESTS_TOTAL = Counter(
    "justice_tracker_correction_requests_total",
    "Correction requests by status",
    ["status"],
)
CORRECTION_RESOLUTION_SECONDS = Histogram(
    "justice_tracker_correction_resolution_seconds",
    "Time to resolution for correction requests",
    ["status"],
)
CONTENT_TAKEDOWNS_TOTAL = Counter(
    "justice_tracker_content_takedowns_total",
    "Number of hidden/takedown actions",
    ["target_type"],
)
LEGAL_ESCALATIONS_TOTAL = Counter(
    "justice_tracker_legal_escalations_total",
    "Number of legal escalations triggered",
    ["reason"],
)
FEEDBACK_SUBMISSIONS_TOTAL = Counter(
    "justice_tracker_feedback_submissions_total",
    "Number of RtR feedback submissions",
    ["responder_type", "received_via"],
)
FEEDBACK_VERIFICATIONS_TOTAL = Counter(
    "justice_tracker_feedback_verifications_total",
    "Number of RtR verification outcomes",
    ["method", "result"],
)
FEEDBACK_MODERATION_ACTIONS_TOTAL = Counter(
    "justice_tracker_feedback_moderation_actions_total",
    "Count of admin RtR moderation actions",
    ["action"],
)
FEEDBACK_PENDING_QUEUE = Gauge(
    "justice_tracker_feedback_pending_queue",
    "Current RtR pending queue length",
)
FEEDBACK_APPROVAL_SECONDS = Histogram(
    "justice_tracker_feedback_approval_seconds",
    "Time from submission to publish for RtR",
    buckets=(60, 300, 900, 3600, 21600, 43200, 86400, 172800, 604800),
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to expose per-request counters and latencies."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        path = request.url.path
        method = request.method
        status = str(response.status_code)

        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(elapsed)
        return response


def metrics_response() -> Response:
    """Return Prometheus metrics response."""

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
