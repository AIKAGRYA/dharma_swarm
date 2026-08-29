"""Provider-route selftest for Forge/RSI Lab high-slot runs.

The command has two levels:

* config mode (default): resolves the candidate model ids without calling any
  provider. This is safe for CI and cheap operator inspection.
* live mode (``--live``): sends a tiny exact-identity probe through each route
  until the requested number of independent callable families is reached, then
  writes a redacted receipt under the lab state directory.

No secret values are printed or persisted. A callable row means the provider
returned non-empty content and the served model identity matched the requested
route according to the Forge runner's exact-route probe.
"""

from __future__ import annotations

import asyncio
import math
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from uuid import uuid4

from dharma_swarm.forge_lab.newrun import (
    DEFAULT_DIVERSE_MUTATOR,
    DEFAULT_DIVERSE_SOLVER,
    DEFAULT_DIVERSE_VERIFIER,
    DEFAULT_FAST_MUTATOR,
    DEFAULT_FAST_SOLVER,
    DEFAULT_FAST_VERIFIER,
    _family,
)
from dharma_swarm.forge_lab.state_io import (
    content_digest,
    provider_selftest_root,
    safe_json,
    write_json_exclusive,
)
from dharma_swarm.forge_lab.unattended_budget import (
    BudgetPolicy,
    PROVIDER_DAILY,
    PROVIDER_MONTHLY,
    PROVIDER_RUN,
    reserve_budget,
    settle_budget,
)
from dharma_swarm.forge_lab.version import (
    PACKAGE_VERSION,
    source_commit,
    source_tree_state,
)

PROVIDER_SELFTEST_SCHEMA = "rsi_lab.provider_selftest.v3"
DEFAULT_PROFILE = "frontier"
ALIAS_POLICY_VERSION = "exact_model_identity.v2"
FAILURE_TAXONOMY_VERSION = "rsi_lab.provider_failure_taxonomy.v1"
PROBE_MAX_OUTPUT_TOKENS = 256
PROBE_MAX_INPUT_TOKEN_LIABILITY = 256
PROBE_MAX_TOTAL_TOKEN_LIABILITY = 512
PROBE_RESERVED_USD = 0.01
OPENAI_GPT55_INPUT_USD_PER_TOKEN = 5.0 / 1_000_000
OPENAI_GPT55_OUTPUT_USD_PER_TOKEN = 30.0 / 1_000_000
OPENAI_ADAPTER_ENDPOINT = "/v1/chat/completions"
ZHIPU_GENERAL_BASE_URL = "https://api.z.ai/api/paas/v4"
MOONSHOT_FIRST_PARTY_BASE_URL = "https://api.moonshot.ai/v1"
UNATTENDED_MAX_INPUT_TOKEN_LIABILITY = 24_000
UNATTENDED_MAX_OUTPUT_TOKEN_LIABILITY = 8_000
UNATTENDED_PER_CALL_ACCOUNTING_RESERVATION_USD = 0.25

# Pricing evidence is deliberately short-lived. A stale source snapshot must
# make a route non-admissible until an operator refreshes the checked schedule;
# it must never silently become an evergreen vendor-liability claim.
PRICING_CHECKED_AT = "2026-08-27T00:00:00Z"
PRICING_VALID_THROUGH = "2026-09-03T23:59:59Z"

_PINNED_PRICING: dict[tuple[str, str], dict[str, Any]] = {
    ("openai", "gpt-5.5"): {
        "pricing_id": "openai_gpt_5_5_api_usd_2026_08_27",
        "input_usd_per_token": OPENAI_GPT55_INPUT_USD_PER_TOKEN,
        "output_usd_per_token": OPENAI_GPT55_OUTPUT_USD_PER_TOKEN,
        "endpoint_policy_id": "provider_default_retry_free_v1",
        "checked_at": PRICING_CHECKED_AT,
        "valid_through": PRICING_VALID_THROUGH,
    },
    ("zhipu", "glm-5.1"): {
        "pricing_id": "zai_general_api_glm_5_1_usd_2026_08_27",
        "input_usd_per_token": 1.4 / 1_000_000,
        "output_usd_per_token": 4.4 / 1_000_000,
        "endpoint_policy_id": "zhipu_general_paas_v4",
        "checked_at": PRICING_CHECKED_AT,
        "valid_through": PRICING_VALID_THROUGH,
    },
    ("moonshot", "kimi-k2.7-code"): {
        "pricing_id": "moonshot_kimi_k2_7_code_standard_usd_2026_08_27",
        # Standard Kimi K2.7 Code, not HighSpeed. Cache-hit input is charged
        # here at the full input price, so this bound never claims a discount.
        "input_usd_per_token": 0.95 / 1_000_000,
        "output_usd_per_token": 4.00 / 1_000_000,
        "endpoint_policy_id": "moonshot_first_party_open_platform_v1",
        "source_url": "https://platform.kimi.ai/docs/pricing/chat-k27-code",
        "checked_at": PRICING_CHECKED_AT,
        "valid_through": PRICING_VALID_THROUGH,
    },
}


class _SanitizedProviderHTTPError(RuntimeError):
    def __init__(self, status_code: int):
        super().__init__(f"provider_http_status_{status_code}")
        self.status_code = status_code


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        value = (item or "").strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def profile_model_ids(profile: str, *, current_model: str | None = None) -> list[str]:
    """Return ordered model ids for a provider selftest profile."""

    profile = (profile or DEFAULT_PROFILE).strip().lower()
    current = (current_model or "").strip()
    fast = [DEFAULT_FAST_SOLVER, DEFAULT_FAST_VERIFIER, DEFAULT_FAST_MUTATOR]
    diverse = [DEFAULT_DIVERSE_SOLVER, DEFAULT_DIVERSE_VERIFIER, DEFAULT_DIVERSE_MUTATOR]
    if profile in {"fast", "offline"}:
        return _dedupe(fast)
    if profile == "staged":
        # Staged means operator-proven names, never a prose default that can
        # silently drift into authority. Values are model IDs, not secrets.
        return _dedupe(os.environ.get("RSI_LAB_STAGED_MODELS", "").split(","))
    if profile in {"current", "newrun"}:
        return _dedupe(([current] if current else []) + fast + diverse)
    if profile == "frontier":
        try:
            from dharma_swarm.model_pool import forge_high_slot_model_ids

            high_slots = list(forge_high_slot_model_ids())
        except Exception:
            high_slots = []
        return _dedupe(fast + diverse + high_slots)
    raise ValueError(
        f"unknown provider selftest profile {profile!r}; "
        "choose staged, frontier, fast, current, newrun, or offline"
    )


