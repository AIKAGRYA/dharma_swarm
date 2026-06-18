"""Direct model-routing live probe receipts.

This module is the primary live-call proof harness for the model-routing
hardening track. It reads the canonical model-status projection, resolves each
live floor route through ``runtime_provider``, constructs the provider through
the factory, and records bounded probe receipts. It never reads key values.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import re
import time
from typing import Any, Callable, Iterable, Sequence

from dharma_swarm.model_status import (
    LIVE_MODEL_E2E_ENV,
    ModelStatusProjection,
    floor_model_status,
    projection_to_dict,
)
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.runtime_provider import (
    RuntimeProviderConfig,
    create_runtime_provider,
    resolve_runtime_provider_config,
)

LIVE_PROBE_SCHEMA_VERSION = "dharma.model_routing_live_probe.v1"

FAILURE_CLASSES = (
    "key_missing",
    "provider_dead",
    "model_missing",
    "rate_limited",
    "quota",
    "unsupported_route",
    "timeout",
    "schema_failure",
    "routing_bug",
)

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*[=:]\s*)[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class LiveProbeSpec:
    logical_model_id: str
    display_name: str
    provider: ProviderType
    model_id: str
    route: str
    rank: int
    max_context: int
    strengths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProbeCase:
    name: str
    prompt: str
    validator: str
    expected: str | None = None
    max_tokens: int = 64


Resolver = Callable[..., RuntimeProviderConfig]
ProviderFactory = Callable[[RuntimeProviderConfig], Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redact(value: Any, *, limit: int = 500) -> str:
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}<redacted>" if match.groups() else "<redacted>", text)
    text = " ".join(text.split())
    return text[:limit]


def _response_preview(content: str, *, limit: int = 180) -> str:
    return _redact(content, limit=limit)


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def classify_live_failure(error: Exception | str) -> str:
    """Map provider/runtime failures to the hardening contract's classes."""

    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return "timeout"
    text = str(error).strip().lower()
    if not text:
        return "schema_failure"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if (
        "not set" in text
        or "missing_config" in text
        or "no api key" in text
        or "api key missing" in text
    ):
        return "key_missing"
    if "http error 429" in text or "too many requests" in text or "rate limit" in text:
        return "rate_limited"
    if (
        "insufficient_quota" in text
        or "exceeded your current quota" in text
        or "credit balance" in text
        or "billing hard limit" in text
        or "payment required" in text
        or "insufficient credits" in text
        or "error code: 402" in text
        or "http error 402" in text
    ):
        return "quota"
    if (
        "http error 404" in text
        or "unknown_model" in text
        or "model_not_found" in text
        or "model not found" in text
        or "no endpoints found" in text
    ):
        return "model_missing"
    if (
        "unsupported runtime provider" in text
        or "unsupported route" in text
        or "unsupported model" in text
        or "does not support" in text
        or "invalid_request" in text
        or "bad request" in text
        or "http error 400" in text
    ):
        return "unsupported_route"
    if (
        "unauthorized" in text
        or "forbidden" in text
        or "http error 401" in text
        or "http error 403" in text
        or "connection refused" in text
        or "all connection attempts failed" in text
        or "name resolution" in text
        or "temporary failure" in text
        or "http error 5" in text
        or "service unavailable" in text
        or "overloaded" in text
        or "pip install" in text
        or "no module named" in text
    ):
        return "provider_dead"
    if "schema" in text or "json" in text:
        return "schema_failure"
    return "routing_bug"


def normalize_failure_class(reason: str | None) -> str:
    """Normalize existing status/probe reasons into the live failure taxonomy."""

    if reason in FAILURE_CLASSES:
        return reason
    if reason in {None, "", "key_status_unknown", "missing_config", "unverified"}:
        return "key_missing"
    if reason in {"quota_exhausted", "billing_exhausted", "insufficient_credits"}:
        return "quota"
    if reason in {"unknown_model", "deprecated"}:
        return "model_missing"
    if reason in {"unreachable", "auth_failed", "blocked", "misconfigured", "error"}:
        return "provider_dead"
    return classify_live_failure(reason)


