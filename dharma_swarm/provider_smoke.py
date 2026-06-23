"""Provider smoke tests with evidence-rich status output."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import uuid4

from dharma_swarm.api_keys import OLLAMA_API_KEY_ENV, env_has_value
from dharma_swarm.evolution_roster import ModelTier
from dharma_swarm.model_pool import (
    provider_model_ids,
    strong_vendor_model_ids,
)
from dharma_swarm.models import LLMRequest, ProviderType
from dharma_swarm.ollama_config import (
    OLLAMA_CLOUD_FRONTIER_MODELS,
)
from dharma_swarm.runtime_provider import (
    NVIDIA_NIM_BASE_URL,
    OPENROUTER_BASE_URL,
    create_runtime_provider,
    resolve_runtime_provider_config,
)
from dharma_swarm.telemetry_plane import (
    ExternalOutcomeRecord,
    TelemetryPlaneStore,
)


_SIZE_RE = re.compile(r"(?P<size>\d+(?:\.\d+)?)\s*(?P<unit>[bkmg]?)", re.I)
_OLLAMA_ROOT_ERROR_MARKERS = (
    "ensure path elements are traversable",
    ".ollama: file exists",
)
_PROVIDER_WIDE_TERMINAL_STATUSES = {
    "auth_failed",
    "insufficient_credits",
    "missing_config",
}
# STEP 6 of the model-routing consolidation: these smoke catalogs are no longer
# hand-typed frontier literals — they are GENERATORS over the ONE model_pool.
# Model-id strings come from the pool (one source); only the smoke probe
# *ordering* (a smoke-lane policy: lead with the high-stakes reasoning model) is
# applied here. Pool order already leads OpenRouter STRONG with kimi-k2.5.


def _ordered(prefer: tuple[str, ...], pool_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Smoke probe order: preferred ids first (if the pool serves them), then the
    rest of the pool ids in pool order, deduped. The preference list never
    invents an id — it only re-orders ids the pool already owns."""
    out: list[str] = [m for m in prefer if m in pool_ids]
    out.extend(m for m in pool_ids if m not in out)
    return tuple(out)


def _nim_hosted_frontier_models() -> tuple[str, ...]:
    """NVIDIA-NIM hosted-API smoke catalog — projected from the pool's NIM routes.

    Lead with the NIM-native reasoning lane, then the re-hosted workhorses. The
    lead is DERIVED from the pool, not a literal: among the pool's NIM routes,
    the NIM-native (``nvidia/`` vendor namespace) ids come first — that is the
    large dedicated reasoning model NVIDIA serves first-party — then the rest in
    pool order. Every string is a pool route."""
    nim_ids = provider_model_ids(ProviderType.NVIDIA_NIM)
    nim_native = tuple(m for m in nim_ids if m.startswith("nvidia/"))
    return _ordered(nim_native, nim_ids)


def _nim_self_hosted_frontier_models() -> tuple[str, ...]:
    """NVIDIA-NIM self-hosted smoke catalog — STRONG-tier open weights served via
    their vendor namespace on a self-hosted OpenAI-compatible NIM endpoint.

    Pure pool projection: :func:`strong_vendor_model_ids` already returns the
    STRONG-tier vendor-namespaced ids in pool order (best-route-first), which
    leads with the high-stakes reasoning model. No literal preference seed is
    needed — the pool order is the smoke order. All strings are pool ids."""
    return strong_vendor_model_ids()


def _openrouter_frontier_models() -> tuple[str, ...]:
    """OpenRouter smoke catalog — STRONG-tier OpenRouter routes from the pool,
    pool order (which already leads with moonshotai/kimi-k2.5)."""
    return provider_model_ids(
        ProviderType.OPENROUTER,
        tiers=(ModelTier.STRONG,),
    )


