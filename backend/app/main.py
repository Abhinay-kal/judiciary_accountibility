from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from app.api.router import api_router
from app.core.config import get_settings
from app.core.constants import DISCLAIMER_TEXT
from app.core.logging import setup_logging
from app.core.monitoring import MetricsMiddleware, metrics_response
from app.core.rate_limit import limiter

settings = get_settings()
setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Startup and shutdown lifecycle hooks."""

    if settings.cache_warmup_enabled:
        from app.tasks.cache_tasks import run_startup_cache_warmup

        run_startup_cache_warmup()

    yield


app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(MetricsMiddleware)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    """Readiness endpoint."""

    return {"status": "ok"}


@app.get("/disclaimer")
def disclaimer() -> dict[str, str]:
    """Public legal disclaimer."""

    return {"disclaimer": DISCLAIMER_TEXT}


@app.get("/metrics")
def metrics(_: Request):
    """Prometheus metrics endpoint for monitoring integrations."""

    return metrics_response()