def probe_cases_for_profile(profile: str) -> tuple[ProbeCase, ...]:
    pong = ProbeCase(
        name="pong_exact",
        prompt="Reply with exactly this token and no other text: PONG",
        validator="exact",
        expected="PONG",
        max_tokens=16,
    )
    json_case = ProbeCase(
        name="json_schema",
        prompt=(
            "Return only minified JSON with exactly these fields: "
            '{"ok":true,"token":"MODEL_PROBE"}'
        ),
        validator="json",
        expected="MODEL_PROBE",
        max_tokens=64,
    )
    arithmetic = ProbeCase(
        name="code_reasoning",
        prompt="Return only the integer result of 17 * 19.",
        validator="exact",
        expected="323",
        max_tokens=16,
    )
    long_context = ProbeCase(
        name="long_context",
        prompt=(
            "The sentinel number is 37. Ignore filler words. "
            + "filler " * 220
            + "Return only the sentinel number."
        ),
        validator="exact",
        expected="37",
        max_tokens=16,
    )
    multilingual = ProbeCase(
        name="multilingual",
        prompt="Translate 'routing healthy' to Japanese. Return only the translated phrase.",
        validator="nonempty",
        max_tokens=32,
    )
    if profile == "pong":
        return (pong,)
    if profile == "standard":
        return (pong, json_case)
    if profile == "full":
        return (pong, json_case, arithmetic, long_context, multilingual)
    raise ValueError(f"unknown live probe profile: {profile}")


def build_probe_plan(
    projection: ModelStatusProjection | None = None,
    *,
    model_ids: Iterable[str] | None = None,
    limit: int | None = None,
) -> tuple[list[LiveProbeSpec], list[dict[str, Any]], dict[str, Any]]:
    """Select live floor routes from the canonical model-status projection."""

    selected_ids = set(model_ids or ())
    projection = projection or floor_model_status()
    specs: list[LiveProbeSpec] = []
    skipped: list[dict[str, Any]] = []
    for model in projection.models:
        if selected_ids and model.id not in selected_ids:
            continue
        live_routes = [route for route in model.route_statuses if route.status == "live_routable"]
        if not live_routes:
            skipped.append(
                {
                    "logical_model_id": model.id,
                    "display_name": model.display_name,
                    "status": model.status,
                    "reason": model.unavailable_reason or "no_live_route",
                    "failure_class": normalize_failure_class(model.unavailable_reason),
                    "available_routes": list(model.available_routes),
                    "routes": list(model.routes),
                }
            )
            continue
        for live_route in live_routes:
            try:
                provider = ProviderType(live_route.provider)
            except ValueError:
                skipped.append(
                    {
                        "logical_model_id": model.id,
                        "display_name": model.display_name,
                        "status": "failed",
                        "reason": f"unknown provider in route: {live_route.provider}",
                        "failure_class": "routing_bug",
                        "available_routes": list(model.available_routes),
                        "routes": list(model.routes),
                    }
                )
                continue
            specs.append(
                LiveProbeSpec(
                    logical_model_id=model.id,
                    display_name=model.display_name,
                    provider=provider,
                    model_id=live_route.model_id,
                    route=live_route.route,
                    rank=model.rank,
                    max_context=model.max_context,
                    strengths=tuple(model.strengths),
                )
            )
            if limit is not None and len(specs) >= limit:
                break
        if limit is not None and len(specs) >= limit:
            break
    return specs, skipped, projection_to_dict(projection)


def _spec_to_dict(spec: LiveProbeSpec) -> dict[str, Any]:
    return {
        "logical_model_id": spec.logical_model_id,
        "display_name": spec.display_name,
        "provider": spec.provider.value,
        "model_id": spec.model_id,
        "route": spec.route,
        "rank": spec.rank,
        "max_context": spec.max_context,
        "strengths": list(spec.strengths),
    }