_NIM_HOSTED_FRONTIER_MODELS = _nim_hosted_frontier_models()
_NIM_SELF_HOSTED_FRONTIER_MODELS = _nim_self_hosted_frontier_models()
_OPENROUTER_FRONTIER_MODELS = _openrouter_frontier_models()
_OLLAMA_NON_CHAT_MARKERS = (
    "embed",
    "embedding",
    "nomic-embed",
    "bge-",
    "e5-",
    "all-minilm",
    "snowflake-arctic-embed",
)
_OLLAMA_CHAT_FAMILY_WEIGHTS = (
    ("deepseek-v3.2", 940.0),
    ("deepseek-v3.1", 930.0),
    ("deepseek", 890.0),
    ("gpt-oss", 850.0),
    ("qwen3", 830.0),
    ("qwen2.5", 790.0),
    ("llama4", 760.0),
    ("llama3.3", 750.0),
    ("llama3.2", 730.0),
    ("mistral", 690.0),
    ("gemma", 650.0),
    ("phi", 620.0),
)
_PROVIDER_SMOKE_OUTCOME_KIND = "provider_smoke_probe"
_QWEN_DASHBOARD_SMOKE_PROVIDERS = {
    ProviderType.GROQ,
    ProviderType.SILICONFLOW,
    ProviderType.TOGETHER,
    ProviderType.FIREWORKS,
    ProviderType.OPENROUTER_FREE,
    ProviderType.OPENROUTER,
}
_DEFAULT_QWEN_DASHBOARD_TASK = (
    "Use tools only. Do a read-only inspection of the Qwen surgical lane in this repo. "
    "Read dharma_swarm/runtime_provider.py and api/routers/chat.py, grep for "
    "ProviderType and DASHBOARD_QWEN settings, then report: "
    "1) which provider/model you are actually running on right now, "
    "2) which files own provider resolution versus dashboard routing, and "
    "3) one concrete mismatch or risk you see. "
    "Use at least two tools. Do not edit files."
)


async def _iter_qwen_dashboard_stream(
    chat_router: Any,
    api_messages: list[dict[str, Any]],
    settings: Any,
    *,
    profile_id: str,
):
    async for chunk in chat_router._agentic_stream(
        api_messages,
        settings,
        profile_id=profile_id,
    ):
        yield chunk


def _classify_error(exc: Exception | str) -> str:
    text = str(exc).strip().lower()
    if "operation not permitted" in text or "permission denied" in text:
        return "blocked"
    if "unauthorized" in text or "http error 401" in text:
        return "auth_failed"
    if (
        "http error 402" in text
        or "error code: 402" in text
        or "payment required" in text
        or "insufficient credits" in text
    ):
        return "insufficient_credits"
    if "not set" in text:
        return "missing_config"
    if "http error 429" in text or "too many requests" in text or "rate limit" in text:
        return "rate_limited"
    if "credit balance" in text or "billing hard limit" in text:
        return "billing_exhausted"
    if "insufficient_quota" in text or "exceeded your current quota" in text:
        return "quota_exhausted"
    if any(marker in text for marker in _OLLAMA_ROOT_ERROR_MARKERS):
        return "misconfigured"
    if "http error 404" in text or "no endpoints found" in text:
        return "unknown_model"
    if "http error 410" in text:
        return "deprecated"
    if "all connection attempts failed" in text or "connection refused" in text:
        return "unreachable"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    return "error"


def _response_status(content: str | None) -> str:
    return "ok" if str(content or "").strip() else "empty_response"


def _strength_score(model_name: str) -> tuple[float, int]:
    text = model_name.lower()
    matches = list(_SIZE_RE.finditer(text))
    if not matches:
        return (0.0, len(text))
    scored: list[float] = []
    for match in matches:
        number = float(match.group("size"))
        unit = match.group("unit").lower()
        scale = {"": 0.0, "b": 1.0, "m": 0.001, "k": 0.000001, "g": 1000.0}.get(unit, 0.0)
        scored.append(number * scale)
    best = max(scored) if scored else 0.0
    return (best, len(text))


