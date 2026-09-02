"""Canonical model-status projection for router and operator surfaces.

This module is intentionally read-only: it projects the model pool plus safe
``dkeys`` status rows into one machine-readable contract. It never reads key
values, constructs providers, or makes model calls.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm import key_oracle
from dharma_swarm.helm_route_truth_codec import (
    helm_on_call_projection_from_dict as helm_on_call_projection_from_dict,
    helm_on_call_projection_to_dict as helm_on_call_projection_to_dict,
    route_evidence_from_dict as route_evidence_from_dict,
    route_verification_from_dict as route_verification_from_dict,
    route_verification_to_dict as route_verification_to_dict,
)
from dharma_swarm.helm_route_truth_evaluator import (
    HelmOnCallProjection as HelmOnCallProjection,
    RouteVerification as RouteVerification,
    evaluate_route_verification as evaluate_route_verification,
    project_helm_on_call as project_helm_on_call,
    unknown_helm_on_call_projection as unknown_helm_on_call_projection,
)
from dharma_swarm.helm_route_truth_types import (
    ACCEPTED_ROUTE_VERIFIER_ID as ACCEPTED_ROUTE_VERIFIER_ID,
    ACCEPTED_ROUTE_VERIFIER_VERSION as ACCEPTED_ROUTE_VERIFIER_VERSION,
    HELM_ON_CALL_PROJECTION_SCHEMA_VERSION as HELM_ON_CALL_PROJECTION_SCHEMA_VERSION,
    HELM_SLICE1_SEATS as HELM_SLICE1_SEATS,
    MAX_ROUTE_VERIFICATION_TTL as MAX_ROUTE_VERIFICATION_TTL,
    ROUTE_VERIFICATION_SCHEMA_VERSION as ROUTE_VERIFICATION_SCHEMA_VERSION,
    HelmOnCallState as HelmOnCallState,
    HelmSeat as HelmSeat,
    RouteEvidence as RouteEvidence,
    RouteVerdict as RouteVerdict,
    SanitizedRouteEvidence as SanitizedRouteEvidence,
)
from dharma_swarm.model_live_results import (
    TRANSIENT_LIVE_FAILURES as _TRANSIENT_LIVE_FAILURES,
    load_live_call_results,
)
from dharma_swarm import model_pool
from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.model_pool import ModelEntry, Route
from dharma_swarm.models import ProviderType

MODEL_STATUS_SCHEMA_VERSION = "dharma.model_status.v1"
LIVE_MODEL_E2E_ENV = "DHARMA_LIVE_MODEL_E2E"
PROFILE_PATH_ENV = "DHARMA_MODEL_PROFILE_PATH"
LIVE_CALL_MATRIX_PATH_ENV = "DHARMA_MODEL_LIVE_CALL_MATRIX_PATH"
LIVE_CALL_MATRIX_DIR_ENV = "DHARMA_MODEL_LIVE_CALL_MATRIX_DIR"
LIVE_CALL_MATRIX_MAX_AGE_HOURS_ENV = "DHARMA_MODEL_LIVE_CALL_MATRIX_MAX_AGE_HOURS"

_PROFILE_FILE_NAME = "model_pool_profiles.json"
_DEFAULT_LIVE_CALL_MATRIX_MAX_AGE_HOURS = 24.0
_LIVE_CALL_MATRIX_GLOBS = ("provider_live_matrix_*.json",)

_PROVIDER_LABELS: dict[str, str] = {
    "anthropic": "Anthropic",
    "claude_code": "Claude Code",
    "codex": "Codex",
    "openai": "OpenAI",
    "openrouter": "OpenRouter",
    "openrouter_free": "OpenRouter Free",
    "ollama": "Ollama",
    "nvidia_nim": "NVIDIA NIM",
    "google_ai": "Google AI",
    "deepseek": "DeepSeek",
    "kimi": "Kimi",
    "minimax": "MiniMax",
    "qwen": "Qwen",
    "local": "Local",
}

_PROVIDER_URLS: dict[str, str] = {
    "anthropic": "https://docs.anthropic.com/",
    "claude_code": "https://docs.anthropic.com/",
    "codex": "https://platform.openai.com/docs/",
    "openai": "https://platform.openai.com/docs/",
    "openrouter": "https://openrouter.ai/docs/",
    "openrouter_free": "https://openrouter.ai/docs/",
    "ollama": "https://docs.ollama.com/",
    "nvidia_nim": "https://docs.nvidia.com/nim/",
    "google_ai": "https://ai.google.dev/",
    "deepseek": "https://api-docs.deepseek.com/",
    "kimi": "https://platform.moonshot.ai/docs/",
    "minimax": "https://www.minimax.io/platform/document",
    "qwen": "https://help.aliyun.com/zh/model-studio/",
    "local": "https://docs.ollama.com/",
}

_SAFE_DKEYS_FIELDS = (
    "glyph",
    "provider",
    "cluster",
    "http",
    "status",
    "env_var",
)


@dataclass(frozen=True, slots=True)
class RouteStatus:
    provider: str
    model_id: str
    route: str
    status: str
    reason: str | None
    dkeys_row: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ModelVerification:
    status: str
    verified_at: str | None = None
    response_preview: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ModelStatus:
    id: str
    rank: int
    provider: str
    display_name: str
    ui_label: str
    custom_label: str | None
    short_name: str | None
    tier: str
    lane: str
    below_floor: bool
    max_context: int
    strengths: list[str]
    available: bool
    status: str
    unavailable_reason: str | None
    available_routes: list[str]
    routes: list[str]
    route_statuses: list[RouteStatus]
    notes: str | None
    docs_url: str
    provider_url: str
    verification: ModelVerification


@dataclass(frozen=True, slots=True)
class ModelStatusProjection:
    schema_version: str
    generated_at: str
    oracle_state: str
    live_providers: list[str] | None
    models: list[ModelStatus]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _profile_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    raw = os.getenv(PROFILE_PATH_ENV)
    if raw:
        return Path(raw).expanduser()
    return dharma_state_dir() / _PROFILE_FILE_NAME


def load_profiles(path: Path | None = None) -> dict[str, dict[str, str | None]]:
    target = _profile_path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, str | None]] = {}
    for model_id, profile in data.items():
        if not isinstance(model_id, str) or not isinstance(profile, dict):
            continue
        custom_label = profile.get("custom_label")
        short_name = profile.get("short_name")
        out[model_id] = {
            "custom_label": custom_label if isinstance(custom_label, str) else None,
            "short_name": short_name if isinstance(short_name, str) else None,
        }
    return out


def save_profile(
    model_id: str,
    *,
    custom_label: str | None,
    short_name: str | None,
    path: Path | None = None,
) -> dict[str, str | None]:
    profiles = load_profiles(path)
    profile = {
        "custom_label": _clean_profile_text(custom_label),
        "short_name": _clean_profile_text(short_name),
    }
    profiles[model_id] = profile
    target = _profile_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profiles, indent=2, sort_keys=True), encoding="utf-8")
    return profile


def _clean_profile_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split()).strip()
    return cleaned[:80] if cleaned else None


def _status_data() -> dict[str, Any] | None:
    loader = getattr(key_oracle, "_load_status")
    data = loader()
    return data if isinstance(data, dict) else None


def _live_call_matrix_path() -> Path | None:
    raw = os.getenv(LIVE_CALL_MATRIX_PATH_ENV)
    if not raw:
        return _discover_live_call_matrix_path()
    return Path(raw).expanduser()


def _live_call_matrix_dir() -> Path:
    raw = os.getenv(LIVE_CALL_MATRIX_DIR_ENV)
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parents[1] / "reports" / "langgraph_parity" / "allnight"


def _live_call_matrix_max_age_hours() -> float:
    raw = os.getenv(LIVE_CALL_MATRIX_MAX_AGE_HOURS_ENV)
    if not raw:
        return _DEFAULT_LIVE_CALL_MATRIX_MAX_AGE_HOURS
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return _DEFAULT_LIVE_CALL_MATRIX_MAX_AGE_HOURS


def _parse_receipt_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _receipt_generated_at(path: Path) -> datetime | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    schema = str(data.get("schema_version") or "")
    if schema and schema != "dharma.provider_live_matrix_closeout.v1":
        return None
    parsed = _parse_receipt_time(data.get("generated_at"))
    if parsed is not None:
        return parsed
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return None


def _discover_live_call_matrix_path(now: datetime | None = None) -> Path | None:
    directory = _live_call_matrix_dir()
    if not directory.exists():
        return None
    current = now or datetime.now(timezone.utc)
    max_age = _live_call_matrix_max_age_hours()
    candidates: list[tuple[datetime, Path]] = []
    for pattern in _LIVE_CALL_MATRIX_GLOBS:
        for path in directory.glob(pattern):
            if not path.is_file():
                continue
            generated_at = _receipt_generated_at(path)
            if generated_at is None:
                continue
            age_hours = max((current - generated_at).total_seconds(), 0.0) / 3600.0
            if age_hours <= max_age:
                candidates.append((generated_at, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1].name))[1]


def _live_call_results(path: Path | None = None) -> dict[str, dict[str, Any]]:
    target = path or _live_call_matrix_path()
    return load_live_call_results(target)


def _provider_row_key(provider: ProviderType | str) -> str | None:
    provider_name = provider.value if isinstance(provider, ProviderType) else str(provider)
    mapping = getattr(key_oracle, "_PROVIDER_TO_ROW")
    return mapping.get(provider_name, provider_name)


def _safe_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    return {field: row.get(field) for field in _SAFE_DKEYS_FIELDS if field in row}


def _row_for_provider(provider: ProviderType, status_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if status_data is None:
        return None
    rows = status_data.get("rows")
    if not isinstance(rows, dict):
        return None
    row_key = _provider_row_key(provider)
    if row_key is None:
        return None
    return rows.get(row_key) if isinstance(rows.get(row_key), dict) else None


def _classify_route(
    route: Route,
    *,
    live: set[str] | None,
    status_data: dict[str, Any] | None,
    live_results: dict[str, dict[str, Any]],
) -> RouteStatus:
    route_id = f"{route.provider.value}:{route.model_id}"
    live_result = live_results.get(route_id)
    if live_result is not None:
        result_status = str(live_result.get("status", "")).strip()
        if result_status == "ok":
            return RouteStatus(
                provider=route.provider.value,
                model_id=route.model_id,
                route=route_id,
                status="live_routable",
                reason=None,
                dkeys_row=_safe_row(_row_for_provider(route.provider, status_data)),
            )
        if result_status == "failed":
            reason = str(live_result.get("failure_class") or "routing_bug")
            if reason in _TRANSIENT_LIVE_FAILURES:
                return RouteStatus(
                    provider=route.provider.value,
                    model_id=route.model_id,
                    route=route_id,
                    status="live_routable",
                    reason=None,
                    dkeys_row=_safe_row(_row_for_provider(route.provider, status_data)),
                )
            return RouteStatus(
                provider=route.provider.value,
                model_id=route.model_id,
                route=route_id,
                status="unavailable",
                reason=reason,
                dkeys_row=_safe_row(_row_for_provider(route.provider, status_data)),
            )
    if live is None:
        return RouteStatus(
            provider=route.provider.value,
            model_id=route.model_id,
            route=route_id,
            status="unverified",
            reason="key_status_unknown",
            dkeys_row=None,
        )
    if route.provider.value in live:
        return RouteStatus(
            provider=route.provider.value,
            model_id=route.model_id,
            route=route_id,
            status="live_routable",
            reason=None,
            dkeys_row=_safe_row(_row_for_provider(route.provider, status_data)),
        )
    row = _row_for_provider(route.provider, status_data)
    reason = _classify_unavailable_reason(row)
    return RouteStatus(
        provider=route.provider.value,
        model_id=route.model_id,
        route=route_id,
        status="unavailable",
        reason=reason,
        dkeys_row=_safe_row(row),
    )


def _classify_unavailable_reason(row: dict[str, Any] | None) -> str:
    if row is None:
        return "key_missing"
    glyph = str(row.get("glyph", "")).strip()
    http = str(row.get("http", "")).strip()
    status = str(row.get("status", "")).lower()
    if glyph == "·" or "no key" in status:
        return "key_missing"
    if glyph == "$" or "funds=0" in status or "insufficient" in status:
        return "quota"
    if glyph == "~" or http == "429" or "rate" in status:
        return "rate_limited"
    if "model" in status and ("missing" in status or "not found" in status):
        return "model_missing"
    if http == "404":
        return "provider_dead"
    if http == "400" or http == "401" or http == "403" or glyph == "✗":
        return "provider_dead"
    return "provider_dead"


def _dominant_reason(route_statuses: Iterable[RouteStatus]) -> str | None:
    reasons = [route.reason for route in route_statuses if route.reason]
    if not reasons:
        return None
    for reason in (
        "key_status_unknown",
        "key_missing",
        "rate_limited",
        "quota",
        "model_missing",
        "provider_dead",
        "unsupported_route",
        "timeout",
        "schema_failure",
        "routing_bug",
    ):
        if reason in reasons:
            return reason
    return reasons[0]


def _verification_for_model(
    model_id: str,
    route_statuses: Iterable[RouteStatus],
    live_results: dict[str, dict[str, Any]],
) -> ModelVerification:
    for route_status in route_statuses:
        live_result = live_results.get(route_status.route)
        if live_result is None:
            continue
        verified_at = live_result.get("started_at") if isinstance(live_result.get("started_at"), str) else None
        if live_result.get("status") == "ok":
            preview = live_result.get("response_preview")
            return ModelVerification(
                status="verified",
                verified_at=verified_at,
                response_preview=preview if isinstance(preview, str) else None,
                error=None,
            )
        error = live_result.get("reason") or live_result.get("error") or live_result.get("failure_class")
        return ModelVerification(
            status="failed",
            verified_at=verified_at,
            response_preview=None,
            error=str(error) if error else "Live model-call receipt failed.",
        )
    return ModelVerification(
        status="unverified",
        verified_at=None,
        response_preview=None,
        error="No live model-call receipt has been recorded for this projection.",
    )


def _model_status(
    entry: ModelEntry,
    *,
    rank: int,
    live: set[str] | None,
    status_data: dict[str, Any] | None,
    live_results: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, str | None]],
) -> ModelStatus:
    route_statuses = [
        _classify_route(route, live=live, status_data=status_data, live_results=live_results)
        for route in entry.routes
    ]
    available_routes = [
        route_status.route
        for route_status in route_statuses
        if route_status.status == "live_routable"
    ]
    has_live_evidence = any(live_results.get(route_status.route) is not None for route_status in route_statuses)
    oracle_unknown = live is None and not has_live_evidence
    available = bool(available_routes)
    status = "unverified" if oracle_unknown else ("live_routable" if available else "unavailable")
    reason = "key_status_unknown" if oracle_unknown else _dominant_reason(route_statuses)
    primary_route = route_statuses[0]
    profile = profiles.get(entry.id, {})
    label = profile.get("custom_label") or entry.display
    provider = primary_route.provider
    return ModelStatus(
        id=entry.id,
        rank=rank,
        provider=provider,
        display_name=entry.display,
        ui_label=label,
        custom_label=profile.get("custom_label"),
        short_name=profile.get("short_name"),
        tier=entry.tier.value,
        lane="grunt" if entry.below_floor else "floor",
        below_floor=entry.below_floor,
        max_context=entry.context,
        strengths=list(entry.caps),
        available=available,
        status=status,
        unavailable_reason=reason if not available else None,
        available_routes=available_routes,
        routes=[route_status.route for route_status in route_statuses],
        route_statuses=route_statuses,
        notes=_notes_for(entry, status=status, reason=reason),
        docs_url=_PROVIDER_URLS.get(provider, "https://docs.dharma.local/models"),
        provider_url=_PROVIDER_URLS.get(provider, "https://docs.dharma.local/models"),
        verification=_verification_for_model(entry.id, route_statuses, live_results),
    )


def _notes_for(entry: ModelEntry, *, status: str, reason: str | None) -> str:
    if entry.below_floor:
        return "Sub-floor model: grunt-only, never part of the default operator path."
    if status == "live_routable":
        return "Live-routable by current key oracle; live model-call receipt still required for verified status."
    if status == "unverified":
        return "Key status is missing or stale; surface must not advertise this model as callable."
    return f"Unavailable: {reason or 'no live route'}."


def project_model_status(
    *,
    entries: Iterable[ModelEntry] | None = None,
    profiles_path: Path | None = None,
) -> ModelStatusProjection:
    live = key_oracle.live_providers(probe=False)
    status_data = _status_data()
    live_results = _live_call_results()
    profiles = load_profiles(profiles_path)
    selected = list(entries) if entries is not None else list(model_pool.all_entries())
    models = [
        _model_status(
            entry,
            rank=index,
            live=live,
            status_data=status_data,
            live_results=live_results,
            profiles=profiles,
        )
        for index, entry in enumerate(selected, start=1)
    ]
    return ModelStatusProjection(
        schema_version=MODEL_STATUS_SCHEMA_VERSION,
        generated_at=_utc_now(),
        oracle_state="unknown" if live is None else "fresh",
        live_providers=sorted(live) if live is not None else None,
        models=models,
    )


def floor_model_status(*, profiles_path: Path | None = None) -> ModelStatusProjection:
    return project_model_status(entries=model_pool.floor_entries(), profiles_path=profiles_path)


def all_model_status(*, profiles_path: Path | None = None) -> ModelStatusProjection:
    return project_model_status(entries=model_pool.all_entries(), profiles_path=profiles_path)


def projection_to_dict(projection: ModelStatusProjection) -> dict[str, Any]:
    return asdict(projection)


def top_floor_models_for_dashboard(*, profiles_path: Path | None = None) -> list[dict[str, Any]]:
    projection = floor_model_status(profiles_path=profiles_path)
    return [asdict(model) for model in projection.models]


def verify_floor_models(*, profiles_path: Path | None = None) -> dict[str, Any]:
    projection = floor_model_status(profiles_path=profiles_path)
    verified_at = _utc_now()
    live_enabled = os.getenv(LIVE_MODEL_E2E_ENV) == "1"
    if not live_enabled:
        return {
            "verified_at": verified_at,
            "ok_count": 0,
            "live_calls_attempted": False,
            "skipped_count": len(projection.models),
            "reason": f"{LIVE_MODEL_E2E_ENV}=1 is required for live model calls.",
        }
    return {
        "verified_at": verified_at,
        "ok_count": 0,
        "live_calls_attempted": False,
        "skipped_count": len(projection.models),
        "reason": "Live verification is performed by scripts/verify/model_pool_e2e.py receipts, not this API route.",
    }


__all__ = [
    "ACCEPTED_ROUTE_VERIFIER_ID",
    "ACCEPTED_ROUTE_VERIFIER_VERSION",
    "HELM_ON_CALL_PROJECTION_SCHEMA_VERSION",
    "HELM_SLICE1_SEATS",
    "LIVE_MODEL_E2E_ENV",
    "MAX_ROUTE_VERIFICATION_TTL",
    "MODEL_STATUS_SCHEMA_VERSION",
    "ROUTE_VERIFICATION_SCHEMA_VERSION",
    "HelmOnCallProjection",
    "HelmOnCallState",
    "HelmSeat",
    "ModelStatus",
    "ModelStatusProjection",
    "ModelVerification",
    "RouteEvidence",
    "RouteStatus",
    "RouteVerdict",
    "RouteVerification",
    "SanitizedRouteEvidence",
    "all_model_status",
    "evaluate_route_verification",
    "floor_model_status",
    "helm_on_call_projection_from_dict",
    "helm_on_call_projection_to_dict",
    "load_profiles",
    "project_helm_on_call",
    "projection_to_dict",
    "route_evidence_from_dict",
    "route_verification_from_dict",
    "route_verification_to_dict",
    "save_profile",
    "top_floor_models_for_dashboard",
    "unknown_helm_on_call_projection",
    "verify_floor_models",
]