def _config_summary(config: RuntimeProviderConfig) -> dict[str, Any]:
    return {
        "provider": config.provider.value,
        "default_model": config.default_model,
        "base_url": config.base_url,
        "transport_mode": config.transport_mode,
        "working_dir": config.working_dir,
        "timeout_seconds": config.timeout_seconds,
        "binary_path": config.binary_path,
        "available": config.available,
        "source": config.source,
        "api_key_present": bool(config.api_key),
    }


def _looks_like_provider_error(content: str) -> bool:
    text = content.strip().lower()
    if not text:
        return False
    markers = (
        "error code:",
        "http error",
        "rate limit",
        "credit balance",
        "insufficient_quota",
        "payment required",
        "api key",
        "no endpoints found",
        "connection refused",
        "all connection attempts failed",
        "timeout",
        "error(rc=",
        "error (rc=",
    )
    return any(marker in text for marker in markers)


def _strip_code_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


def _validate_response(case: ProbeCase, response: LLMResponse) -> tuple[bool, str | None, str | None]:
    content = response.content or ""
    if _looks_like_provider_error(content):
        return False, classify_live_failure(content), _response_preview(content)
    stripped = _strip_code_fence(content).strip()
    if case.validator == "exact":
        if stripped == case.expected:
            return True, None, None
        return False, "schema_failure", f"expected {case.expected!r}, got {_response_preview(stripped)!r}"
    if case.validator == "json":
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return False, "schema_failure", f"invalid JSON: {_response_preview(stripped)!r}"
        if parsed == {"ok": True, "token": case.expected}:
            return True, None, None
        return False, "schema_failure", f"unexpected JSON payload: {_response_preview(stripped)!r}"
    if case.validator == "nonempty":
        if stripped:
            return True, None, None
        return False, "schema_failure", "empty response"
    return False, "routing_bug", f"unknown validator: {case.validator}"


async def _maybe_close_provider(provider: Any) -> None:
    close = getattr(provider, "close", None)
    if not callable(close):
        return
    result = close()
    if inspect.isawaitable(result):
        await result


async def run_probe_spec(
    spec: LiveProbeSpec,
    cases: Sequence[ProbeCase],
    *,
    resolver: Resolver = resolve_runtime_provider_config,
    provider_factory: ProviderFactory = create_runtime_provider,
    timeout_seconds: int = 90,
    working_dir: str | None = None,
) -> list[dict[str, Any]]:
    """Run all probe cases for one planned provider/model route."""

    started_at = _utc_now()
    try:
        config = resolver(
            spec.provider,
            model=spec.model_id,
            timeout_seconds=timeout_seconds,
            working_dir=working_dir,
        )
    except Exception as exc:
        return [
            {
                **_spec_to_dict(spec),
                "probe": "runtime_config",
                "status": "failed",
                "failure_class": classify_live_failure(exc),
                "started_at": started_at,
                "elapsed_ms": 0,
                "live_call_attempted": False,
                "error": _redact(exc),
            }
        ]

    config_data = _config_summary(config)
    if not config.available:
        return [
            {
                **_spec_to_dict(spec),
                "probe": "runtime_config",
                "status": "failed",
                "failure_class": "routing_bug",
                "started_at": started_at,
                "elapsed_ms": 0,
                "live_call_attempted": False,
                "runtime_config": config_data,
                "error": "model-status projection marked route live, but runtime config is unavailable",
            }
        ]

    try:
        provider = provider_factory(config)
    except Exception as exc:
        return [
            {
                **_spec_to_dict(spec),
                "probe": "provider_factory",
                "status": "failed",
                "failure_class": classify_live_failure(exc),
                "started_at": started_at,
                "elapsed_ms": 0,
                "live_call_attempted": False,
                "runtime_config": config_data,
                "error": _redact(exc),
            }
        ]

    results: list[dict[str, Any]] = []
    try:
        for case in cases:
            request = LLMRequest(
                model=spec.model_id,
                system="You are running a bounded live routing health probe. Do not use tools.",
                messages=[{"role": "user", "content": case.prompt}],
                max_tokens=case.max_tokens,
                temperature=0.0,
            )
            probe_started = _utc_now()
            monotonic_started = time.monotonic()
            try:
                response = await asyncio.wait_for(
                    provider.complete(request),
                    timeout=timeout_seconds,
                )
            except Exception as exc:
                elapsed_ms = int((time.monotonic() - monotonic_started) * 1000)
                results.append(
                    {
                        **_spec_to_dict(spec),
                        "probe": case.name,
                        "status": "failed",
                        "failure_class": classify_live_failure(exc),
                        "started_at": probe_started,
                        "elapsed_ms": elapsed_ms,
                        "live_call_attempted": True,
                        "runtime_config": config_data,
                        "error": _redact(exc),
                    }
                )
                continue
            elapsed_ms = int((time.monotonic() - monotonic_started) * 1000)
            ok, failure_class, error = _validate_response(case, response)
            content = response.content or ""
            results.append(
                {
                    **_spec_to_dict(spec),
                    "probe": case.name,
                    "status": "ok" if ok else "failed",
                    "failure_class": failure_class,
                    "started_at": probe_started,
                    "elapsed_ms": elapsed_ms,
                    "live_call_attempted": True,
                    "runtime_config": config_data,
                    "served_provider": response.provider or None,
                    "served_model": response.model,
                    "usage": dict(response.usage),
                    "stop_reason": response.stop_reason,
                    "response_sha256": _sha256(content),
                    "response_preview": _response_preview(content),
                    "error": error,
                }
            )
    finally:
        await _maybe_close_provider(provider)
    return results