def _is_ollama_chat_model_candidate(model_name: str) -> bool:
    text = str(model_name or "").strip().lower()
    if not text:
        return False
    return not any(marker in text for marker in _OLLAMA_NON_CHAT_MARKERS)


def _ollama_chat_score(model_name: str) -> tuple[float, float, int]:
    text = model_name.lower()
    size_score, name_length = _strength_score(text)
    family_score = 0.0
    for marker, score in _OLLAMA_CHAT_FAMILY_WEIGHTS:
        if marker in text:
            family_score = score
            break
    return (family_score + size_score, size_score, name_length)


def _configured_ollama_root(base_dir: str | Path | None = None) -> Path:
    if base_dir is not None:
        return Path(base_dir).expanduser()
    root = os.environ.get("OLLAMA_HOME") or os.environ.get("OLLAMA_ROOT")
    if root:
        return Path(root).expanduser()
    return Path.home() / ".ollama"


def _nim_deployment_mode(base_url: str | None = None) -> str:
    resolved = (
        base_url
        or os.environ.get("NVIDIA_NIM_BASE_URL")
        or NVIDIA_NIM_BASE_URL
    ).rstrip("/")
    return "self_hosted" if resolved != NVIDIA_NIM_BASE_URL else "hosted_api"


def inspect_ollama_root(base_dir: str | Path | None = None) -> dict[str, str]:
    root = _configured_ollama_root(base_dir)
    try:
        resolved = root.resolve(strict=False)
    except OSError:
        resolved = root

    issue = ""
    symlink_target = ""
    try:
        if root.is_symlink():
            symlink_target = str(root.readlink())
            if not root.exists():
                issue = "broken_symlink"
        elif not root.exists():
            issue = "missing"
    except OSError:
        issue = "unreadable"

    return {
        "configured_root": str(root),
        "resolved_root": str(resolved),
        "root_issue": issue,
        "symlink_target": symlink_target,
    }


def list_ollama_manifest_models(base_dir: str | Path | None = None) -> list[str]:
    """Best-effort discovery of locally installed Ollama models from manifests."""
    root = _configured_ollama_root(base_dir)
    try:
        resolved = root.resolve(strict=False)
    except OSError:
        resolved = root
    manifests_root = resolved / "models" / "manifests"
    if not manifests_root.exists():
        return []

    found: set[str] = set()
    for path in manifests_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(manifests_root)
        parts = rel.parts
        if len(parts) < 3:
            continue
        if parts[0] == "registry.ollama.ai" and parts[1] == "library":
            model = parts[2]
            tag = parts[3] if len(parts) >= 4 else ""
            found.add(f"{model}:{tag}" if tag else model)
            continue
        if len(parts) >= 2:
            found.add(f"{parts[-2]}:{parts[-1]}")
            continue
        found.add(parts[-1])
    return sorted(found)


def list_ollama_runtime_models(base_url: str | None = None) -> list[str]:
    """Return models reported by the running Ollama daemon, if reachable."""
    base = str(base_url or "http://localhost:11434").strip().rstrip("/")
    if not base or not base.startswith(("http://", "https://")):
        return []  # scheme allowlist — no file:// / ftp:// via configured base
    try:
        with urlopen(f"{base}/api/tags", timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError):
        return []

    models = payload.get("models", [])
    if not isinstance(models, list):
        return []
    found: set[str] = set()
    for item in models:
        if not isinstance(item, dict):
            continue
        name = str(item.get("model") or item.get("name") or "").strip()
        if name:
            found.add(name)
    return sorted(found)


def strongest_ollama_model(installed_models: list[str]) -> str | None:
    chat_models = [
        model
        for model in installed_models
        if _is_ollama_chat_model_candidate(model)
    ]
    if not chat_models:
        return None
    ranked = sorted(chat_models, key=_ollama_chat_score, reverse=True)
    return ranked[0]


