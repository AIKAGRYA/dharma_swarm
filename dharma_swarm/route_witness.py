"""Canonical route witness emitter (Phase 1, 2026-05-10).

Single responsibility: build, redact, classify, and emit routing decision
records to the existing TelemetryPlaneStore + audit JSONL. **NEVER routes,
gates, ranks, or chooses providers.** Decision authority remains with
``ProviderPolicyRouter``; execution remains with ``ModelRouter``;
persistence remains with ``TelemetryPlaneStore``. This module is the
emission/normalization layer that makes Phase 1 dashboard-ready without
inventing a second routing reality.

See docs/plans/2026-05-10-phase1-routing-witness.md for the full spec.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

from dharma_swarm.models import ProviderType
from dharma_swarm.telemetry_plane import (
    DEFAULT_TELEMETRY_DB,
    ProviderAttemptRecord,
    RoutingDecisionRecord,
    TelemetryPlaneStore,
)

logger = logging.getLogger(__name__)

# --- Public constants ----------------------------------------------------

# Single source of truth for the Phase 1 error class enumeration. Each
# string is what gets stored in ProviderAttemptRecord.error_class so
# Grafana/SQL queries can filter by error class without parsing prose.
ERROR_CLASS_CREDIT_EXHAUSTED = "credit_exhausted"
ERROR_CLASS_RATE_LIMIT = "rate_limit"
ERROR_CLASS_TIMEOUT = "timeout"
ERROR_CLASS_NETWORK = "network"
ERROR_CLASS_MODEL_UNAVAILABLE = "model_unavailable"
ERROR_CLASS_EMPTY_CONTENT = "empty_content"
ERROR_CLASS_API_ERROR = "api_error"
ERROR_CLASS_AUTH_ERROR = "auth_error"
ERROR_CLASS_UNKNOWN = "unknown"

ERROR_CLASSES: tuple[str, ...] = (
    ERROR_CLASS_CREDIT_EXHAUSTED,
    ERROR_CLASS_RATE_LIMIT,
    ERROR_CLASS_TIMEOUT,
    ERROR_CLASS_NETWORK,
    ERROR_CLASS_MODEL_UNAVAILABLE,
    ERROR_CLASS_EMPTY_CONTENT,
    ERROR_CLASS_API_ERROR,
    ERROR_CLASS_AUTH_ERROR,
    ERROR_CLASS_UNKNOWN,
)

DECISION_CLASSES: tuple[str, ...] = (
    "pinned", "widened", "fallback", "no_route", "canary",
)

OUTCOMES: tuple[str, ...] = (
    "success", "empty_content", "all_failed", "timeout", "gate_block", "no_route",
)

MAX_ERROR_DETAIL_CHARS = 200

# --- Tier and cost lookup ------------------------------------------------

# Free providers (zero marginal cost). All others are 'paid' or 'cheap'
# depending on the canonical seed order tier in model_hierarchy.
_FREE_PROVIDERS: frozenset[str] = frozenset({
    ProviderType.OLLAMA.value,
    ProviderType.NVIDIA_NIM.value,
    ProviderType.GROQ.value,
    ProviderType.CEREBRAS.value,
    ProviderType.SILICONFLOW.value,
    ProviderType.SAMBANOVA.value,
    ProviderType.TOGETHER.value,
    ProviderType.FIREWORKS.value,
    ProviderType.OPENROUTER_FREE.value,
})

_CHEAP_PROVIDERS: frozenset[str] = frozenset({
    ProviderType.MISTRAL.value,
    ProviderType.GOOGLE_AI.value,
    ProviderType.CHUTES.value,
})

# Per-1K-token rough estimates (USD). Used only when a caller doesn't
# supply cost_estimate_usd. Conservative; updated via Phase 2 once we
# have empirical cost data from the witness.
_PROVIDER_COST_PER_1K_INPUT_USD: dict[str, float] = {
    ProviderType.ANTHROPIC.value: 0.015,    # claude-opus-4 ~ $15/1M input
    ProviderType.OPENAI.value: 0.0125,      # gpt-5 ~ $12.5/1M input
    ProviderType.OPENROUTER.value: 0.005,   # mid-range default
    ProviderType.CLAUDE_CODE.value: 0.015,  # mirrors anthropic
    ProviderType.CODEX.value: 0.0125,       # mirrors openai
}

_PROVIDER_COST_PER_1K_OUTPUT_USD: dict[str, float] = {
    ProviderType.ANTHROPIC.value: 0.075,    # claude-opus-4 ~ $75/1M output
    ProviderType.OPENAI.value: 0.10,        # gpt-5 ~ $100/1M output
    ProviderType.OPENROUTER.value: 0.015,
    ProviderType.CLAUDE_CODE.value: 0.075,
    ProviderType.CODEX.value: 0.10,
}


def _provider_value(provider: ProviderType | str) -> str:
    if isinstance(provider, ProviderType):
        return provider.value
    return str(provider)


def tier_for_provider(provider: ProviderType | str) -> Literal["free", "cheap", "paid", "unknown"]:
    """Classify a provider lane into free / cheap / paid for slicing."""
    name = _provider_value(provider)
    if not name:
        return "unknown"
    if name in _FREE_PROVIDERS:
        return "free"
    if name in _CHEAP_PROVIDERS:
        return "cheap"
    return "paid"


def estimate_cost_usd(
    provider: ProviderType | str,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> float:
    """Conservative cost estimate from token usage. 0.0 for free lanes.

    Phase 2 will replace this with model-specific pricing pulled from
    model_hierarchy.py. For Phase 1 we use a single per-provider rate so
    the witness has a non-zero baseline cost dimension.
    """
    name = _provider_value(provider)
    if name in _FREE_PROVIDERS:
        return 0.0
    in_rate = _PROVIDER_COST_PER_1K_INPUT_USD.get(name, 0.001)
    out_rate = _PROVIDER_COST_PER_1K_OUTPUT_USD.get(name, 0.003)
    cost = (prompt_tokens / 1000.0) * in_rate + (completion_tokens / 1000.0) * out_rate
    return round(cost, 6)


# --- Redaction -----------------------------------------------------------

# Patterns that must NEVER reach the witness file.
_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "[redacted-key]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_.-]{16,}", re.IGNORECASE), "Bearer [redacted]"),
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b"), "[redacted-hex]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[redacted-email]"),
    (
        re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[=:]\s*\S+"),
        r"\1=[redacted]",
    ),
    (re.compile(r"/Users/[^/\s]+/\.dharma/[^\s]*"), "<witness_path>"),
    (re.compile(r"/Users/[^/\s]+/\.claude/[^\s]*"), "<claude_config_path>"),
)


def _scrub_secret_patterns(text: str) -> str:
    redacted = text
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_error_detail(detail: str) -> str:
    """Scrub secret patterns, then truncate to MAX_ERROR_DETAIL_CHARS.

    If after redaction the string is empty or only whitespace, returns
    '[redacted]' so the column is never empty for an attempt that
    actually had an error.
    """
    if not detail:
        return ""
    # Scrub before truncation so a secret that crosses the truncation boundary
    # cannot leave a prefix behind. Scrub again after truncation in case the
    # replacement exposed a secondary pattern.
    original = detail.strip()
    scrubbed = _scrub_secret_patterns(original)
    if len(scrubbed) > MAX_ERROR_DETAIL_CHARS and scrubbed != original:
        suffix = " [redacted]"
        redacted = scrubbed[: MAX_ERROR_DETAIL_CHARS - len(suffix)].rstrip() + suffix
    else:
        redacted = scrubbed[:MAX_ERROR_DETAIL_CHARS]
    redacted = _scrub_secret_patterns(redacted)
    redacted = redacted.strip()
    if not redacted:
        return "[redacted]"
    return redacted


def _redact_json_value(value: Any) -> Any:
    """Return a JSON-safe value with secret-bearing strings scrubbed.

    route_witness owns all witness serialization, so this defensive pass also
    covers metadata/reasons/caller fields, not just ProviderAttempt.error_detail.
    """
    if isinstance(value, str):
        return _scrub_secret_patterns(value)
    if isinstance(value, dict):
        return {
            _scrub_secret_patterns(str(key)): _redact_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_redact_json_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _scrub_secret_patterns(str(value))


# --- Error classification ------------------------------------------------

_CREDIT_PATTERNS = (
    "credit balance is too low", "out of credits", "insufficient credit",
    "billing", "payment required", "credits exhausted",
)
_RATE_LIMIT_PATTERNS = (
    "rate limit", "rate-limited", "too many requests", "quota exceeded", "429",
)
_AUTH_PATTERNS = ("401", "unauthorized", "invalid api key", "authentication failed")
_FORBIDDEN_PATTERNS = ("403", "forbidden", "access denied", "permission denied")
_NETWORK_PATTERNS = (
    "connection refused", "connection reset", "name resolution", "dns",
    "network is unreachable", "no route to host",
)
_MODEL_UNAVAIL_PATTERNS = (
    "model not found", "model_not_found", "no such model", "deprecated",
    "404", "not_found", "model unavailable",
)


def classify_error(error: BaseException | str | None) -> str:
    """Map an exception or error string to a Phase 1 error_class."""
    if error is None:
        return ""
    if isinstance(error, asyncio.TimeoutError):
        return ERROR_CLASS_TIMEOUT
    msg = (str(error) or "").lower()
    if not msg:
        return ERROR_CLASS_UNKNOWN
    if any(p in msg for p in _CREDIT_PATTERNS):
        return ERROR_CLASS_CREDIT_EXHAUSTED
    if any(p in msg for p in _RATE_LIMIT_PATTERNS):
        return ERROR_CLASS_RATE_LIMIT
    if any(p in msg for p in _AUTH_PATTERNS):
        return ERROR_CLASS_AUTH_ERROR
    if any(p in msg for p in _FORBIDDEN_PATTERNS):
        # Forbidden is closer to auth than network; many providers return
        # 403 for region/account blocks (e.g. Groq from APAC).
        return ERROR_CLASS_AUTH_ERROR
    if any(p in msg for p in _MODEL_UNAVAIL_PATTERNS):
        return ERROR_CLASS_MODEL_UNAVAILABLE
    if any(p in msg for p in _NETWORK_PATTERNS):
        return ERROR_CLASS_NETWORK
    if "timeout" in msg or "timed out" in msg:
        return ERROR_CLASS_TIMEOUT
    if "empty" in msg and "content" in msg:
        return ERROR_CLASS_EMPTY_CONTENT
    if "500" in msg or "503" in msg or "internal server error" in msg:
        return ERROR_CLASS_API_ERROR
    return ERROR_CLASS_UNKNOWN


# --- Public builders -----------------------------------------------------

def build_provider_attempt(
    *,
    decision_id: str,
    attempt_idx: int,
    provider: ProviderType | str,
    model: str,
    success: bool,
    duration_ms: float,
    error: BaseException | str | None = None,
    error_class: str | None = None,
    error_detail: str = "",
    stop_reason: str | None = None,
    usage: dict[str, int] | None = None,
    cost_estimate_usd: float | None = None,
    circuit_state: str = "closed",
    outcome: str | None = None,
) -> ProviderAttemptRecord:
    """Construct a redacted, classified ProviderAttemptRecord.

    Auto-derives:
        - error_class from exception type/message if not provided.
        - tier from provider name.
        - cost_estimate_usd from token usage if not provided.
    Always:
        - redacts error_detail to ≤ MAX_ERROR_DETAIL_CHARS, scrubs secrets.
    """
    provider_name = _provider_value(provider)
    derived_class = error_class or (classify_error(error) if error is not None or error_detail else "")
    detail_source = error_detail or (str(error) if error is not None else "")
    detail_redacted = redact_error_detail(detail_source) if detail_source else ""
    usage_dict = {
        str(k): max(0, int(v))
        for k, v in (usage or {}).items()
        if isinstance(v, (int, float))
    }
    if cost_estimate_usd is None:
        cost_estimate_usd = estimate_cost_usd(
            provider,
            prompt_tokens=int(usage_dict.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage_dict.get("completion_tokens", 0) or 0),
        )
    derived_outcome = outcome or ("success" if success else "failed")
    return ProviderAttemptRecord(
        decision_id=decision_id,
        attempt_idx=max(0, int(attempt_idx)),
        provider=provider_name,
        model=str(model or ""),
        tier=tier_for_provider(provider),
        success=bool(success),
        outcome=derived_outcome,
        error_class=derived_class,
        error_detail=detail_redacted,
        duration_ms=max(0.0, float(duration_ms)),
        stop_reason=str(stop_reason or ""),
        usage=usage_dict,
        cost_estimate_usd=max(0.0, float(cost_estimate_usd)),
        circuit_state=str(circuit_state or "closed"),
    )


def _default_audit_path() -> Path:
    env = os.environ.get("DGC_ROUTER_AUDIT_LOG", "").strip()
    if env:
        return Path(env)
    return Path.home() / ".dharma" / "logs" / "router" / "routing_decisions.jsonl"


def _audit_enabled() -> bool:
    raw = os.environ.get("DGC_ROUTER_AUDIT_ENABLE", "1").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _telemetry_enabled() -> bool:
    raw = os.environ.get("DGC_ROUTER_TELEMETRY_ENABLE", "1").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _helper_disabled() -> bool:
    """Emergency kill-switch: DGC_ROUTE_WITNESS_DISABLE_HELPER=1 disables
    all emissions from this module. ModelRouter falls back to its prior
    direct emission path (if any). Set ONLY if the helper itself misbehaves.
    """
    raw = os.environ.get("DGC_ROUTE_WITNESS_DISABLE_HELPER", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _coerce_provider_list(items: Iterable[ProviderType | str]) -> list[str]:
    out: list[str] = []
    for item in items:
        out.append(_provider_value(item))
    return out


def _resolve_decision_outcome(
    *,
    explicit: str | None,
    attempts: list[ProviderAttemptRecord],
) -> str:
    if explicit:
        return explicit
    if not attempts:
        return "no_route"
    if any(a.success for a in attempts):
        return "success"
    classes = {a.error_class for a in attempts}
    if classes == {ERROR_CLASS_TIMEOUT}:
        return "timeout"
    if not classes - {""}:
        return "all_failed"
    return "all_failed"


def _decision_to_jsonl_row(
    record: RoutingDecisionRecord,
) -> dict[str, Any]:
    return {
        "row_kind": "decision",
        "schema_version": record.schema_version or "v1",
        "decision_id": record.decision_id,
        "ts": record.created_at.isoformat(),
        "session_id": record.session_id,
        "task_id": record.task_id,
        "run_id": record.run_id,
        "task_signature": record.task_signature,
        "task_type": record.task_type,
        "caller": record.caller,
        "action_name": record.action_name,
        "route_path": record.route_path,
        "decision_class": record.decision_class,
        "requires_human": record.requires_human,
        "confidence": record.confidence,
        "reasons": list(record.reasons),
        "candidate_chain": list(record.candidate_chain),
        "selected_provider": record.selected_provider,
        "selected_model": record.selected_model_hint,
        "selected_tier": record.selected_tier,
        "widened_from": record.widened_from,
        "n_attempts": record.n_attempts,
        "outcome": record.outcome,
        "duration_ms": record.duration_ms,
        "total_tokens": record.total_tokens,
        "cost_estimate_usd": record.cost_estimate_usd,
        "metadata": dict(record.metadata),
    }


def _attempt_to_jsonl_row(
    record: ProviderAttemptRecord,
) -> dict[str, Any]:
    return {
        "row_kind": "attempt",
        "schema_version": record.schema_version or "v1",
        "decision_id": record.decision_id,
        "attempt_idx": record.attempt_idx,
        "ts": record.created_at.isoformat(),
        "provider": record.provider,
        "model": record.model,
        "tier": record.tier,
        "success": record.success,
        "outcome": record.outcome,
        "error_class": record.error_class,
        "error_detail": record.error_detail,
        "duration_ms": record.duration_ms,
        "stop_reason": record.stop_reason,
        "usage": dict(record.usage),
        "cost_estimate_usd": record.cost_estimate_usd,
        "circuit_state": record.circuit_state,
    }


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Atomic append of all rows in one open()/write()/close().

    SQLite transactions are atomic; for the audit JSONL we approximate
    atomicity by writing all rows under a single file handle. Concurrent
    writers can still interleave at the OS level; for true atomicity the
    decision row + attempts would need a separate per-decision file.
    Phase 1 accepts the residual interleave risk — every row carries
    decision_id so consumers can reconstruct the decision tree.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload)


_global_telemetry: TelemetryPlaneStore | None = None


def _shared_telemetry() -> TelemetryPlaneStore:
    """Lazily construct a singleton TelemetryPlaneStore on the default DB.

    Callers that already own a store should pass it via the kwarg; this
    fallback exists for direct-call sites (heartbeat pulse, inquiry chew)
    that don't have access to the SwarmManager-owned instance.
    """
    global _global_telemetry
    if _global_telemetry is None:
        _global_telemetry = TelemetryPlaneStore(db_path=DEFAULT_TELEMETRY_DB)
    return _global_telemetry


async def emit_routing_decision(
    *,
    decision_id: str,
    action_name: str,
    route_path: str,
    selected_provider: ProviderType | str,
    selected_model: str,
    candidate_chain: Iterable[ProviderType | str],
    decision_class: str,
    caller: str,
    duration_ms: float,
    attempts: list[ProviderAttemptRecord],
    task_type: str = "unknown",
    task_signature: str = "",
    confidence: float = 0.0,
    requires_human: bool = False,
    reasons: list[str] | None = None,
    widened_from: ProviderType | str | None = None,
    session_id: str = "",
    task_id: str = "",
    run_id: str = "",
    total_tokens: int | None = None,
    cost_estimate_usd: float | None = None,
    outcome: str | None = None,
    metadata: dict[str, Any] | None = None,
    telemetry: TelemetryPlaneStore | None = None,
    audit_log_path: Path | None = None,
    telemetry_enabled: bool | None = None,
    audit_enabled: bool | None = None,
) -> None:
    """Write one canonical RoutingDecisionRecord + N ProviderAttemptRecord rows.

    Best-effort. Logs and swallows all exceptions; never raises into the
    caller. A witness write failure must never break a real LLM call.
    Honours kill-switch ``DGC_ROUTE_WITNESS_DISABLE_HELPER=1``.
    """
    if _helper_disabled():
        return

    try:
        attempts = list(attempts)
        chain = [
            str(_redact_json_value(item))
            for item in _coerce_provider_list(candidate_chain)
        ]
        widened = (
            str(_redact_json_value(_provider_value(widened_from)))
            if widened_from else ""
        )
        selected = str(_redact_json_value(_provider_value(selected_provider)))
        safe_metadata = _redact_json_value(metadata or {})
        if not isinstance(safe_metadata, dict):
            safe_metadata = {}
        safe_reasons = [
            str(_redact_json_value(item)) for item in (reasons or [])
        ]
        if decision_class not in DECISION_CLASSES:
            logger.debug("route_witness: unknown decision_class %r, allowing through", decision_class)
        derived_outcome = _resolve_decision_outcome(explicit=outcome, attempts=attempts)
        if total_tokens is None:
            total_tokens = sum(
                int(a.usage.get("total_tokens", 0) or 0)
                or (
                    int(a.usage.get("prompt_tokens", 0) or 0)
                    + int(a.usage.get("completion_tokens", 0) or 0)
                )
                for a in attempts
            )
        if cost_estimate_usd is None:
            cost_estimate_usd = round(sum(a.cost_estimate_usd for a in attempts), 6)
        record = RoutingDecisionRecord(
            decision_id=decision_id,
            action_name=str(_redact_json_value(action_name)),
            route_path=str(_redact_json_value(route_path)),
            selected_provider=selected,
            selected_model_hint=str(_redact_json_value(selected_model or "")),
            confidence=float(confidence),
            requires_human=bool(requires_human),
            session_id=str(_redact_json_value(session_id)),
            task_id=str(_redact_json_value(task_id)),
            run_id=str(_redact_json_value(run_id)),
            reasons=safe_reasons,
            metadata=safe_metadata,
            schema_version="v1",
            task_signature=str(_redact_json_value(task_signature)),
            task_type=str(_redact_json_value(task_type)),
            caller=str(_redact_json_value(caller)),
            decision_class=str(_redact_json_value(decision_class)),
            selected_tier=tier_for_provider(selected) if selected else "unknown",
            widened_from=widened,
            candidate_chain=chain,
            n_attempts=len(attempts),
            outcome=derived_outcome,
            duration_ms=max(0.0, float(duration_ms)),
            total_tokens=max(0, int(total_tokens or 0)),
            cost_estimate_usd=max(0.0, float(cost_estimate_usd or 0.0)),
        )
    except Exception:  # noqa: BLE001
        logger.warning("route_witness: failed to construct RoutingDecisionRecord", exc_info=True)
        return

    # SQLite write
    if (_telemetry_enabled() if telemetry_enabled is None else bool(telemetry_enabled)):
        try:
            store = telemetry or _shared_telemetry()
            await store.record_routing_decision(record)
            for attempt in attempts:
                await store.record_provider_attempt(attempt)
        except Exception:  # noqa: BLE001
            logger.warning("route_witness: telemetry write failed", exc_info=True)

    # JSONL audit (decision row first, then attempts in attempt_idx order)
    if (_audit_enabled() if audit_enabled is None else bool(audit_enabled)):
        try:
            path = audit_log_path or _default_audit_path()
            sorted_attempts = sorted(attempts, key=lambda a: a.attempt_idx)
            rows = [_decision_to_jsonl_row(record)] + [
                _attempt_to_jsonl_row(a) for a in sorted_attempts
            ]
            _append_jsonl(path, rows)
        except Exception:  # noqa: BLE001
            logger.warning("route_witness: audit JSONL write failed", exc_info=True)


__all__ = [
    "DECISION_CLASSES",
    "ERROR_CLASSES",
    "ERROR_CLASS_API_ERROR",
    "ERROR_CLASS_AUTH_ERROR",
    "ERROR_CLASS_CREDIT_EXHAUSTED",
    "ERROR_CLASS_EMPTY_CONTENT",
    "ERROR_CLASS_MODEL_UNAVAILABLE",
    "ERROR_CLASS_NETWORK",
    "ERROR_CLASS_RATE_LIMIT",
    "ERROR_CLASS_TIMEOUT",
    "ERROR_CLASS_UNKNOWN",
    "MAX_ERROR_DETAIL_CHARS",
    "OUTCOMES",
    "build_provider_attempt",
    "classify_error",
    "emit_routing_decision",
    "estimate_cost_usd",
    "redact_error_detail",
    "tier_for_provider",
]