async def build_live_probe_matrix(
    *,
    projection: ModelStatusProjection | None = None,
    live_calls_enabled: bool = False,
    profile: str = "standard",
    limit: int | None = None,
    model_ids: Iterable[str] | None = None,
    timeout_seconds: int = 90,
    working_dir: str | None = None,
    resolver: Resolver = resolve_runtime_provider_config,
    provider_factory: ProviderFactory = create_runtime_provider,
) -> dict[str, Any]:
    specs, skipped, projection_data = build_probe_plan(
        projection,
        model_ids=model_ids,
        limit=limit,
    )
    cases = probe_cases_for_profile(profile)
    results: list[dict[str, Any]] = []
    if live_calls_enabled:
        for spec in specs:
            results.extend(
                await run_probe_spec(
                    spec,
                    cases,
                    resolver=resolver,
                    provider_factory=provider_factory,
                    timeout_seconds=timeout_seconds,
                    working_dir=working_dir,
                )
            )

    attempted = sum(1 for result in results if result.get("live_call_attempted"))
    failed = [result for result in results if result.get("status") != "ok"]
    ok = [result for result in results if result.get("status") == "ok"]
    if not live_calls_enabled:
        status = "planned"
    elif failed:
        status = "failed"
    elif not specs:
        status = "blocked"
    else:
        status = "passed"
    return {
        "schema_version": LIVE_PROBE_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "mode": "live" if live_calls_enabled else "dry-run",
        "profile": profile,
        "live_env": LIVE_MODEL_E2E_ENV,
        "live_calls_enabled": live_calls_enabled,
        "status": status,
        "failure_classes": list(FAILURE_CLASSES),
        "counts": {
            "planned_models": len(specs),
            "skipped_models": len(skipped),
            "probe_cases_per_model": len(cases),
            "live_calls_attempted": attempted,
            "ok": len(ok),
            "failed": len(failed),
        },
        "projection": {
            "schema_version": projection_data["schema_version"],
            "generated_at": projection_data["generated_at"],
            "oracle_state": projection_data["oracle_state"],
            "live_providers": projection_data["live_providers"],
        },
        "planned": [_spec_to_dict(spec) for spec in specs],
        "skipped": skipped,
        "results": results,
    }


def write_live_probe_matrix(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


__all__ = [
    "FAILURE_CLASSES",
    "LIVE_PROBE_SCHEMA_VERSION",
    "LiveProbeSpec",
    "ProbeCase",
    "build_live_probe_matrix",
    "build_probe_plan",
    "classify_live_failure",
    "normalize_failure_class",
    "probe_cases_for_profile",
    "run_probe_spec",
    "write_live_probe_matrix",
]