def _receipt_root() -> Path:
    return provider_selftest_root()


def _receipt_digest(payload: dict[str, Any]) -> str:
    unsigned = {
        key: value
        for key, value in payload.items()
        if key not in {"receipt_digest", "cached", "refresh_skipped"}
    }
    return content_digest(unsigned)


def validate_provider_receipt(
    payload: dict[str, Any],
    *,
    path: Path | None = None,
) -> list[str]:
    """Return structural, identity, and accounting failures for one receipt."""

    failures: list[str] = []
    if payload.get("schema") != PROVIDER_SELFTEST_SCHEMA:
        failures.append("wrong_schema")
    policy = payload.get("policy")
    if not isinstance(policy, dict):
        failures.append("policy_missing")
    elif payload.get("policy_digest") != content_digest(policy):
        failures.append("policy_digest_mismatch")
    if payload.get("receipt_digest") != _receipt_digest(payload):
        failures.append("receipt_digest_mismatch")
    if path is not None and payload.get("receipt") != str(path):
        failures.append("receipt_path_mismatch")
    try:
        checked = datetime.fromisoformat(str(payload.get("checked_at")).replace("Z", "+00:00"))
        if checked.tzinfo is None or checked.astimezone(timezone.utc) > datetime.now(timezone.utc):
            failures.append("checked_at_future_or_unzoned")
    except (TypeError, ValueError):
        failures.append("checked_at_invalid")
    if payload.get("live"):
        budget = payload.get("budget")
        try:
            monthly_cap = float((budget or {}).get("monthly_cap_usd"))
            budget_numeric_valid = math.isfinite(monthly_cap) and 0 <= monthly_cap <= 30.0
        except (TypeError, ValueError):
            budget_numeric_valid = False
        if (
            not isinstance(budget, dict)
            or not str(budget.get("reservation_digest") or "").startswith("sha256:")
            or not str(budget.get("settlement_digest") or "").startswith("sha256:")
            or not budget_numeric_valid
        ):
            failures.append("provider_budget_evidence_invalid")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        failures.append("rows_missing_or_invalid")
        rows = []
    callable_rows = [row for row in rows if row.get("callable")]
    admission_rows = [row for row in rows if row.get("admission_eligible")]
    for row in rows:
        calls = row.get("probe_calls", 0)
        if not isinstance(calls, int) or isinstance(calls, bool) or calls < 0:
            failures.append("probe_numeric_evidence_invalid")
            break
        if calls <= 0:
            continue
        max_output = row.get("max_output_tokens")
        max_total = row.get("max_total_token_liability")
        reserved = row.get("reserved_usd")
        numeric_valid = bool(
            isinstance(max_output, int)
            and not isinstance(max_output, bool)
            and max_output == PROBE_MAX_OUTPUT_TOKENS
            and isinstance(max_total, int)
            and not isinstance(max_total, bool)
            and max_total == PROBE_MAX_TOTAL_TOKEN_LIABILITY
            and isinstance(reserved, (int, float))
            and not isinstance(reserved, bool)
            and math.isfinite(float(reserved))
            and float(reserved) == PROBE_RESERVED_USD
        )
        if (
            row.get("failure_taxonomy") != FAILURE_TAXONOMY_VERSION
            or row.get("result_category") in {None, "not_probed"}
            or not numeric_valid
            or row.get("transport_requests_verified") != calls
            or row.get("retry_liability")
            != "max_retries_zero_exactly_one_dispatch"
            or row.get("usd_reservation_scope")
            not in {
                "internal_ledger_not_vendor_liability_cap",
                "pinned_public_tariff_bound",
            }
            or row.get("within_reserved_usd") is False
        ):
            failures.append("probe_liability_or_taxonomy_invalid")
            break
    for row in callable_rows:
        if (
            not str(row.get("provider") or "").strip()
            or not str(row.get("transport_id") or "").strip()
            or row.get("endpoint_policy_id")
            != _endpoint_policy_id(str(row.get("provider") or ""))
            or row.get("result_category") != "success"
            or row.get("stage") != "complete"
            or not isinstance(row.get("probe_calls"), int)
            or isinstance(row.get("probe_calls"), bool)
            or row["probe_calls"] < 1
            or row.get("usage_verified") is not True
            or not isinstance(row.get("usage"), dict)
            or not _usage_is_coherent(row["usage"])
            or _probe_model_identity(str(row.get("requested_model") or ""))
            != _probe_model_identity(str(row.get("served_model") or ""))
        ):
            failures.append("callable_row_incomplete")
            break
    for row in rows:
        if row.get("admission_eligible") and (
            row.get("callable") is not True
            or row.get("pricing_verified") is not True
            or row.get("unattended_budget_eligible") is not True
            or row.get("within_reserved_usd") is not True
            or isinstance(row.get("provider_usd_verified"), bool)
            or not isinstance(row.get("provider_usd_verified"), (int, float))
            or not math.isfinite(float(row["provider_usd_verified"]))
            or row.get("pricing")
            != _pinned_pricing(
                str(row.get("provider") or ""),
                str(row.get("requested_model") or ""),
            )
        ):
            failures.append("admission_pricing_evidence_invalid")
            break
    independent = _independent_routes(rows)
    if payload.get("callable_count") != len(callable_rows):
        failures.append("callable_count_mismatch")
    if payload.get("admission_eligible_count") != len(admission_rows):
        failures.append("admission_eligible_count_mismatch")
    if payload.get("independent_route_count") != len(independent):
        failures.append("independent_route_count_mismatch")
    if sorted(payload.get("independent_routes") or []) != independent:
        failures.append("independent_routes_mismatch")
    if payload.get("probe_call_count") != sum(
        row.get("probe_calls", 0)
        for row in rows
        if isinstance(row.get("probe_calls", 0), int)
        and not isinstance(row.get("probe_calls", 0), bool)
    ):
        failures.append("probe_call_count_mismatch")
    return failures


