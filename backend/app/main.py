from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.constants import DISCLAIMER_TEXT
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Startup and shutdown lifecycle hooks."""

    yield


app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    """Readiness endpoint."""

    return {"status": "ok"}


@app.get("/disclaimer")
def disclaimer() -> dict[str, str]:
    """Public legal disclaimer."""

    return {"disclaimer": DISCLAIMER_TEXT}