def _resolve_ollama_smoke_models(
    *,
    requested_model: str | None,
    configured_model: str | None,
    transport_mode: str,
    installed_models: list[str],
    strongest_local_model: str | None,
) -> list[str]:
    requested = str(requested_model or "").strip()
    configured = str(configured_model or "").strip()
    if transport_mode == "cloud_api":
        return _dedupe_models(
            [
                requested,
                configured,
                *OLLAMA_CLOUD_FRONTIER_MODELS,
            ]
        )

    if requested:
        return _dedupe_models(
            [
                requested,
                strongest_local_model or "",
                configured,
            ]
        )

    configured_is_installed_chat = (
        bool(configured)
        and configured in installed_models
        and _is_ollama_chat_model_candidate(configured)
    )
    return _dedupe_models(
        [
            strongest_local_model or "",
            configured if configured_is_installed_chat else "",
            configured,
        ]
    )


async def _probe_ollama(model: str) -> dict[str, Any]:
    config = resolve_runtime_provider_config(
        ProviderType.OLLAMA,
        model=model,
    )
    provider = create_runtime_provider(config)
    try:
        response = await provider.complete(
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "Reply with exactly OK."}],
                max_tokens=16,
                temperature=0.0,
            )
        )
        content = str(response.content or "")
        return {
            "status": _response_status(content),
            "model": response.model or model,
            "response_preview": content[:120],
            "usage": response.usage,
            "base_url": config.base_url,
            "transport_mode": config.transport_mode,
        }
    except Exception as exc:
        return {
            "status": _classify_error(exc),
            "model": model,
            "base_url": config.base_url,
            "transport_mode": config.transport_mode,
            "error": str(exc),
        }
    finally:
        await provider.close()


async def _probe_nim(model: str) -> dict[str, Any]:
    config = resolve_runtime_provider_config(
        ProviderType.NVIDIA_NIM,
        model=model,
    )
    provider = create_runtime_provider(config)
    try:
        response = await provider.complete(
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "Reply with exactly OK."}],
                max_tokens=16,
                temperature=0.0,
            )
        )
        content = str(response.content or "")
        return {
            "status": _response_status(content),
            "model": response.model or model,
            "response_preview": content[:120],
            "usage": response.usage,
            "base_url": config.base_url,
        }
    except Exception as exc:
        return {
            "status": _classify_error(exc),
            "model": model,
            "base_url": config.base_url or "",
            "error": str(exc),
        }
    finally:
        await provider.close()


async def _probe_openrouter(model: str) -> dict[str, Any]:
    config = resolve_runtime_provider_config(
        ProviderType.OPENROUTER,
        model=model,
    )
    provider = create_runtime_provider(config)
    try:
        response = await provider.complete(
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "Reply with exactly OK."}],
                max_tokens=16,
                temperature=0.0,
            )
        )
        content = str(response.content or "")
        return {
            "status": _response_status(content),
            "model": response.model or model,
            "response_preview": content[:120],
            "usage": response.usage,
            "base_url": config.base_url,
        }
    except Exception as exc:
        return {
            "status": _classify_error(exc),
            "model": model,
            "base_url": config.base_url,
            "error": str(exc),
        }
    finally:
        client = getattr(provider, "_client", None)
        if client is not None:
            await client.close()