def _write_live_receipt(payload: dict[str, Any]) -> Path:
    """Persist a collision-proof append-only receipt and bind its path."""

    root = _receipt_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = re.sub(r"[^0-9TZ]", "", str(payload["checked_at"]))
    suffix = payload["profile"].replace("/", "_")
    for _ in range(8):
        receipt_id = uuid4().hex
        path = root / f"{stamp}__{suffix}__{receipt_id}__provider_selftest.json"
        stored = {
            **payload,
            "receipt_id": receipt_id,
            "receipt": str(path),
            "cached": False,
        }
        stored["receipt_digest"] = _receipt_digest(stored)
        try:
            write_json_exclusive(path, stored)
        except FileExistsError:
            continue
        payload.clear()
        payload.update(stored)
        return path
    raise RuntimeError("provider_selftest_receipt_id_collision")


def _policy_payload(
    *,
    profile: str,
    current_model: str | None,
    requested_models: list[str],
    require: int,
    timeout_s: int,
    max_probes: int,
) -> dict[str, Any]:
    """Bind a live observation to source, configuration, and probe policy."""

    return {
        "source": {
            "package_version": PACKAGE_VERSION,
            "commit": source_commit(),
            "tree_state": source_tree_state(),
        },
        "configuration": {
            "profile": profile,
            "current_model": (current_model or "").strip() or None,
            "requested_models": requested_models,
        },
        "probe_policy": {
            "require_independent_routes": require,
            "timeout_s": timeout_s,
            "max_provider_calls": max_probes,
            "max_output_tokens_per_probe": PROBE_MAX_OUTPUT_TOKENS,
            "max_total_token_liability_per_probe": PROBE_MAX_TOTAL_TOKEN_LIABILITY,
            "internal_accounting_reservation_usd_per_probe": PROBE_RESERVED_USD,
            "unpriced_routes_admission_eligible": False,
            "alias_policy": ALIAS_POLICY_VERSION,
            "failure_taxonomy": FAILURE_TAXONOMY_VERSION,
            "cooldowns_seconds": {"rate_limited": 900, "timeout": 60, "provider_error": 120},
        },
    }


