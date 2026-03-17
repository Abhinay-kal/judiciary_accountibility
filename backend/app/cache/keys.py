from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_SAFE_CHARS = re.compile(r"[^a-zA-Z0-9_:\-]")


def _sanitize_token(value: str) -> str:
    cleaned = _SAFE_CHARS.sub("_", value)
    return cleaned[:120]


def params_hash(params: dict[str, Any] | None) -> str:
    payload = json.dumps(params or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_cache_key(
    *,
    app_prefix: str,
    version: str,
    resource: str,
    identifier: str,
    params: dict[str, Any] | None = None,
    tenant: str | None = None,
) -> str:
    """Build centralized namespaced key: app:{resource}:{id}:{params_hash}."""

    prefix = _sanitize_token(app_prefix)
    ver = _sanitize_token(version)
    res = _sanitize_token(resource)
    ident = _sanitize_token(identifier)
    phash = params_hash(params)
    if tenant:
        return f"{prefix}:{ver}:{_sanitize_token(tenant)}:{res}:{ident}:{phash}"
    return f"{prefix}:{ver}:{res}:{ident}:{phash}"


def namespace_prefix(*, app_prefix: str, version: str, resource: str, tenant: str | None = None) -> str:
    prefix = _sanitize_token(app_prefix)
    ver = _sanitize_token(version)
    res = _sanitize_token(resource)
    if tenant:
        return f"{prefix}:{ver}:{_sanitize_token(tenant)}:{res}:"
    return f"{prefix}:{ver}:{res}:"
