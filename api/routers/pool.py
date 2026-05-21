"""Dashboard model-pool compatibility endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any

from fastapi import APIRouter

from api.models import ApiResponse

router = APIRouter(prefix="/api/pool", tags=["pool"])

_MODEL_ROWS: list[dict[str, Any]] = [
    {
        "id": "claude_opus",
        "rank": 1,
        "provider": "openrouter",
        "display_name": "Claude Opus 4.6",
        "ui_label": "Opus",
        "max_context": 200_000,
        "strengths": ["strategy", "synthesis", "operator reasoning"],
        "routes": ["claude_opus"],
        "notes": "Served through the dashboard chat profile when configured.",
    },
    {
        "id": "codex_operator",
        "rank": 2,
        "provider": "openai",
        "display_name": "Codex 5.4",
        "ui_label": "Codex",
        "max_context": 200_000,
        "strengths": ["implementation", "diagnostics", "repo edits"],
        "routes": ["codex_operator"],
        "notes": "Implementation lane for bounded engineering work.",
    },
    {
        "id": "qwen35_surgeon",
        "rank": 3,
        "provider": "groq",
        "display_name": "Qwen3.5 Surgical Coder",
        "ui_label": "Qwen",
        "max_context": 32_000,
        "strengths": ["fast coding", "bounded fixes", "triage"],
        "routes": ["qwen35_surgeon"],
        "notes": "Fast surgical lane when Groq is configured.",
    },
    {
        "id": "glm5_researcher",
        "rank": 4,
        "provider": "openrouter",
        "display_name": "GLM-5 Cartographer",
        "ui_label": "GLM-5",
        "max_context": 128_000,
        "strengths": ["research", "cartography", "pattern extraction"],
        "routes": ["glm5_researcher"],
        "notes": "Synthesis lane when OpenRouter is configured.",
    },
]

_PROVIDER_ENV = {
    "groq": ("GROQ_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
}


def _provider_available(provider: str) -> bool:
    return any(os.environ.get(name) for name in _PROVIDER_ENV.get(provider, ()))


@router.get("/top10/status")
async def top10_status() -> ApiResponse:
    rows = []
    for row in _MODEL_ROWS:
        available = _provider_available(str(row["provider"]))
        rows.append({
            **row,
            "available": available,
            "available_routes": row.get("routes", []) if available else [],
            "verification": {
                "status": "configured" if available else "missing_key",
                "verified_at": None,
                "response_preview": None,
                "error": None if available else f"{row['provider']} API key is not present",
            },
        })
    return ApiResponse(data=rows)


@router.post("/top10/verify")
async def verify_top10() -> ApiResponse:
    rows = [row for row in _MODEL_ROWS if _provider_available(str(row["provider"]))]
    return ApiResponse(data={
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "ok_count": len(rows),
    })


@router.patch("/models/{model_id}/profile")
async def update_model_profile(model_id: str, body: dict[str, Any]) -> ApiResponse:
    return ApiResponse(data={
        "custom_label": body.get("custom_label"),
        "short_name": body.get("short_name"),
    })