def _dedupe_models(models: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for model in models:
        name = str(model).strip()
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _resolve_provider_smoke_telemetry_db(
    telemetry_db_path: str | Path | None,
) -> Path | None:
    if telemetry_db_path not in (None, ""):
        return Path(telemetry_db_path).expanduser()
    for env_name in ("DGC_ROUTER_TELEMETRY_DB", "DHARMA_RUNTIME_DB"):
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return Path(raw).expanduser()
    return None


def _provider_smoke_subject_id(label: str, block: dict[str, Any]) -> str:
    if label == "qwen_dashboard":
        return str(
            block.get("resolved_provider")
            or block.get("requested_provider")
            or label
        )
    return label


def _provider_smoke_value(status: str) -> float:
    return 1.0 if status == "ok" else 0.0


async def _persist_provider_smoke_telemetry(
    payload: dict[str, Any],
    *,
    telemetry_db_path: str | Path,
) -> dict[str, Any]:
    store = TelemetryPlaneStore(Path(telemetry_db_path).expanduser())
    session_id = f"provider-smoke-{uuid4().hex[:12]}"
    run_id = f"provider-smoke-{uuid4().hex[:12]}"
    errors: list[str] = []
    outcome_count = 0

    await store.init_db()
    for label, block in payload.items():
        if not isinstance(block, dict):
            continue
        status = str(block.get("status") or "").strip()
        if not status:
            continue

        subject_id = _provider_smoke_subject_id(label, block)
        model = str(block.get("model") or block.get("configured_model") or "").strip()
        summary = f"{label} {status}"
        if model:
            summary += f" ({model})"
        record = ExternalOutcomeRecord(
            outcome_id=f"outcome_{uuid4().hex[:16]}",
            outcome_kind=_PROVIDER_SMOKE_OUTCOME_KIND,
            subject_id=subject_id,
            value=_provider_smoke_value(status),
            unit="success_ratio",
            confidence=1.0 if status == "ok" else 0.0,
            status=status,
            summary=summary,
            session_id=session_id,
            task_id="provider_smoke",
            run_id=run_id,
            metadata={
                "probe_name": label,
                "provider": subject_id,
                "status": status,
                **dict(block),
            },
        )
        try:
            await store.record_external_outcome(record)
            outcome_count += 1
        except Exception as exc:
            errors.append(f"{label}: {exc}")

    if errors and outcome_count:
        status = "partial"
    elif errors:
        status = "error"
    else:
        status = "persisted"

    result = {
        "status": status,
        "db_path": str(store.db_path),
        "session_id": session_id,
        "run_id": run_id,
        "outcome_kind": _PROVIDER_SMOKE_OUTCOME_KIND,
        "outcome_count": outcome_count,
    }
    if errors:
        result["errors"] = errors
    return result


@contextmanager
def _temporary_env(overrides: dict[str, str | None]):
    sentinel = object()
    previous: dict[str, object] = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key, sentinel)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is sentinel:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)


