from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])


def per_minute_limit(request: Request) -> str:
    """Return endpoint limit string; supports future per-route overrides."""

    return f"{settings.rate_limit_per_minute}/minute"
