"""Model-pool API for the dashboard model screen.

This router exposes model availability and UI labels only. Provider secrets
remain in dkeys/agent_keys.env and are never accepted or returned here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import hashlib
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.models import ApiResponse
from dharma_swarm.model_pool_registry import ModelPoolEntry, build_model_pool_snapshot


router = APIRouter(prefix="/api/pool", tags=["pool"])

_STATE_DIR = Path.home() / ".dharma"
_PROFILE_PATH = _STATE_DIR / "model_pool_profiles.json"
_VERIFY_PATH = _STATE_DIR / "model_pool_verification.json"

_AVAILABLE_STATES = {"live_verified", "credential_present", "configured"}
_DEGRADED_STATES = {"degraded"}

_PROVIDER_URLS: dict[str, str] = {
    "anthropic": "https://console.anthropic.com/",
    "claude_code": "https://claude.ai/",
    "codex": "https://chatgpt.com/codex",
    "openai": "https://platform.openai.com/",
    "openrouter": "https://openrouter.ai/",
    "openrouter_free": "https://openrouter.ai/",
    "ollama": "https://ollama.com/",
    "nvidia_nim": "https://build.nvidia.com/",
    "google_ai": "https://aistudio.google.com/",
    "groq": "https://console.groq.com/",
    "cerebras": "https://cloud.cerebras.ai/",
    "siliconflow": "https://siliconflow.cn/",
    "together": "https://api.together.ai/",
    "fireworks": "https://fireworks.ai/",
    "mistral": "https://console.mistral.ai/",
    "chutes": "https://chutes.ai/",
    "zai_coding": "https://z.ai/",
    "zai_global": "https://z.ai/",
    "deepseek": "https://platform.deepseek.com/",
    "kimi": "https://platform.moonshot.ai/",
    "minimax": "https://www.minimax.io/",
}


class ModelProfilePatch(BaseModel):
    custom_label: str = ""
    short_name: str = ""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _model_id(entry: ModelPoolEntry) -> str:
    digest = hashlib.sha256(f"{entry.provider}\0{entry.model}".encode("utf-8")).hexdigest()
    return digest[:16]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _display_name(entry: ModelPoolEntry) -> str:
    model = entry.model.rsplit("/", 1)[-1].replace("_", " ").replace("-", " ")
    return " ".join(part.upper() if len(part) <= 3 else part.capitalize() for part in model.split())


def _strengths(entry: ModelPoolEntry) -> list[str]:
    values = [entry.lane_role, entry.cost_tier, *entry.tags]
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out[:6]


def _verification_for(entry: ModelPoolEntry) -> dict[str, Any]:
    status = "ok" if entry.availability in _AVAILABLE_STATES else "unverified"
    if entry.availability == "degraded":
        status = "unexpected"
    return {
        "status": status,
        "verified_at": None,
        "response_preview": entry.status or entry.availability,
        "error": None if status == "ok" else entry.status or entry.availability,
    }


def _entry_to_top_model(
    entry: ModelPoolEntry,
    *,
    rank: int,
    profiles: dict[str, Any],
    verifications: dict[str, Any],
) -> dict[str, Any]:
    model_id = _model_id(entry)
    profile = profiles.get(model_id, {})
    if not isinstance(profile, dict):
        profile = {}
    display_name = _display_name(entry)
    custom_label = str(profile.get("custom_label") or "").strip() or None
    short_name = str(profile.get("short_name") or "").strip() or None
    verification = verifications.get(model_id)
    if not isinstance(verification, dict):
        verification = _verification_for(entry)
    return {
        "id": model_id,
        "rank": rank,
        "provider": entry.provider,
        "display_name": display_name,
        "ui_label": custom_label or short_name or display_name,
        "custom_label": custom_label,
        "short_name": short_name,
        "max_context": entry.context_length or 0,
        "strengths": _strengths(entry),
        "available": entry.availability in _AVAILABLE_STATES,
        "available_routes": [entry.route] if entry.availability in _AVAILABLE_STATES else [],
        "routes": [entry.route],
        "notes": entry.status or entry.availability,
        "docs_url": _PROVIDER_URLS.get(entry.provider, "https://docs.dharma.local/"),
        "provider_url": _PROVIDER_URLS.get(entry.provider, "https://docs.dharma.local/"),
        "verification": verification,
    }


def _top_models(limit: int = 10) -> list[dict[str, Any]]:
    profiles = _load_json(_PROFILE_PATH)
    verifications = _load_json(_VERIFY_PATH)
    snapshot = build_model_pool_snapshot(refresh_nim=False)
    entries = sorted(
        snapshot.entries,
        key=lambda entry: (
            0
            if entry.availability in _AVAILABLE_STATES
            else 1
            if entry.availability in _DEGRADED_STATES
            else 2,
            -entry.power_score,
            entry.provider,
            entry.model,
        ),
    )
    return [
        _entry_to_top_model(
            entry,
            rank=index + 1,
            profiles=profiles,
            verifications=verifications,
        )
        for index, entry in enumerate(entries[:limit])
    ]


@router.get("/top10/status")
async def top10_status() -> ApiResponse:
    try:
        return ApiResponse(data=_top_models(10))
    except Exception as exc:
        return ApiResponse(status="error", data=[], error=str(exc))


@router.post("/top10/verify")
async def verify_top10() -> ApiResponse:
    try:
        models = _top_models(10)
        verified_at = _utc_now()
        verifications: dict[str, Any] = {}
        ok_count = 0
        for model in models:
            status = "ok" if model.get("available") else "unverified"
            if status == "ok":
                ok_count += 1
            verifications[str(model["id"])] = {
                "status": status,
                "verified_at": verified_at,
                "response_preview": model.get("notes") or model.get("provider"),
                "error": None if status == "ok" else model.get("notes") or "not callable",
            }
        _write_json(_VERIFY_PATH, verifications)
        return ApiResponse(data={"verified_at": verified_at, "ok_count": ok_count})
    except Exception as exc:
        return ApiResponse(status="error", data=None, error=str(exc))


@router.patch("/models/{model_id}/profile")
async def update_model_profile(model_id: str, body: ModelProfilePatch) -> ApiResponse:
    known_ids = {model["id"] for model in _top_models(40)}
    if model_id not in known_ids:
        raise HTTPException(status_code=404, detail=f"model '{model_id}' not found in model pool")
    profiles = _load_json(_PROFILE_PATH)
    profiles[model_id] = {
        "custom_label": body.custom_label.strip(),
        "short_name": body.short_name.strip(),
        "updated_at": _utc_now(),
    }
    _write_json(_PROFILE_PATH, profiles)
    return ApiResponse(
        data={
            "custom_label": profiles[model_id]["custom_label"] or None,
            "short_name": profiles[model_id]["short_name"] or None,
        }
    )