def _latest_compatible_receipt(
    *,
    policy_digest: str,
    min_refresh_interval_s: int,
) -> tuple[dict[str, Any] | None, Path | None]:
    if min_refresh_interval_s <= 0:
        return None, None
    root = _receipt_root()
    if not root.is_dir():
        return None, None
    now = datetime.now(timezone.utc)
    for path in sorted(root.glob("*provider_selftest.json"), reverse=True):
        payload = safe_json(path)
        if not payload or validate_provider_receipt(payload, path=path):
            continue
        if not payload.get("live") or payload.get("policy_digest") != policy_digest:
            continue
        try:
            checked = datetime.fromisoformat(str(payload["checked_at"]).replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            continue
        age = (now - checked).total_seconds()
        if 0 <= age <= min_refresh_interval_s:
            return payload, path
    return None, None


def _probe_model_identity(model_id: str) -> str:
    return str(model_id or "").strip().casefold()


def _wire_model_for_provider(provider_name: str, configured_model: str) -> str:
    """Return the exact model identifier placed on one provider request.

    Ollama uses ``:cloud`` only as a local routing selector.  Its OpenAI-
    compatible cloud endpoint receives the suffix-free model identifier.  The
    distinction is recorded explicitly; it is never used to normalize a
    provider's served-model assertion after the fact.
    """

    provider = str(provider_name or "").strip().casefold()
    model = str(configured_model or "").strip()
    if provider == "ollama":
        if model.endswith(":cloud"):
            return model[: -len(":cloud")]
        if model.endswith("-cloud"):
            return model[: -len("-cloud")]
    return model


def _endpoint_policy_id(provider_name: str) -> str:
    provider = str(provider_name or "").strip().casefold()
    if provider == "zhipu":
        return "zhipu_general_paas_v4"
    if provider == "ollama":
        return "ollama_tokenized_cloud_v1"
    if provider == "moonshot":
        return "moonshot_first_party_open_platform_v1"
    return "provider_default_retry_free_v1"


def _pinned_pricing(provider_name: str, model_id: str) -> dict[str, Any] | None:
    key = (
        str(provider_name or "").strip().casefold(),
        _probe_model_identity(model_id),
    )
    schedule = _PINNED_PRICING.get(key)
    if schedule is None:
        return None
    if schedule["endpoint_policy_id"] != _endpoint_policy_id(key[0]):
        return None
    try:
        checked = datetime.fromisoformat(
            str(schedule["checked_at"]).replace("Z", "+00:00")
        )
        valid_through = datetime.fromisoformat(
            str(schedule["valid_through"]).replace("Z", "+00:00")
        )
    except (KeyError, TypeError, ValueError):
        return None
    now = datetime.now(timezone.utc)
    if (
        checked.tzinfo is None
        or valid_through.tzinfo is None
        or checked.astimezone(timezone.utc) > now
        or valid_through.astimezone(timezone.utc) < now
        or valid_through <= checked
    ):
        return None
    pricing = dict(schedule)
    pricing["currency"] = "USD"
    pricing["cached_input_discount_claimed"] = False
    pricing["model"] = str(model_id)
    pricing["unattended_max_call_liability_usd"] = round(
        UNATTENDED_MAX_INPUT_TOKEN_LIABILITY * pricing["input_usd_per_token"]
        + UNATTENDED_MAX_OUTPUT_TOKEN_LIABILITY * pricing["output_usd_per_token"],
        9,
    )
    pricing["unattended_accounting_reservation_usd"] = (
        UNATTENDED_PER_CALL_ACCOUNTING_RESERVATION_USD
    )
    pricing["unattended_budget_eligible"] = bool(
        pricing["unattended_max_call_liability_usd"]
        <= UNATTENDED_PER_CALL_ACCOUNTING_RESERVATION_USD
    )
    return pricing


def _enforce_endpoint_policy(provider: Any, provider_name: str) -> None:
    """Force price-bound routes onto their exact first-party API endpoint."""

    normalized = str(provider_name or "").strip().casefold()
    enforced_url = {
        "zhipu": ZHIPU_GENERAL_BASE_URL,
        "moonshot": MOONSHOT_FIRST_PARTY_BASE_URL,
    }.get(normalized)
    if enforced_url is None:
        return
    if getattr(provider, "_client", None) is not None or not hasattr(provider, "_base_url"):
        raise RuntimeError(f"{normalized}_endpoint_control_unavailable")
    # Receipts persist the stable policy identifier, never the endpoint URL.
    provider._base_url = enforced_url


def _resolve_selftest_slot(route_id: str) -> Any | None:
    """Resolve a model route without collapsing an explicit provider choice.

    The general Forge slot helper chooses the first pool route for a logical
    model. A provider selftest must instead preserve an operator's explicit
    ``provider:model`` selection so, for example, an OpenAI credential is never
    substituted with a Codex OAuth route serving the same model name.
    """

    from dharma_swarm.forge_v1.forge_v2.runner_slots import _slot_for_id
    from dharma_swarm.models import ProviderType

    text = str(route_id or "").strip()
    if ":" in text:
        provider_name, wire_model = text.split(":", 1)
        try:
            provider = ProviderType(provider_name.strip().casefold())
        except ValueError:
            provider = None
        if provider is not None and wire_model.strip():
            return SimpleNamespace(
                provider=provider,
                model_id=wire_model.strip(),
                route_id=text,
                tier="frontier",
            )
    slot = _slot_for_id(text)
    if slot is not None:
        slot.route_id = text
    return slot


def _sanitized_http_status(exc: BaseException) -> int | None:
    """Extract only an HTTP status; never persist an exception body or URL."""

    candidates = [exc, getattr(exc, "response", None)]
    for candidate in candidates:
        for name in ("status_code", "status"):
            value = getattr(candidate, name, None)
            if isinstance(value, int) and 100 <= value <= 599:
                return value
    match = re.search(r"(?<![0-9])(4(?:01|02|03|08|09|29)|5(?:00|02|03|04))(?![0-9])", str(exc))
    return int(match.group(1)) if match else None


def _exception_hint(exc: BaseException, status: int | None) -> str:
    name = type(exc).__name__
    lowered = name.casefold()
    if status == 429 or "ratelimit" in lowered or "rate_limit" in lowered:
        return "rate_limited"
    if status == 402 or "quota" in lowered or "payment" in lowered:
        return "quota_or_payment"
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or "timeout" in lowered:
        return "timeout"
    if status in {401, 403} or "auth" in lowered or "permission" in lowered:
        return "authentication"
    return "provider_error_unclassified"


def _safe_usage(response: Any) -> dict[str, int]:
    raw = getattr(response, "usage", None)
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump()
    elif raw is not None and not isinstance(raw, dict):
        raw = {
            name: getattr(raw, name, None)
            for name in (
                "input_tokens",
                "prompt_tokens",
                "output_tokens",
                "completion_tokens",
                "total_tokens",
            )
        }
    if not isinstance(raw, dict):
        return {}
    aliases = {
        "input_tokens": ("input_tokens", "prompt_tokens"),
        "output_tokens": ("output_tokens", "completion_tokens"),
        "total_tokens": ("total_tokens",),
    }
    usage: dict[str, int] = {}
    for canonical, names in aliases.items():
        value = next((raw.get(name) for name in names if raw.get(name) is not None), None)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            usage[canonical] = value
    return usage


def _usage_is_coherent(usage: dict[str, int]) -> bool:
    """Reject adapter placeholders and internally inconsistent usage."""

    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")
    return bool(
        isinstance(input_tokens, int)
        and not isinstance(input_tokens, bool)
        and input_tokens > 0
        and isinstance(output_tokens, int)
        and not isinstance(output_tokens, bool)
        and 0 <= output_tokens <= PROBE_MAX_OUTPUT_TOKENS
        and isinstance(total_tokens, int)
        and not isinstance(total_tokens, bool)
        and 0 < total_tokens <= PROBE_MAX_TOTAL_TOKEN_LIABILITY
        and total_tokens == input_tokens + output_tokens
    )


def _probe_cost_evidence(provider: str, requested_model: str, usage: dict[str, int]) -> dict[str, Any]:
    """Return conservative, endpoint-specific cost evidence without guessing.

    The canonical OpenAI adapter uses Chat Completions and normalizes that
    endpoint's ``prompt_tokens``/``completion_tokens`` fields into the common
    input/output names above. Other providers remain full-reservation charged
    in the internal ledger, without claiming that reservation bounds the
    provider's invoice, unless an equally pinned price schedule is added here.
    """

    normalized_provider = str(provider or "").strip().casefold()
    pricing = _pinned_pricing(normalized_provider, requested_model)
    evidence: dict[str, Any] = {
        "adapter_endpoint": OPENAI_ADAPTER_ENDPOINT
        if normalized_provider == "openai"
        else "provider_adapter_complete",
        "cost_basis": "internal_accounting_reservation_v3",
        "reserved_usd": PROBE_RESERVED_USD,
        "usd_reservation_scope": "internal_ledger_not_vendor_liability_cap",
        "vendor_liability_ceiling_usd": None,
        "pricing_verified": False,
        "unattended_budget_eligible": False,
    }
    if pricing is None:
        evidence["provider_usd_verified"] = None
        return evidence
    worst_case = round(
        PROBE_MAX_INPUT_TOKEN_LIABILITY * pricing["input_usd_per_token"]
        + PROBE_MAX_OUTPUT_TOKENS * pricing["output_usd_per_token"],
        9,
    )
    evidence["pricing"] = pricing
    evidence["pricing_verified"] = True
    evidence["unattended_budget_eligible"] = pricing["unattended_budget_eligible"]
    evidence["vendor_liability_ceiling_usd"] = worst_case
    evidence["within_reserved_usd"] = worst_case <= PROBE_RESERVED_USD
    evidence["usd_reservation_scope"] = "pinned_public_tariff_bound"
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if input_tokens is None or output_tokens is None:
        # Once dispatch begins, a provider failure may still incur the full
        # bounded response liability.  Charge the pinned worst case.
        evidence["provider_usd_verified"] = worst_case
        return evidence
    estimated = (
        input_tokens * pricing["input_usd_per_token"]
        + output_tokens * pricing["output_usd_per_token"]
    )
    # The liability reservation is deliberately rounded up relative to the
    # exact token arithmetic; a response above it is an accounting failure.
    evidence["provider_usd_verified"] = round(estimated, 9)
    return evidence


async def _complete_exactly_one_transport(
    provider: Any,
    request: Any,
    *,
    provider_name: str,
    timeout_s: int,
    before_dispatch: Callable[[], None] | None = None,
) -> Any:
    """Dispatch once with SDK retries and model fallback explicitly disabled."""

    from dharma_swarm.forge_v1.providers import _complete_and_close
    from dharma_swarm.models import LLMResponse

    _enforce_endpoint_policy(provider, provider_name)

    if provider_name == "ollama":
        if getattr(provider, "transport_mode", None) != "cloud_api":
            raise RuntimeError("ollama_transport_not_tokenized_cloud")
        client = provider._get_client()
        headers = provider._headers_or_raise()
        headers["Content-Type"] = "application/json"
        messages = provider._build_messages(request)
        wire_model = _wire_model_for_provider(provider_name, str(request.model))
        payload: dict[str, Any] = {
            "model": wire_model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }
        if request.tools:
            payload["tools"] = request.tools
        try:
            if before_dispatch is not None:
                before_dispatch()
            response = await asyncio.wait_for(
                client.post(
                    f"{provider.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                ),
                timeout=timeout_s,
            )
            if response.status_code != 200:
                raise _SanitizedProviderHTTPError(int(response.status_code))
            data = response.json()
            choice = (data.get("choices") or [])[0]
            message = choice.get("message") or {}
            content = message.get("content")
            if not isinstance(content, str):
                content = str(message.get("reasoning_content") or "")
            usage = data.get("usage") or {}
            return LLMResponse(
                content=content,
                model=str(data.get("model") or ""),
                usage={
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                },
                stop_reason=str(choice.get("finish_reason") or ""),
            )
        finally:
            close = getattr(provider, "close", None)
            if callable(close):
                await close()

    client_factory = getattr(provider, "_client_or_raise", None)
    if not callable(client_factory):
        raise RuntimeError("provider_retry_control_unavailable")
    client = client_factory()
    with_options = getattr(client, "with_options", None)
    if not callable(with_options):
        raise RuntimeError("provider_retry_control_unavailable")
    bounded_client = with_options(max_retries=0)
    if getattr(bounded_client, "max_retries", None) != 0:
        raise RuntimeError("provider_retry_control_unverified")
    provider._client = bounded_client
    if before_dispatch is not None:
        before_dispatch()
    return await _complete_and_close(provider, request, timeout_s=timeout_s)


def _probe_route_with_receipt(slot: Any, *, timeout_s: int) -> dict[str, Any]:
    """One redacted exact-route probe that preserves typed failure evidence."""

    from dharma_swarm.forge_v1.canonical import KIMI_TEMP1, _provider_for_slot
    from dharma_swarm.models import LLMRequest

    started = time.monotonic()
    requested_model = str(slot.model_id)
    receipt: dict[str, Any] = {
        "outcome": "unavailable",
        "callable": False,
        "requested_model": requested_model,
        "requested_family": _family(requested_model),
        "max_output_tokens": PROBE_MAX_OUTPUT_TOKENS,
        "max_total_token_liability": PROBE_MAX_TOTAL_TOKEN_LIABILITY,
        "reserved_usd": PROBE_RESERVED_USD,
        "cost_basis": "internal_accounting_reservation_v3",
        "usd_reservation_scope": "internal_ledger_not_vendor_liability_cap",
        "vendor_liability_ceiling_usd": None,
        "transport_requests_verified": None,
        "retry_liability": "max_retries_zero_exactly_one_dispatch",
        "probe_calls": 0,
    }

    def finish(**fields: Any) -> dict[str, Any]:
        receipt.update(fields)
        receipt["latency_ms"] = max(0, round((time.monotonic() - started) * 1000))
        return receipt

    try:
        provider, wire = _provider_for_slot(slot, timeout_s=timeout_s)
    except Exception as exc:
        status = _sanitized_http_status(exc)
        return finish(
            stage="config",
            error_type=type(exc).__name__[:96],
            http_status=status,
            error_category_hint=_exception_hint(exc, status),
        )
    provider_name = str(getattr(slot.provider, "value", slot.provider))
    requested_wire_model = _wire_model_for_provider(provider_name, str(wire))
    receipt["requested_route_model"] = requested_model
    receipt["requested_model"] = requested_wire_model
    receipt["endpoint_policy_id"] = _endpoint_policy_id(provider_name)
    receipt["route_to_wire_mapping"] = (
        "ollama_cloud_selector_removed_before_dispatch"
        if provider_name == "ollama" and requested_model != requested_wire_model
        else "identity"
    )
    request = LLMRequest(
        model=wire,
        messages=[{"role": "user", "content": "Reply with the single word OK."}],
        max_tokens=PROBE_MAX_OUTPUT_TOKENS,
        temperature=1.0 if slot.model_id in KIMI_TEMP1 else 0.2,
    )
    receipt["wire_model"] = requested_wire_model
    receipt.update(_probe_cost_evidence(provider_name, requested_wire_model, {}))

    def mark_dispatch() -> None:
        receipt["probe_calls"] = 1
        receipt["transport_requests_verified"] = 1

    try:
        response = asyncio.run(
            _complete_exactly_one_transport(
                provider,
                request,
                provider_name=provider_name,
                timeout_s=timeout_s,
                before_dispatch=mark_dispatch,
            )
        )
    except Exception as exc:
        status = _sanitized_http_status(exc)
        hint = _exception_hint(exc, status)
        return finish(
            stage="timeout" if hint == "timeout" else "call",
            error_type=type(exc).__name__[:96],
            http_status=status,
            error_category_hint=hint,
        )
    served_model = str(getattr(response, "model", "") or "").strip()
    content = str(getattr(response, "content", "") or "").strip()
    usage = _safe_usage(response)
    cost_evidence = _probe_cost_evidence(
        str(getattr(slot.provider, "value", slot.provider)),
        requested_wire_model,
        usage,
    )
    usage_fields = {
        "usage": usage,
        "usage_verified": _usage_is_coherent(usage),
        **cost_evidence,
    }
    if not served_model:
        return finish(stage="response", error_type="missing_served_model", **usage_fields)
    served_family = _family(served_model)
    if _probe_model_identity(requested_wire_model) != _probe_model_identity(served_model):
        return finish(
            stage="response",
            error_type="served_model_mismatch",
            served_model=served_model,
            served_family=served_family,
            **usage_fields,
        )
    if not content:
        return finish(
            stage="response",
            error_type="empty_content",
            served_model=served_model,
            served_family=served_family,
            **usage_fields,
        )
    if not _usage_is_coherent(usage):
        return finish(
            stage="accounting",
            error_type="usage_unverifiable",
            error_category_hint="accounting_unverifiable",
            served_model=served_model,
            served_family=served_family,
            **usage_fields,
        )
    return finish(
        outcome="callable",
        callable=True,
        stage="complete",
        served_model=served_model,
        served_family=served_family,
        **usage_fields,
    )


def _config_row(model_id: str) -> dict[str, Any]:
    from dharma_swarm.api_keys import provider_api_key_env

    slot = _resolve_selftest_slot(model_id)
    row: dict[str, Any] = {
        "model_id": model_id,
        "requested_model": str(slot.model_id) if slot is not None else model_id,
        "requested_route": model_id,
        "requested_family": _family(str(slot.model_id) if slot is not None else model_id),
        "callable": False,
        "outcome": "not_probed",
        "stage": "config",
        "live": False,
        "result_category": "not_probed",
    }
    if slot is None:
        row["slot_resolved"] = False
        row["error_type"] = "unresolved_model_id"
        return row
    row["slot_resolved"] = True
    row["provider"] = getattr(slot.provider, "value", str(slot.provider))
    row["wire_model"] = str(slot.model_id)
    key_env = provider_api_key_env(slot.provider)
    row["credential_env"] = key_env
    row["credential_present"] = bool(key_env and os.environ.get(key_env, "").strip())
    row["credential_required"] = key_env is not None
    row["transport_id"] = _transport_id(str(row["provider"]), key_env)
    return row


def _transport_id(provider: str, credential_env: str | None) -> str:
    """Identify an entitlement without persisting endpoint or credential values."""

    entitlement = str(credential_env or "credentialless_live_transport").strip().lower()
    return f"{provider.strip().lower()}::{entitlement}"


def _result_category(row: dict[str, Any]) -> str:
    if row.get("callable"):
        return "success"
    hint = str(row.get("error_category_hint") or "")
    if hint in {
        "rate_limited",
        "quota_or_payment",
        "timeout",
        "authentication",
        "provider_error_unclassified",
        "accounting_unverifiable",
    }:
        return hint
    error = str(row.get("error_type") or "").casefold()
    stage = str(row.get("stage") or "").casefold()
    status = str(row.get("http_status") or "")
    if status == "429" or "429" in error or "ratelimit" in error or "rate_limit" in error:
        return "rate_limited"
    if status == "402" or "payment" in error or "quota" in error:
        return "quota_or_payment"
    if stage == "timeout" or "timeout" in error:
        return "timeout"
    if error in {"empty_content", "missing_served_model", "malformed_response"}:
        return "malformed_response"
    if error == "usage_unverifiable" or stage == "accounting":
        return "accounting_unverifiable"
    if error == "served_model_mismatch" or "alias_confirmation" in error:
        return "identity_mismatch"
    if status in {"401", "403"} or "auth" in error or "permission" in error:
        return "authentication"
    if stage in {"config", "policy"}:
        return "configuration"
    return "provider_error_unclassified"


def _decorate_live_row(row: dict[str, Any], *, credential_env: str | None) -> dict[str, Any]:
    category = _result_category(row)
    row["result_category"] = category
    row["failure_taxonomy"] = FAILURE_TAXONOMY_VERSION
    row["transport_id"] = _transport_id(str(row.get("provider") or ""), credential_env)
    row["retryable"] = category in {
        "rate_limited",
        "timeout",
        "provider_error_unclassified",
    }
    cooldown = {
        "rate_limited": 900,
        "timeout": 60,
        "provider_error_unclassified": 120,
    }.get(category, 0)
    row["cooldown_seconds"] = cooldown
    row["admission_eligible"] = bool(
        row.get("callable")
        and row.get("pricing_verified") is True
        and row.get("unattended_budget_eligible") is True
        and row.get("within_reserved_usd") is True
        and not isinstance(row.get("provider_usd_verified"), bool)
        and isinstance(row.get("provider_usd_verified"), (int, float))
        and math.isfinite(float(row["provider_usd_verified"]))
    )
    return row


def _live_row(
    model_id: str,
    *,
    timeout_s: int,
    remaining_probe_calls: int,
) -> dict[str, Any]:
    del remaining_probe_calls
    slot = _resolve_selftest_slot(model_id)
    if slot is None:
        return {
            "model_id": model_id,
            "requested_route": model_id,
            "requested_model": model_id,
            "requested_family": _family(model_id),
            "callable": False,
            "outcome": "unavailable",
            "stage": "config",
            "error_type": "unresolved_model_id",
            "live": True,
            "probe_calls": 0,
            "result_category": "configuration",
        }
    provider = getattr(slot.provider, "value", str(slot.provider))
    from dharma_swarm.api_keys import provider_api_key_env

    credential_env = provider_api_key_env(slot.provider)
    receipt = _probe_route_with_receipt(slot, timeout_s=timeout_s)
    row = {
        "model_id": model_id,
        "requested_route": model_id,
        "provider": provider,
        "live": True,
        "probe_calls": 1,
        "max_output_tokens": PROBE_MAX_OUTPUT_TOKENS,
        "max_total_token_liability": PROBE_MAX_TOTAL_TOKEN_LIABILITY,
        "reserved_usd": PROBE_RESERVED_USD,
        "cost_basis": "internal_accounting_reservation_v3",
        "usd_reservation_scope": "internal_ledger_not_vendor_liability_cap",
        "vendor_liability_ceiling_usd": None,
        "transport_requests_verified": None,
        "retry_liability": "max_retries_zero_exactly_one_dispatch",
        **receipt,
    }
    return _decorate_live_row(row, credential_env=credential_env)


def _families(rows: list[dict[str, Any]]) -> list[str]:
    families = {
        str(row.get("served_family") or row.get("requested_family") or "")
        for row in rows
        if row.get("callable")
    }
    return sorted(family for family in families if family)


def _independent_routes(rows: list[dict[str, Any]]) -> list[str]:
    """Count distinct attested provider entitlements, not model-family labels."""

    by_provider: dict[str, str] = {}
    for row in rows:
        provider = str(row.get("provider") or "").strip().lower()
        transport = str(row.get("transport_id") or "").strip().lower()
        if not row.get("admission_eligible") or not provider or not transport:
            continue
        prior = by_provider.get(provider)
        if prior is None:
            by_provider[provider] = transport
        elif prior != transport:
            # Multiple credentials for one provider are failover capacity, not
            # genuinely independent transports for the two-route doctor gate.
            continue
    return sorted(by_provider.values())


def run_provider_selftest(
    *,
    profile: str,
    live: bool,
    require_independent_routes: int | None = None,
    current_model: str | None = None,
    timeout_s: int = 20,
    max_probes: int = 4,
    min_refresh_interval_s: int = 0,
) -> dict[str, Any]:
    """Run or plan a provider selftest and return a redacted result."""

    require = max(0, int(require_independent_routes or 0))
    timeout_s = max(1, min(int(timeout_s), 60))
    max_probes = max(1, min(int(max_probes), 4))
    model_ids = profile_model_ids(profile, current_model=current_model)
    policy = _policy_payload(
        profile=profile,
        current_model=current_model,
        requested_models=model_ids,
        require=require,
        timeout_s=timeout_s,
        max_probes=max_probes,
    )
    policy_digest = content_digest(policy)
    if live:
        cached, cached_path = _latest_compatible_receipt(
            policy_digest=policy_digest,
            min_refresh_interval_s=max(0, int(min_refresh_interval_s)),
        )
        if cached is not None:
            return {
                **cached,
                "cached": True,
                "receipt": str(cached_path),
                "refresh_skipped": "minimum_refresh_interval",
            }
    budget_reservation: dict[str, Any] | None = None
    budget_started = time.monotonic()
    if live:
        budget_reservation = reserve_budget(
            _receipt_root() / "provider_budget_ledger.jsonl",
            run_id="provider-selftest-" + uuid4().hex,
            at=_now(),
            policy=BudgetPolicy(
                policy_kind="provider_selftest_hourly",
                run_usd=PROVIDER_RUN["usd"],
                run_calls=PROVIDER_RUN["logical_calls"],
                run_requests=PROVIDER_RUN["requests"],
                run_tokens=PROVIDER_RUN["tokens"],
                run_wall_seconds=PROVIDER_RUN["wall_seconds"],
                daily_usd=PROVIDER_DAILY["usd"],
                daily_calls=PROVIDER_DAILY["logical_calls"],
                daily_requests=PROVIDER_DAILY["requests"],
                daily_tokens=PROVIDER_DAILY["tokens"],
                daily_wall_seconds=PROVIDER_DAILY["wall_seconds"],
                monthly_usd=PROVIDER_MONTHLY["usd"],
                monthly_calls=PROVIDER_MONTHLY["logical_calls"],
                monthly_requests=PROVIDER_MONTHLY["requests"],
                monthly_tokens=PROVIDER_MONTHLY["tokens"],
                monthly_wall_seconds=PROVIDER_MONTHLY["wall_seconds"],
            ),
        )
    rows: list[dict[str, Any]] = []
    # Configuration inspection is free and should report every configured
    # route. The spend bound applies only to network-capable live probes.
    probe_call_count = 0
    for model_id in model_ids:
        if live and probe_call_count >= max_probes:
            break
        row = (
            _live_row(
                model_id,
                timeout_s=timeout_s,
                remaining_probe_calls=max_probes - probe_call_count,
            )
            if live
            else _config_row(model_id)
        )
        rows.append(row)
        probe_call_count += int(row.get("probe_calls") or 0)
        if live and require and len(_independent_routes(rows)) >= require:
            break

    callable_rows = [row for row in rows if row.get("callable")]
    admission_rows = [row for row in rows if row.get("admission_eligible")]
    independent = _independent_routes(rows)
    families = _families(rows)
    ok = bool(live and callable_rows)
    failures: list[str] = []
    if not model_ids:
        failures.append("zero_profile_targets")
    if not live:
        failures.append("config_only_no_callable_route_attestation")
    if live and not callable_rows:
        failures.append("zero_callable_routes")
    if live and require and len(independent) < require:
        ok = False
        failures.append(
            f"independent_routes:{len(independent)}/{require}"
        )
    if not live and require:
        failures.append("live_probe_required_for_independent_routes")
    unresolved = [row for row in rows if not row.get("slot_resolved", True)]
    if unresolved:
        failures.append(f"unresolved_targets:{len(unresolved)}")
    if failures:
        ok = False

    payload: dict[str, Any] = {
        "schema": PROVIDER_SELFTEST_SCHEMA,
        "profile": profile,
        "live": live,
        "checked_at": _now(),
        "requested_models": model_ids,
        "probed_models": [str(row.get("model_id")) for row in rows],
        "max_probes": max_probes,
        "probe_call_count": probe_call_count,
        "require_independent_routes": require,
        "callable_count": len(callable_rows),
        "admission_eligible_count": len(admission_rows),
        "independent_route_count": len(independent),
        "independent_routes": independent,
        "independent_families": families,
        "failure_taxonomy": FAILURE_TAXONOMY_VERSION,
        "liability_ceiling": {
            "logical_provider_calls": PROVIDER_RUN["logical_calls"],
            "transport_requests": PROVIDER_RUN["requests"],
            "max_output_tokens": PROVIDER_RUN["logical_calls"] * PROBE_MAX_OUTPUT_TOKENS,
            "max_total_tokens": PROVIDER_RUN["tokens"],
            "internal_accounting_reservation_usd": PROVIDER_RUN["usd"],
            "vendor_liability_ceiling_usd": None,
            "usd_reservation_scope": "internal_ledger_not_vendor_liability_cap",
            "retry_accounting": "max_retries_zero_exactly_one_dispatch",
        },
        "typed_failure_counts": {
            category: sum(row.get("result_category") == category for row in rows)
            for category in sorted(
                {
                    str(row.get("result_category"))
                    for row in rows
                    if row.get("result_category") and row.get("result_category") != "success"
                }
            )
        },
        "failover_trace": [
            {
                "attempt": index,
                "provider": row.get("provider"),
                "transport_id": row.get("transport_id"),
                "model_id": row.get("model_id"),
                "result_category": row.get("result_category"),
                "selected": bool(row.get("callable")),
                "cooldown_seconds": row.get("cooldown_seconds", 0),
            }
            for index, row in enumerate(rows, start=1)
        ],
        "ok": ok,
        "failures": failures,
        "rows": rows,
        "policy": policy,
        "policy_digest": policy_digest,
        "receipt": None,
        "cached": False,
    }
    if live:
        verified_totals = [
            int((row.get("usage") or {}).get("total_tokens"))
            for row in rows
            if int(row.get("probe_calls") or 0) > 0
            and row.get("usage_verified")
            and isinstance((row.get("usage") or {}).get("total_tokens"), int)
        ]
        usage_rows = sum(int(row.get("probe_calls") or 0) > 0 for row in rows)
        verified_tokens = sum(verified_totals) if len(verified_totals) == usage_rows else None
        verified_requests = [
            row.get("transport_requests_verified")
            for row in rows
            if int(row.get("probe_calls") or 0) > 0
        ]
        requests = (
            sum(int(value) for value in verified_requests)
            if len(verified_requests) == usage_rows
            and all(type(value) is int and value >= 0 for value in verified_requests)
            else None
        )
        verified_usd = [
            row.get("provider_usd_verified")
            for row in rows
            if int(row.get("probe_calls") or 0) > 0
        ]
        usd = (
            round(sum(float(value) for value in verified_usd), 9)
            if len(verified_usd) == usage_rows
            and all(
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and math.isfinite(float(value))
                and float(value) >= 0
                for value in verified_usd
            )
            else None
        )
        budget_settlement = settle_budget(
            _receipt_root() / "provider_budget_ledger.jsonl",
            run_id=str(budget_reservation["run_id"]),
            reservation_digest=str(budget_reservation["ledger_digest"]),
            at=_now(),
            observed={
                "logical_calls": probe_call_count,
                "requests": requests,
                "tokens": verified_tokens,
                "usd": usd,
                "wall_seconds": max(0, math.ceil(time.monotonic() - budget_started)),
            },
            terminal_kind="provider_selftest",
        )
        payload["budget"] = {
            "reservation_digest": budget_reservation["ledger_digest"],
            "settlement_digest": budget_settlement["ledger_digest"],
            "charged": budget_settlement["charged"],
            "unverifiable_dimensions": budget_settlement["unverifiable_dimensions"],
            "overrun_dimensions": budget_settlement["overrun_dimensions"],
            "daily_cap_usd": PROVIDER_DAILY["usd"],
            "monthly_cap_usd": PROVIDER_MONTHLY["usd"],
            "usd_cap_scope": "internal_accounting_reservation_not_vendor_liability_cap",
            "accounting_valid": budget_settlement["accounting_valid"],
        }
        if not budget_settlement["accounting_valid"]:
            payload["ok"] = False
            payload["failures"].append(
                "provider_probe_budget_overrun"
                if budget_settlement["overrun_dimensions"]
                else "provider_probe_usage_unverifiable"
            )
        payload["receipt"] = str(_write_live_receipt(payload))
    return payload
