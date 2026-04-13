"""Proxy selected live daemon truth into the dashboard API."""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter

from api.models import ApiResponse

router = APIRouter(prefix="/api/daemon", tags=["daemon"])


def _daemon_base_url() -> str:
    return os.environ.get("DHARMA_DAEMON_URL", "http://127.0.0.1:7433").rstrip("/")


@router.get("/health")
async def daemon_health() -> ApiResponse:
    url = f"{_daemon_base_url()}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        return ApiResponse(data=response.json())
    except Exception as exc:
        return ApiResponse(
            status="error",
            data=None,
            error=f"daemon health unavailable: {exc}",
        )