async def _probe_qwen_dashboard(provider_name: str, task: str) -> dict[str, Any]:
    from api.routers import chat as chat_router

    requested = str(provider_name or "").strip().lower()
    if not requested:
        return {
            "status": "missing_config",
            "requested_provider": "",
            "error": "No Qwen provider requested.",
            "task": task,
        }
    try:
        provider = ProviderType(requested)
    except ValueError:
        return {
            "status": "unsupported_provider",
            "requested_provider": requested,
            "error": f"Unknown provider: {requested}",
            "task": task,
        }
    if provider not in _QWEN_DASHBOARD_SMOKE_PROVIDERS:
        return {
            "status": "unsupported_provider",
            "requested_provider": provider.value,
            "error": f"{provider.value} is not enabled for the Qwen dashboard smoke lane.",
            "task": task,
        }

    profile = chat_router._get_profile_spec("qwen35_surgeon")
    env_key = chat_router.PROVIDER_ENV_KEYS.get(provider, "")
    with _temporary_env({profile.provider_order_env: provider.value}):
        settings = chat_router._get_chat_settings(profile.profile_id)

    if settings.provider != provider:
        return {
            "status": "provider_mismatch",
            "requested_provider": provider.value,
            "resolved_provider": settings.provider.value,
            "model": settings.model,
            "required_env_key": env_key,
            "task": task,
            "error": (
                f"Requested {provider.value} but dashboard resolved "
                f"{settings.provider.value}."
            ),
        }

    if not settings.available:
        return {
            "status": "missing_config",
            "requested_provider": provider.value,
            "resolved_provider": settings.provider.value,
            "model": settings.model,
            "required_env_key": env_key,
            "task": task,
            "error": f"{env_key or 'provider credentials'} not set",
        }

    api_messages = [
        {
            "role": "system",
            "content": (
                profile.system_prompt
                + "\n\n[Live smoke task. Read-only verification. Use tools.]"
            ),
        },
        {"role": "user", "content": task},
    ]

    tool_calls: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    content_parts: list[str] = []
    errors: list[str] = []
    raw_events: list[dict[str, Any]] = []
    try:
        async for chunk in _iter_qwen_dashboard_stream(
            chat_router,
            api_messages,
            settings,
            profile_id=profile.profile_id,
        ):
            if not chunk.startswith("data: "):
                continue
            payload_raw = chunk[6:].strip()
            if payload_raw == "[DONE]":
                continue
            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                continue
            raw_events.append(payload)
            if "tool_call" in payload:
                tool_calls.append(payload["tool_call"])
            if "tool_result" in payload:
                tool_results.append(payload["tool_result"])
            if "content" in payload:
                content_parts.append(str(payload["content"]))
            if "error" in payload:
                errors.append(str(payload["error"]))
    except Exception as exc:
        return {
            "status": _classify_error(exc),
            "requested_provider": provider.value,
            "resolved_provider": settings.provider.value,
            "model": settings.model,
            "required_env_key": env_key,
            "task": task,
            "error": str(exc),
        }

    status = "ok"
    if errors:
        status = "error"
    elif not content_parts and not tool_calls:
        status = "empty"
    elif tool_calls and not content_parts:
        status = "tool_only"

    return {
        "status": status,
        "requested_provider": provider.value,
        "resolved_provider": settings.provider.value,
        "model": settings.model,
        "required_env_key": env_key,
        "task": task,
        "tool_call_count": len(tool_calls),
        "tool_result_count": len(tool_results),
        "tool_names": [str(item.get("name", "")) for item in tool_calls if item.get("name")],
        "response_preview": "".join(content_parts)[:600],
        "events_seen": len(raw_events),
        "errors": errors,
    }


async def _probe_model_pack(
    probe_fn,
    models: list[str],
    *,
    stop_on_success: bool = True,
    stop_on_provider_terminal_status: bool = True,
) -> dict[str, Any]:
    verified: list[dict[str, Any]] = []
    first_success: dict[str, Any] | None = None

    for model in _dedupe_models(models):
        result = await probe_fn(model)
        verified.append(result)
        status = str(result.get("status") or "").strip()
        if first_success is None and status == "ok":
            first_success = result
            if stop_on_success:
                break
        if (
            stop_on_provider_terminal_status
            and status in _PROVIDER_WIDE_TERMINAL_STATUSES
        ):
            break

    if first_success is not None:
        return {
            **first_success,
            "verified_models": verified,
            "strongest_verified": first_success.get("model"),
        }

    if verified:
        return {
            **verified[0],
            "verified_models": verified,
            "strongest_verified": None,
        }

    return {
        "status": "missing_config",
        "model": "",
        "verified_models": [],
        "strongest_verified": None,
        "error": "No models configured for probe pack.",
    }


