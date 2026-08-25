#!/usr/bin/env python3
"""Minimal loopback-only API for the immutable SADHANA mission projection."""

from __future__ import annotations

import inspect
import hashlib
import json
import os
import stat
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from api.mission_snapshot_provider import mission_snapshot_provider_from_environment
from api.routers.control_surface import control_surface_mission_snapshot

API_STATE_ROOT = "/var/lib/dharma-sadhana/api-state"
API_PORT = "18420"
SNAPSHOT_READINESS_PATH = (
    "/var/lib/dharma-sadhana/api-state/snapshot-readiness.v1.json"
)
_LOOPBACK_CLIENTS = {"127.0.0.1", "::1"}


class ImmutableObserverConfigurationError(RuntimeError):
    """The observer was not bound to the exact read-only campaign surface."""


def _snapshot_readiness() -> dict[str, Any]:
    path = os.fspath(SNAPSHOT_READINESS_PATH)
    try:
        identity = os.lstat(path)
    except FileNotFoundError:
        return {"status": "unknown", "reason": "no_capacity_receipt"}
    if (
        not stat.S_ISREG(identity.st_mode)
        or identity.st_uid != os.geteuid()
        or stat.S_IMODE(identity.st_mode) != 0o600
        or identity.st_nlink != 1
        or not 0 < identity.st_size <= 64 * 1024
    ):
        return {"status": "invalid", "reason": "capacity_receipt_custody"}
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        return {"status": "invalid", "reason": "nofollow_unavailable"}
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        before = os.fstat(descriptor)
        raw = os.read(descriptor, 64 * 1024 + 1)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if len(raw) > 64 * 1024 or (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        return {"status": "invalid", "reason": "capacity_receipt_changed"}
    try:
        payload = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError):
        return {"status": "invalid", "reason": "capacity_receipt_json"}
    if not isinstance(payload, dict):
        return {"status": "invalid", "reason": "capacity_receipt_shape"}
    digest = payload.get("receipt_digest")
    unsigned = dict(payload)
    unsigned.pop("receipt_digest", None)
    canonical = json.dumps(unsigned, separators=(",", ":"), sort_keys=True).encode(
        "ascii"
    )
    if (
        payload.get("schema_version") != "dharma.sadhana.snapshot_capacity_readiness.v1"
        or digest != hashlib.sha256(canonical).hexdigest()
        or raw
        != json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("ascii")
        + b"\n"
    ):
        return {"status": "invalid", "reason": "capacity_receipt_binding"}
    return {
        "status": payload.get("status"),
        "observed_at": payload.get("observed_at"),
        "free_bytes": payload.get("free_bytes"),
        "required_free_bytes_for_remaining_series": payload.get(
            "required_free_bytes_for_remaining_series"
        ),
        "remaining_snapshot_count": payload.get("remaining_snapshot_count"),
        "standby_capacity_proven": payload.get("standby_capacity_proven"),
    }


def create_app(
    provider_factory: Callable[[], Any] = mission_snapshot_provider_from_environment,
) -> FastAPI:
    """Compose only health plus the existing immutable snapshot endpoint."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if os.environ.get("DHARMA_STATE_DIR") != API_STATE_ROOT:
            raise ImmutableObserverConfigurationError(
                "DHARMA_STATE_DIR must be the separate disposable API state root"
            )
        if os.environ.get("SADHANA_API_PORT") != API_PORT:
            raise ImmutableObserverConfigurationError(
                "SADHANA_API_PORT must preserve the admitted collision-free port"
            )
        provider = provider_factory()
        if provider is None:
            raise ImmutableObserverConfigurationError(
                "immutable mission snapshot provider must be fully configured"
            )
        admit = getattr(provider, "admit", None)
        if callable(admit):
            candidate = admit()
            if inspect.isawaitable(candidate):
                await candidate
        if getattr(provider, "runtime_projection_mode", None) != "unavailable":
            raise ImmutableObserverConfigurationError(
                "provider must keep generic runtime projection unavailable"
            )
        app.state.mission_snapshot_provider = provider
        try:
            yield
        finally:
            if getattr(app.state, "mission_snapshot_provider", None) is provider:
                del app.state.mission_snapshot_provider

    observer = FastAPI(
        title="SADHANA immutable observer",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @observer.middleware("http")
    async def loopback_only(request: Request, call_next):  # noqa: ANN202
        client = request.client
        if client is None or client.host not in _LOOPBACK_CLIENTS:
            return JSONResponse(
                status_code=403,
                content={
                    "status": "rejected",
                    "reason": "observer accepts only the loopback dashboard proxy",
                },
            )
        return await call_next(request)

    @observer.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "mode": "immutable_observer",
            "runtime_projection_mode": "unavailable",
            "proves_executor_liveness": False,
            "write_routes": 0,
            "snapshot_readiness": _snapshot_readiness(),
        }

    @observer.get("/api/control-surface/missions/{mission_id}/snapshot")
    async def mission_snapshot(mission_id: str, request: Request) -> dict[str, Any]:
        if request.method != "GET":
            raise HTTPException(status_code=405, detail="read-only observer")
        return await control_surface_mission_snapshot(mission_id, request)

    return observer


app = create_app()