def run_provider_smoke(
    *,
    ollama_model: str | None = None,
    nim_model: str | None = None,
    qwen_provider: str | None = None,
    qwen_task: str | None = None,
    telemetry_db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run best-effort smoke tests for cloud and external provider lanes."""
    ollama_config = resolve_runtime_provider_config(ProviderType.OLLAMA)
    nim_config = resolve_runtime_provider_config(ProviderType.NVIDIA_NIM)
    openrouter_config = resolve_runtime_provider_config(ProviderType.OPENROUTER)

    nim_base_url = nim_config.base_url or NVIDIA_NIM_BASE_URL
    nim_mode = _nim_deployment_mode(nim_base_url)
    ollama_base_url = ollama_config.base_url or ""
    ollama_mode = ollama_config.transport_mode or "local_api"
    ollama_root = (
        inspect_ollama_root()
        if ollama_mode == "local_api"
        else {
            "configured_root": "",
            "resolved_root": "",
            "root_issue": "",
            "symlink_target": "",
        }
    )
    runtime_installed = (
        list_ollama_runtime_models(ollama_base_url)
        if ollama_mode == "local_api"
        else []
    )
    manifest_installed = (
        list_ollama_manifest_models()
        if ollama_mode == "local_api" and not runtime_installed
        else []
    )
    installed = runtime_installed or manifest_installed
    installed_source = (
        "runtime_api"
        if runtime_installed
        else "manifest"
        if manifest_installed
        else ""
    )
    strongest_local = strongest_ollama_model(installed)
    resolved_ollama = _resolve_ollama_smoke_models(
        requested_model=ollama_model,
        configured_model=ollama_config.default_model,
        transport_mode=ollama_mode,
        installed_models=installed,
        strongest_local_model=strongest_local,
    )
    resolved_nim = _dedupe_models(
        [
            nim_model or "",
            os.environ.get("NVIDIA_NIM_MODEL", ""),
            *(
                _NIM_SELF_HOSTED_FRONTIER_MODELS
                if nim_mode == "self_hosted"
                else _NIM_HOSTED_FRONTIER_MODELS
            ),
        ]
    )
    resolved_openrouter = _dedupe_models(
        [
            os.environ.get("OPENROUTER_MODEL", ""),
            *_OPENROUTER_FRONTIER_MODELS,
        ]
    )

    ollama = asyncio.run(_probe_model_pack(_probe_ollama, resolved_ollama))
    nim = asyncio.run(_probe_model_pack(_probe_nim, resolved_nim))
    openrouter = asyncio.run(_probe_model_pack(_probe_openrouter, resolved_openrouter))

    payload = {
        "ollama": {
            "configured_base_url": ollama_base_url,
            "transport_mode": ollama_mode,
            "api_key_configured": env_has_value(OLLAMA_API_KEY_ENV),
            "installed_models": installed,
            "installed_model_source": installed_source,
            "strongest_installed": strongest_local,
            "catalog_models": list(OLLAMA_CLOUD_FRONTIER_MODELS),
            "configured_model": resolved_ollama[0] if resolved_ollama else "",
            **ollama_root,
            **ollama,
        },
        "nvidia_nim": {
            "configured_base_url": nim_base_url,
            "configured_model": resolved_nim[0] if resolved_nim else "",
            "deployment_mode": nim_mode,
            "catalog_models": {
                "hosted_api": list(_NIM_HOSTED_FRONTIER_MODELS),
                "self_hosted": list(_NIM_SELF_HOSTED_FRONTIER_MODELS),
            },
            **nim,
        },
        "openrouter": {
            "configured_base_url": openrouter_config.base_url or OPENROUTER_BASE_URL,
            "configured_model": resolved_openrouter[0] if resolved_openrouter else "",
            **openrouter,
        },
    }
    if qwen_provider:
        payload["qwen_dashboard"] = asyncio.run(
            _probe_qwen_dashboard(
                qwen_provider,
                qwen_task or _DEFAULT_QWEN_DASHBOARD_TASK,
            )
        )
    resolved_telemetry_db = _resolve_provider_smoke_telemetry_db(telemetry_db_path)
    if resolved_telemetry_db is not None:
        payload["_telemetry"] = asyncio.run(
            _persist_provider_smoke_telemetry(
                payload,
                telemetry_db_path=resolved_telemetry_db,
            )
        )
    return payload


__all__ = [
    "inspect_ollama_root",
    "list_ollama_manifest_models",
    "list_ollama_runtime_models",
    "run_provider_smoke",
    "strongest_ollama_model",
]
