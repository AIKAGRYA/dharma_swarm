"""Live cycle — the first honest real signal: the army actually calls models.

Dry mode proves the loop runs; this proves it runs on real model output,
objectively scored. Every OpenAI-compatible route is pinned to one model and a
current conservative tariff binding; account-dependent "free" claims are not
trusted without operator evidence. Provider-reported usage or a precomputed
full-request liability flows into ``CampaignResult.spend_usd``.

Deliberately stdlib-only (``urllib``) so it deploys to a bare host with no pip
install and imports without the heavy stack. This is smoke-grade real signal —
an internal capability probe, not yet an external One Wire receipt. The harder
external targets (kernel/eval-harness benchmarks) need isolation and come next;
this is the honest first rung from rehearsal to real.
"""

from __future__ import annotations

import json
import math
import os
import re
import socket
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence

# OpenAI-compatible lanes, in preference order: (name, base_url, key_env,
# default_model). Order is failover preference, never a pricing assertion.
# Models are exact tariff-bound pins; no unreceipted /models request is made.
PROVIDERS: tuple[tuple[str, str, str, str], ...] = (
    ("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
    ("cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "llama-3.3-70b"),
    ("moonshot", "https://api.moonshot.ai/v1", "MOONSHOT_API_KEY", "moonshot-v1-8k"),
    ("zhipu", "https://api.z.ai/api/paas/v4", "ZHIPU_API_KEY", "glm-4.6"),
    ("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "meta-llama/llama-3.3-70b-instruct:free"),
    ("nvidia", "https://integrate.api.nvidia.com/v1", "NVIDIA_NIM_API_KEY", "meta/llama-3.3-70b-instruct"),
)

_BUILTIN_TARIFFS: dict[str, tuple[float, str, str, str]] = {
    "zhipu": (
        3.0,
        "official-pricing-upper-bound:glm-4.6-general-api:2026-08-27",
        "2026-08-27T00:00:00+00:00",
        "2026-09-03T00:00:00+00:00",
    ),
    "openrouter": (
        0.0,
        "pinned-model-tariff:openrouter-free-suffix:2026-08-27",
        "2026-08-27T00:00:00+00:00",
        "2026-09-03T00:00:00+00:00",
    ),
}
_ATTESTED_TARIFF_PROVIDERS = {
    "groq", "cerebras", "nvidia", "zhipu", "openrouter"
}
_EXCLUDED_ROUTES = {
    "moonshot": "model-retirement:moonshot-v1-8k:2026-08-31",
}
_TARIFF_PROVENANCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,255}")
_MAX_TARIFF_VALIDITY = timedelta(days=31)
_MAX_TARIFF_FUTURE_SKEW = timedelta(minutes=5)


@dataclass(frozen=True)
class TariffBinding:
    rate: float
    provenance: str
    checked_at: str
    valid_until: str


def _tariff_time(raw: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _configured_tariff(
    provider: str,
    source: dict | os._Environ[str],
    *,
    now: datetime | None = None,
) -> TariffBinding | None:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    prefix = f"FOUNDRY_{provider.upper()}"
    has_operator_binding = any(
        source.get(prefix + suffix)
        for suffix in (
            "_USD_PER_MTOK_UPPER_BOUND",
            "_TARIFF_PROVENANCE",
            "_TARIFF_CHECKED_AT",
            "_TARIFF_VALID_UNTIL",
        )
    )
    builtin = _BUILTIN_TARIFFS.get(provider)
    if builtin is not None and not has_operator_binding:
        rate, provenance, checked_raw, valid_raw = builtin
    else:
        if provider not in _ATTESTED_TARIFF_PROVIDERS:
            return None
        rate_raw = source.get(prefix + "_USD_PER_MTOK_UPPER_BOUND")
        provenance = str(source.get(prefix + "_TARIFF_PROVENANCE", ""))
        checked_raw = str(source.get(prefix + "_TARIFF_CHECKED_AT", ""))
        valid_raw = str(source.get(prefix + "_TARIFF_VALID_UNTIL", ""))
        try:
            rate = float(str(rate_raw))
        except (TypeError, ValueError):
            return None
    checked = _tariff_time(checked_raw)
    valid_until = _tariff_time(valid_raw)
    if (
        not math.isfinite(rate)
        or rate < 0
        or rate > 1000
        or not _TARIFF_PROVENANCE.fullmatch(provenance)
        or checked is None
        or valid_until is None
        or checked > now + _MAX_TARIFF_FUTURE_SKEW
        or not checked < valid_until
        or valid_until - checked > _MAX_TARIFF_VALIDITY
        or not now < valid_until
    ):
        return None
    return TariffBinding(rate, provenance, checked.isoformat(), valid_until.isoformat())


@dataclass(frozen=True)
class ProviderRoute:
    """One credential-bound OpenAI-compatible route (the key is never rendered)."""

    name: str
    base_url: str
    key: str = field(repr=False)
    default_model: str = ""
    tariff_usd_per_mtok_upper_bound: float = 0.0
    tariff_provenance: str = ""
    tariff_checked_at: str = ""
    tariff_valid_until: str = ""


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model: str
    content: str
    total_tokens: int
    attempts: tuple["ProviderAttempt", ...] = ()


@dataclass(frozen=True)
class ProviderAttempt:
    """Secret-free, budget-verifiable evidence for one outbound attempt."""

    provider: str
    model: str
    attempt: int
    category: str
    status_code: int | None
    tokens: int
    usage_basis: str
    retryable: bool
    backoff_seconds: float = 0.0
    prompt_bytes: int = 0
    liability_tokens: int = 0
    liability_cost_usd: float = 0.0
    route_base_url: str = ""
    tariff_usd_per_mtok_upper_bound: float | None = None
    tariff_provenance: str = ""
    tariff_checked_at: str = ""
    tariff_valid_until: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "attempt": self.attempt,
            "category": self.category,
            "status_code": self.status_code,
            "tokens": self.tokens,
            "usage_basis": self.usage_basis,
            "retryable": self.retryable,
            "backoff_seconds": self.backoff_seconds,
            "prompt_bytes": self.prompt_bytes,
            "liability_tokens": self.liability_tokens,
            "liability_cost_usd": self.liability_cost_usd,
            "route_base_url": self.route_base_url,
            "tariff_usd_per_mtok_upper_bound": (
                self.tariff_usd_per_mtok_upper_bound
            ),
            "tariff_provenance": self.tariff_provenance,
            "tariff_checked_at": self.tariff_checked_at,
            "tariff_valid_until": self.tariff_valid_until,
        }


class ProviderCallError(RuntimeError):
    """Typed, secret-free provider failure used by routing and receipts."""

    def __init__(
        self,
        provider: str,
        category: str,
        *,
        retryable: bool,
        status_code: int | None = None,
        billable_tokens: int = 0,
        usage_basis: str = "",
        usage_verified: bool = True,
    ) -> None:
        self.provider = provider
        self.category = category
        self.retryable = retryable
        self.status_code = status_code
        self.billable_tokens = max(0, int(billable_tokens))
        self.usage_basis = usage_basis
        self.usage_verified = bool(usage_verified)
        status = f" status={status_code}" if status_code is not None else ""
        super().__init__(f"provider={provider} category={category}{status}")


class ProviderExhausted(RuntimeError):
    """All configured routes failed or had an open circuit."""

    def __init__(self, failures: tuple[ProviderCallError, ...]) -> None:
        self.failures = failures
        summary = ", ".join(f"{f.provider}:{f.category}" for f in failures) or "no-route"
        super().__init__(f"provider routes exhausted ({summary})")

    @property
    def billable_tokens(self) -> int:
        return sum(f.billable_tokens for f in self.failures)


class ProviderUsageUnverifiable(RuntimeError):
    """A provider request occurred without actual or bounded usage evidence."""


_CHAT_FRAMING_TOKEN_ALLOWANCE = 1024
_MAX_PROMPT_BYTES = 2_000_000


def conservative_total_tokens(prompt: str, max_tokens: int) -> int:
    """Upper-bound one request's input framing plus permitted output.

    UTF-8 bytes conservatively dominate normal tokenizer input-token counts;
    an additional fixed allowance covers message framing and provider-specific
    special tokens.  This deliberately overcharges uncertain calls.
    """
    if not isinstance(prompt, str):
        raise ValueError("provider prompt must be text")
    prompt_bytes = len(prompt.encode("utf-8"))
    if prompt_bytes > _MAX_PROMPT_BYTES:
        raise ValueError("provider prompt exceeds the bounded request size")
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
        raise ValueError("provider max_tokens must be an integer")
    if max_tokens <= 0 or max_tokens > 131_072:
        raise ValueError("provider max_tokens is outside the bounded range")
    return prompt_bytes + _CHAT_FRAMING_TOKEN_ALLOWANCE + max_tokens


def _typed_provider_error(
    provider: str,
    exc: BaseException,
    *,
    conservative_tokens: int = 0,
) -> ProviderCallError:
    """Classify an exception without copying response bodies, URLs, or secrets."""
    if isinstance(exc, ProviderCallError):
        # Once a chat caller was invoked, a typed zero-token failure is not
        # proof of zero billing.  Upgrade it to the precomputed full request
        # liability unless the caller supplied explicit bounded usage.
        if conservative_tokens > 0 and exc.billable_tokens <= 0:
            return ProviderCallError(
                provider,
                exc.category,
                retryable=exc.retryable,
                status_code=exc.status_code,
                billable_tokens=conservative_tokens,
                usage_basis="conservative_total_liability",
                usage_verified=True,
            )
        if exc.billable_tokens > 0 and not exc.usage_basis:
            return ProviderCallError(
                provider,
                exc.category,
                retryable=exc.retryable,
                status_code=exc.status_code,
                billable_tokens=exc.billable_tokens,
                usage_basis="provider_reported_bounded",
                usage_verified=exc.usage_verified,
            )
        return exc
    if isinstance(exc, urllib.error.HTTPError):
        code = int(exc.code)
        if code in (401, 403):
            category, retryable = "authentication", False
        elif code == 402:
            category, retryable = "payment_required", False
        elif code == 429:
            category, retryable = "rate_limited", True
        elif code >= 500:
            category, retryable = "provider_unavailable", True
        else:
            category, retryable = "http_rejected", False
        # An HTTP response is post-dispatch. Authentication/payment/client
        # rejection is not provider-attested zero usage, so every status is
        # charged at the same full prompt+output liability.
        uncertain = conservative_tokens
        return ProviderCallError(
            provider,
            category,
            retryable=retryable,
            status_code=code,
            billable_tokens=uncertain,
            usage_basis="conservative_total_liability",
            usage_verified=conservative_tokens > 0,
        )
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return ProviderCallError(
            provider,
            "timeout",
            retryable=True,
            billable_tokens=conservative_tokens,
            usage_basis="conservative_total_liability",
            usage_verified=conservative_tokens > 0,
        )
    if isinstance(exc, (urllib.error.URLError, ConnectionError, OSError)):
        return ProviderCallError(
            provider,
            "network",
            retryable=True,
            billable_tokens=conservative_tokens,
            usage_basis="conservative_total_liability",
            usage_verified=conservative_tokens > 0,
        )
    if isinstance(exc, (KeyError, TypeError, ValueError, json.JSONDecodeError)):
        return ProviderCallError(
            provider,
            "invalid_response",
            retryable=False,
            billable_tokens=conservative_tokens,
            usage_basis="conservative_total_liability",
            usage_verified=conservative_tokens > 0,
        )
    return ProviderCallError(
        provider,
        "unexpected",
        retryable=False,
        billable_tokens=conservative_tokens,
        usage_basis="conservative_total_liability",
        usage_verified=conservative_tokens > 0,
    )


@dataclass
class _Circuit:
    failures: int = 0
    opened_at: float = 0.0
    retry_after_epoch: float = 0.0
    category: str = ""


class ProviderPool:
    """Bounded failover with a per-route circuit breaker.

    A failed route is opened after ``failure_threshold`` consecutive failures.
    It is retried only after ``cooldown_seconds``. Failed zero-token calls add
    exactly zero to ``total_tokens`` and therefore zero to spend accounting.
    """

    def __init__(
        self,
        *,
        env: dict | None = None,
        failure_threshold: int = 1,
        cooldown_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
        chat_caller: Callable[..., tuple[str, int]] | None = None,
        model_lister: Callable[[ProviderRoute], list[str]] | None = None,
        max_attempts_per_route: int = 2,
        backoff_base_seconds: float = 0.25,
        max_backoff_seconds: float = 2.0,
        sleeper: Callable[[float], None] = time.sleep,
        circuit_state_path: Path | None = None,
        wall_clock: Callable[[], float] = time.time,
        tariff_now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        budget_cap_usd: float | None = None,
    ) -> None:
        source = env if env is not None else os.environ
        tariff_observed_at = tariff_now()
        if tariff_observed_at.tzinfo is None:
            raise ValueError("tariff clock must be timezone-aware")
        routes: list[ProviderRoute] = []
        rejected_routes: list[dict[str, str]] = []
        for name, base, key_env, default_model in PROVIDERS:
            if not source.get(key_env):
                continue
            if name in _EXCLUDED_ROUTES:
                rejected_routes.append({
                    "provider": name,
                    "base_url": base,
                    "model": default_model,
                    "category": "route_retired",
                    "provenance": _EXCLUDED_ROUTES[name],
                })
                continue
            tariff = _configured_tariff(name, source, now=tariff_observed_at)
            if tariff is None:
                rejected_routes.append({
                    "provider": name,
                    "base_url": base,
                    "model": default_model,
                    "category": "tariff_unverified",
                    "provenance": "missing-stale-or-future-tariff-attestation",
                })
                continue
            routes.append(ProviderRoute(
                name,
                base,
                str(source[key_env]),
                default_model,
                tariff.rate,
                tariff.provenance,
                tariff.checked_at,
                tariff.valid_until,
            ))
        self.routes = tuple(routes)
        self.rejected_routes = tuple(rejected_routes)
        self.tariff_by_provider = {
            route.name: route.tariff_usd_per_mtok_upper_bound
            for route in self.routes
        }
        self.route_provenance = {
            route.name: {
                "base_url": route.base_url,
                "model": route.default_model,
                "tariff_usd_per_mtok_upper_bound": (
                    route.tariff_usd_per_mtok_upper_bound
                ),
                "tariff_provenance": route.tariff_provenance,
                "tariff_checked_at": route.tariff_checked_at,
                "tariff_valid_until": route.tariff_valid_until,
            }
            for route in self.routes
        }
        for rejected in self.rejected_routes:
            self.route_provenance[rejected["provider"]] = {
                "base_url": rejected["base_url"],
                "model": rejected["model"],
                "tariff_usd_per_mtok_upper_bound": None,
                "tariff_provenance": rejected["provenance"],
                "tariff_checked_at": "",
                "tariff_valid_until": "",
            }
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self.clock = clock
        self.chat_caller = chat_caller or self._call_route
        self.model_lister = model_lister or (
            lambda route: list_models(route.base_url, route.key)
        )
        self.circuits = {route.name: _Circuit() for route in self.routes}
        self.max_attempts_per_route = max(1, int(max_attempts_per_route))
        self.backoff_base_seconds = max(0.0, float(backoff_base_seconds))
        self.max_backoff_seconds = max(0.0, float(max_backoff_seconds))
        self.sleeper = sleeper
        self.circuit_state_path = (
            Path(circuit_state_path) if circuit_state_path is not None else None
        )
        self.wall_clock = wall_clock
        self.tariff_now = tariff_now
        if budget_cap_usd is not None and (
            isinstance(budget_cap_usd, bool)
            or not isinstance(budget_cap_usd, (int, float))
            or not math.isfinite(float(budget_cap_usd))
            or float(budget_cap_usd) < 0
        ):
            raise ValueError("provider budget cap must be finite and non-negative")
        self.budget_cap_usd = (
            None if budget_cap_usd is None else float(budget_cap_usd)
        )
        self.total_tokens = 0
        self.tokens_by_provider: dict[str, int] = {}
        self.successful_calls = 0
        self.total_attempts = 0
        self.attempt_history: list[ProviderAttempt] = []
        self.usage_verified = True
        self._load_circuits()

    def _load_circuits(self) -> None:
        if self.circuit_state_path is None:
            return
        try:
            payload = json.loads(self.circuit_state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError, TypeError) as exc:
            raise ProviderUsageUnverifiable("provider circuit state is unreadable") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != "foundry_provider_circuits.v1":
            raise ProviderUsageUnverifiable("provider circuit state schema is invalid")
        raw_routes = payload.get("routes")
        if not isinstance(raw_routes, dict):
            raise ProviderUsageUnverifiable("provider circuit routes are invalid")
        now = self.wall_clock()
        for name, raw in raw_routes.items():
            if name not in self.circuits or not isinstance(raw, dict):
                continue
            try:
                failures = int(raw.get("failures", 0))
                retry_after = float(raw.get("retry_after_epoch", 0.0))
            except (TypeError, ValueError) as exc:
                raise ProviderUsageUnverifiable("provider circuit numeric state invalid") from exc
            if failures < 0 or not (0.0 <= retry_after < float("inf")):
                raise ProviderUsageUnverifiable("provider circuit state is out of range")
            if retry_after > now:
                self.circuits[name] = _Circuit(
                    failures=max(self.failure_threshold, failures),
                    opened_at=self.clock(),
                    retry_after_epoch=retry_after,
                    category=str(raw.get("category", ""))[:80],
                )

    def _persist_circuits(self) -> None:
        if self.circuit_state_path is None:
            return
        path = self.circuit_state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "foundry_provider_circuits.v1",
            "routes": {
                name: {
                    "failures": circuit.failures,
                    "retry_after_epoch": circuit.retry_after_epoch,
                    "category": circuit.category,
                }
                for name, circuit in self.circuits.items()
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        encoded = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        temp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        try:
            with temp.open("xb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temp.unlink(missing_ok=True)

    def _record_failure(self, route: ProviderRoute, error: ProviderCallError) -> None:
        circuit = self.circuits[route.name]
        circuit.failures += 1
        circuit.opened_at = self.clock()
        circuit.retry_after_epoch = self.wall_clock() + self.cooldown_seconds
        circuit.category = error.category
        self._persist_circuits()

    def _reset_circuit(self, route: ProviderRoute) -> None:
        self.circuits[route.name] = _Circuit()
        self._persist_circuits()

    @staticmethod
    def _call_route(
        route: ProviderRoute,
        model: str,
        prompt: str,
        **kwargs,
    ) -> tuple[str, int]:
        return call_chat(
            route.base_url,
            route.key,
            model,
            prompt,
            provider=route.name,
            **kwargs,
        )

    def _is_open(self, route: ProviderRoute) -> bool:
        circuit = self.circuits[route.name]
        if circuit.failures < self.failure_threshold:
            return False
        if (
            self.wall_clock() >= circuit.retry_after_epoch
            and (self.clock() - circuit.opened_at) >= self.cooldown_seconds
        ):
            self._reset_circuit(route)
            return False
        return True

    def _charged_cost_usd(self) -> float:
        return sum(
            tokens * self.tariff_by_provider.get(
                provider, _UNKNOWN_LANE_USD_PER_MTOK
            ) / 1_000_000
            for provider, tokens in self.tokens_by_provider.items()
        )

    @staticmethod
    def _liability_cost_usd(route: ProviderRoute, tokens: int) -> float:
        return tokens * route.tariff_usd_per_mtok_upper_bound / 1_000_000

    @staticmethod
    def _route_attempt_fields(route: ProviderRoute) -> dict[str, object]:
        return {
            "route_base_url": route.base_url,
            "tariff_usd_per_mtok_upper_bound": (
                route.tariff_usd_per_mtok_upper_bound
            ),
            "tariff_provenance": route.tariff_provenance,
            "tariff_checked_at": route.tariff_checked_at,
            "tariff_valid_until": route.tariff_valid_until,
        }

    def call(
        self,
        prompt: str,
        *,
        model_hint: str = "",
        max_tokens: int = 64,
        temperature: float = 0.0,
        timeout: float = 45.0,
    ) -> ProviderResponse:
        liability_tokens = conservative_total_tokens(prompt, max_tokens)
        prompt_bytes = len(prompt.encode("utf-8"))
        if not isinstance(model_hint, str):
            raise ValueError("provider model hint must be text")
        if not math.isfinite(float(timeout)) or timeout <= 0 or timeout > 600:
            raise ValueError("provider timeout is outside the bounded range")
        if not math.isfinite(float(temperature)):
            raise ValueError("provider temperature must be finite")
        failures: list[ProviderCallError] = []
        call_attempts: list[ProviderAttempt] = []
        for rejected in self.rejected_routes:
            error = ProviderCallError(
                rejected["provider"], rejected["category"], retryable=False
            )
            failures.append(error)
            attempt = ProviderAttempt(
                provider=rejected["provider"],
                model=rejected["model"],
                attempt=0,
                category=error.category,
                status_code=None,
                tokens=0,
                usage_basis="no_request_route_policy",
                retryable=False,
                route_base_url=rejected["base_url"],
                tariff_usd_per_mtok_upper_bound=None,
                tariff_provenance=rejected["provenance"],
            )
            call_attempts.append(attempt)
            self.attempt_history.append(attempt)
        for route in self.routes:
            tariff_now = self.tariff_now()
            valid_until = _tariff_time(route.tariff_valid_until)
            if (
                tariff_now.tzinfo is None
                or valid_until is None
                or tariff_now.astimezone(timezone.utc) >= valid_until
            ):
                error = ProviderCallError(
                    route.name, "tariff_expired", retryable=False
                )
                failures.append(error)
                attempt = ProviderAttempt(
                    provider=route.name,
                    model=route.default_model,
                    attempt=0,
                    category=error.category,
                    status_code=None,
                    tokens=0,
                    usage_basis="no_request_tariff_expiry_guard",
                    retryable=False,
                    **self._route_attempt_fields(route),
                )
                call_attempts.append(attempt)
                self.attempt_history.append(attempt)
                continue
            if model_hint and model_hint != route.default_model:
                error = ProviderCallError(
                    route.name, "model_tariff_mismatch", retryable=False
                )
                failures.append(error)
                attempt = ProviderAttempt(
                    provider=route.name,
                    model=str(model_hint)[:200],
                    attempt=0,
                    category=error.category,
                    status_code=None,
                    tokens=0,
                    usage_basis="no_request_model_tariff_guard",
                    retryable=False,
                    **self._route_attempt_fields(route),
                )
                call_attempts.append(attempt)
                self.attempt_history.append(attempt)
                continue
            if self._is_open(route):
                error = ProviderCallError(route.name, "circuit_open", retryable=True)
                failures.append(error)
                attempt = ProviderAttempt(
                    provider=route.name,
                    model=route.default_model,
                    attempt=0,
                    category=error.category,
                    status_code=None,
                    tokens=0,
                    usage_basis="no_request_circuit_open",
                    retryable=True,
                    **self._route_attempt_fields(route),
                )
                call_attempts.append(attempt)
                self.attempt_history.append(attempt)
                continue
            try:
                model = route.default_model
                if not model:
                    raise ProviderCallError(
                        route.name, "no_usable_model", retryable=False
                    )
            except Exception as exc:  # noqa: BLE001 - classified, bounded failover
                error = _typed_provider_error(route.name, exc)
                failures.append(error)
                attempt = ProviderAttempt(
                    provider=route.name,
                    model=route.default_model,
                    attempt=0,
                    category=error.category,
                    status_code=error.status_code,
                    tokens=error.billable_tokens,
                    usage_basis="no_request_model_resolution",
                    retryable=error.retryable,
                    **self._route_attempt_fields(route),
                )
                call_attempts.append(attempt)
                self.attempt_history.append(attempt)
                self._record_failure(route, error)
                continue
            for attempt_number in range(1, self.max_attempts_per_route + 1):
                liability_cost = self._liability_cost_usd(route, liability_tokens)
                if (
                    self.budget_cap_usd is not None
                    and self._charged_cost_usd() + liability_cost
                    > self.budget_cap_usd + 1e-12
                ):
                    error = ProviderCallError(
                        route.name,
                        "budget_pre_dispatch",
                        retryable=False,
                        billable_tokens=0,
                        usage_basis="no_request_budget_guard",
                    )
                    failures.append(error)
                    attempt = ProviderAttempt(
                        provider=route.name,
                        model=model,
                        attempt=attempt_number,
                        category=error.category,
                        status_code=None,
                        tokens=0,
                        usage_basis=error.usage_basis,
                        retryable=False,
                        prompt_bytes=prompt_bytes,
                        liability_tokens=liability_tokens,
                        liability_cost_usd=round(liability_cost, 9),
                        **self._route_attempt_fields(route),
                    )
                    call_attempts.append(attempt)
                    self.attempt_history.append(attempt)
                    break
                self.total_attempts += 1
                try:
                    content, tokens = self.chat_caller(
                        route,
                        model,
                        prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=timeout,
                    )
                    if not isinstance(content, str):
                        raise ProviderCallError(
                            route.name,
                            "invalid_response",
                            retryable=False,
                            billable_tokens=liability_tokens,
                            usage_basis="conservative_total_liability",
                        )
                    safe_tokens = int(tokens)
                    if safe_tokens <= 0:
                        raise ProviderCallError(
                            route.name,
                            "usage_unverifiable",
                            retryable=False,
                            billable_tokens=liability_tokens,
                            usage_basis="conservative_total_liability",
                        )
                    if safe_tokens > liability_tokens:
                        raise ProviderCallError(
                            route.name,
                            "usage_exceeds_reserved_liability",
                            retryable=False,
                            billable_tokens=safe_tokens,
                            usage_basis="provider_usage_exceeded_reservation",
                            usage_verified=False,
                        )
                except Exception as exc:  # noqa: BLE001 - classified and bounded
                    error = _typed_provider_error(
                        route.name,
                        exc,
                        conservative_tokens=liability_tokens,
                    )
                    failures.append(error)
                    if not error.usage_verified:
                        self.usage_verified = False
                    self.total_tokens += error.billable_tokens
                    self.tokens_by_provider[route.name] = (
                        self.tokens_by_provider.get(route.name, 0)
                        + error.billable_tokens
                    )
                    will_retry = (
                        error.retryable
                        and attempt_number < self.max_attempts_per_route
                    )
                    backoff = 0.0
                    if will_retry:
                        backoff = min(
                            self.max_backoff_seconds,
                            self.backoff_base_seconds * (2 ** (attempt_number - 1)),
                        )
                    attempt = ProviderAttempt(
                        provider=route.name,
                        model=model,
                        attempt=attempt_number,
                        category=error.category,
                        status_code=error.status_code,
                        tokens=error.billable_tokens,
                        usage_basis=(
                            error.usage_basis
                            or (
                                "provider_reported"
                                if error.billable_tokens
                                and isinstance(exc, ProviderCallError)
                                else (
                                    "conservative_total_liability"
                                    if error.billable_tokens
                                    else "verified_zero_pre_rejection"
                                )
                            )
                        ),
                        retryable=error.retryable,
                        backoff_seconds=round(backoff, 6),
                        prompt_bytes=prompt_bytes,
                        liability_tokens=liability_tokens,
                        liability_cost_usd=round(liability_cost, 9),
                        **self._route_attempt_fields(route),
                    )
                    call_attempts.append(attempt)
                    self.attempt_history.append(attempt)
                    if will_retry:
                        if backoff:
                            self.sleeper(backoff)
                        continue
                    self._record_failure(route, error)
                    break

                self._reset_circuit(route)
                self.total_tokens += safe_tokens
                self.tokens_by_provider[route.name] = (
                    self.tokens_by_provider.get(route.name, 0) + safe_tokens
                )
                self.successful_calls += 1
                attempt = ProviderAttempt(
                    provider=route.name,
                    model=model,
                    attempt=attempt_number,
                    category="ok",
                    status_code=200,
                    tokens=safe_tokens,
                    usage_basis="provider_usage_total_tokens",
                    retryable=False,
                    prompt_bytes=prompt_bytes,
                    liability_tokens=liability_tokens,
                    liability_cost_usd=round(liability_cost, 9),
                    **self._route_attempt_fields(route),
                )
                call_attempts.append(attempt)
                self.attempt_history.append(attempt)
                return ProviderResponse(
                    route.name, model, content, safe_tokens, tuple(call_attempts)
                )
        raise ProviderExhausted(tuple(failures))


@dataclass(frozen=True)
class Task:
    prompt: str
    answer: str  # normalized (alnum, lowercase) expected answer


# A tiny frozen, deterministic benchmark. Reality owns the answers; the model
# must actually compute/know them — it cannot grade itself. Versioned by content.
FROZEN_TASKS: tuple[Task, ...] = (
    Task("Reply with ONLY the integer result and nothing else: 17 * 23", "391"),
    Task("Reply with ONLY the integer and nothing else, the value printed by: print(sum(range(10)))", "45"),
    Task("Reply with ONLY one lowercase word and no punctuation: the capital city of Japan", "tokyo"),
    Task("Reply with ONLY the integer number of bits in one byte and nothing else", "8"),
    Task("Reply with ONLY the integer and nothing else: the length of the string 'dharma'", "6"),
)
BENCHMARK_ID = "foundry_live_frozen_v1"


def _norm(text: str) -> str:
    return "".join(ch for ch in text.strip().lower() if ch.isalnum())


# Built-in upper bounds in USD per 1M tokens. Account-dependent lanes are
# intentionally absent: they are admitted only through an operator-provided
# upper-bound and provenance attestation parsed by ``_configured_tariff``.
UPPER_BOUND_USD_PER_MTOK: dict[str, float] = {
    "openrouter": 0.0,
    "moonshot": 3.0,
    "zhipu": 3.0,
}
_UNKNOWN_LANE_USD_PER_MTOK = 5.0


def estimate_cost_usd(
    provider: str,
    total_tokens: int,
    *,
    rate_upper_bound: float | None = None,
) -> float:
    rate = (
        UPPER_BOUND_USD_PER_MTOK.get(provider, _UNKNOWN_LANE_USD_PER_MTOK)
        if rate_upper_bound is None else float(rate_upper_bound)
    )
    if not math.isfinite(rate) or rate < 0:
        raise ValueError("provider tariff must be finite and non-negative")
    return round(total_tokens * rate / 1_000_000, 6)


def pick_provider(env: dict | None = None) -> tuple[str, str, str, str] | None:
    """First lane whose key is present in the environment.

    Returns (name, base_url, key, default_model).
    """
    env = env if env is not None else os.environ
    for name, base, key_env, default_model in PROVIDERS:
        key = env.get(key_env)
        if key and _configured_tariff(name, env) is not None:
            return name, base, key, default_model
    return None


def _http_json(url: str, key: str, *, payload: dict | None = None,
               method: str = "GET", timeout: float = 45.0) -> dict:
    if not url.startswith("https://"):
        raise ValueError(f"Only HTTPS URLs are permitted; got: {url!r}")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted provider URLs)
        return json.loads(resp.read().decode("utf-8"))


def list_models(base_url: str, key: str, *, timeout: float = 30.0) -> list[str]:
    try:
        data = _http_json(f"{base_url}/models", key, timeout=timeout)
        return [m.get("id") for m in data.get("data", []) if m.get("id")]
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return []


def choose_model(models: Sequence[str]) -> str:
    """Pick a small, general chat model; skip non-chat (whisper/embed/tts/guard)."""
    # Prefer stable, non-thinking chat models that answer a short prompt cleanly.
    prefs = ("moonshot-v1-8k", "llama-3.3-70b", "llama-3.3", "gpt-oss-120b", "glm-4-flash",
             "glm-4", "qwen", "moonshot-v1", "kimi-k2.5", "kimi-k2", "llama-3.1-8b",
             "llama3.1-8b", "llama")
    chat = [m for m in models if not any(
        bad in m.lower() for bad in
        ("whisper", "embed", "tts", "guard", "vision", "rerank", "code", "highspeed", "auto")
    )]
    for pref in prefs:
        for m in chat:
            if pref in m.lower():
                return m
    return chat[0] if chat else (models[0] if models else "")


def call_chat(base_url: str, key: str, model: str, prompt: str, *,
              timeout: float = 45.0, max_tokens: int = 64,
              temperature: float = 0.0, provider: str = "unknown") -> tuple[str, int]:
    """Returns (content, total_tokens) — token count straight from the API's usage block.

    The tiny default ``max_tokens`` fits the frozen heartbeat benchmark;
    mutation proposals (unified diffs) pass a much larger budget.
    """
    liability_tokens = conservative_total_tokens(prompt, max_tokens)
    try:
        data = _http_json(
            f"{base_url}/chat/completions", key,
            payload={
                "model": model, "temperature": temperature, "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            method="POST", timeout=timeout,
        )
        content = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage")
        if not isinstance(usage, dict) or "total_tokens" not in usage:
            raise ProviderCallError(
                provider,
                "usage_unverifiable",
                retryable=False,
                billable_tokens=liability_tokens,
                usage_basis="conservative_total_liability",
            )
        tokens = int(usage["total_tokens"])
        if tokens <= 0:
            raise ProviderCallError(
                provider,
                "usage_unverifiable",
                retryable=False,
                billable_tokens=liability_tokens,
                usage_basis="conservative_total_liability",
            )
        return content, tokens
    except Exception as exc:  # noqa: BLE001 - converted to secret-free typed failure
        raise _typed_provider_error(
            provider, exc, conservative_tokens=liability_tokens
        ) from exc


@dataclass
class LiveResult:
    provider: str
    model: str
    tasks: int
    correct: int
    accuracy: float
    per_task: list = field(default_factory=list)
    error: str = ""
    ran_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_tokens: int = 0
    est_cost_usd: float = 0.0
    tokens_by_provider: dict[str, int] = field(default_factory=dict)
    provider_failures: int = 0
    provider_calls: int = 0
    provider_attempts: list[dict[str, object]] = field(default_factory=list)
    provider_route_provenance: dict[str, dict[str, object]] = field(default_factory=dict)
    usage_verified: bool = True


def run_live_eval(
    *,
    env: dict | None = None,
    model: str | None = None,
    caller: Callable[[str, str], str] | None = None,
    model_lister: Callable[[], list[str]] | None = None,
    budget_cap_usd: float | None = None,
) -> LiveResult:
    """Run the frozen benchmark against a real free-lane model. Injectable for tests."""
    env = env if env is not None else os.environ
    picked = pick_provider(env)
    if picked is None:
        return LiveResult("none", "none", 0, 0, 0.0, error="no provider key present")
    name, base, key, default_model = picked
    picked_tariff = _configured_tariff(name, env)
    assert picked_tariff is not None
    lister = model_lister or (lambda: list_models(base, key))
    usage_tokens: list[int] = []

    pool = (
        ProviderPool(env=env, budget_cap_usd=budget_cap_usd)
        if caller is None else None
    )
    routed: list[tuple[str, str]] = []

    def _default_call(m: str, p: str) -> str:
        assert pool is not None
        response = pool.call(p, model_hint=m)
        usage_tokens.append(response.total_tokens)
        routed.append((response.provider, response.model))
        return response.content

    call = caller or _default_call

    if model is None:
        # The provider pool must resolve a model independently per route; a
        # Moonshot model name is not valid evidence that Zhipu can serve it.
        model = "" if caller is None and model_lister is None else (
            choose_model(lister()) or default_model
        )
        if caller is not None and not model:
            return LiveResult(name, "none", 0, 0, 0.0, error="no usable chat model listed")

    correct = 0
    provider_failures = 0
    per: list = []
    for task in FROZEN_TASKS:
        try:
            resp = call(model, task.prompt)
            ok = _norm(resp) == task.answer or task.answer in _norm(resp)
        except Exception as exc:  # noqa: BLE001 - typed miss evidence, not a crash
            if isinstance(exc, ProviderExhausted):
                provider_failures += 1
            per.append({"prompt": task.prompt, "ok": False, "error": type(exc).__name__})
            continue
        correct += 1 if ok else 0
        per.append({"prompt": task.prompt, "ok": ok})
    n = len(FROZEN_TASKS)
    provider_tokens = (
        dict(pool.tokens_by_provider)
        if pool is not None
        else ({name: sum(usage_tokens)} if usage_tokens else {})
    )
    tokens = sum(provider_tokens.values())
    cost = round(sum(
        estimate_cost_usd(
            provider,
            count,
            rate_upper_bound=(
                pool.tariff_by_provider[provider]
                if pool is not None
                else picked_tariff.rate
            ),
        )
        for provider, count in provider_tokens.items()
    ), 6)
    if routed:
        name, model = routed[-1]
    return LiveResult(
        name, model, n, correct, (correct / n) if n else 0.0, per,
        total_tokens=tokens, est_cost_usd=cost, tokens_by_provider=provider_tokens,
        provider_failures=provider_failures,
        provider_calls=(pool.total_attempts if pool is not None else len(per)),
        provider_attempts=(
            [attempt.to_dict() for attempt in pool.attempt_history]
            if pool is not None else []
        ),
        provider_route_provenance=(
            dict(pool.route_provenance)
            if pool is not None else {
                name: {
                    "base_url": base,
                    "model": model,
                    "tariff_usd_per_mtok_upper_bound": (
                        picked_tariff.rate
                    ),
                    "tariff_provenance": picked_tariff.provenance,
                    "tariff_checked_at": picked_tariff.checked_at,
                    "tariff_valid_until": picked_tariff.valid_until,
                }
            }
        ),
        usage_verified=(pool is not None and pool.usage_verified),
    )


def _latest_receipt(root: Path) -> Path | None:
    records = _live_records(root)
    return records[-1][0] if records else None


def _live_records(root: Path) -> list[tuple[Path, dict]]:
    records: list[tuple[Path, dict]] = []
    for path in sorted(root.glob(f"{BENCHMARK_ID}_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            data = {}
        records.append((path, data))
    legacy = [item for item in records if int(item[1].get("sequence", 0) or 0) <= 0]
    chained = [item for item in records if int(item[1].get("sequence", 0) or 0) > 0]
    chained.sort(key=lambda item: int(item[1]["sequence"]))
    return legacy + chained


def _chain_prev_digest(root: Path) -> str:
    """Digest of the newest existing receipt, or the genesis marker.

    Each receipt embeds its predecessor's digest, forming a hash chain:
    rewriting any historical receipt breaks every digest after it. This is
    tamper-EVIDENT, not tamper-proof (see the honest gap note in
    docs/foundry/ — local disk is still rewritable wholesale; ring 3 anchors
    in venues we don't control remain the strongest link).
    """
    records = _live_records(root)
    if not records:
        return "genesis"
    return str(records[-1][1].get("digest", "genesis"))


def write_live_receipt(result: LiveResult, *, state_root: Path) -> Path:
    from dharma_swarm.foundry.evaluator import canonical_digest
    from dharma_swarm.foundry.receipts import ReceiptChainError, _chain_lock

    root = Path(state_root) / "live_eval"
    root.mkdir(parents=True, exist_ok=True)
    with _chain_lock(root):
        ok, detail = verify_live_chain(Path(state_root))
        if not ok:
            raise ReceiptChainError(f"refusing to append live receipt: {detail}")
        records = _live_records(root)
        sequences = [int(data.get("sequence", 0) or 0) for _, data in records]
        sequence = max(sequences, default=0) + 1
        stamp = result.ran_at.replace(":", "").replace("-", "")[:15]
        payload = {
            "benchmark": BENCHMARK_ID,
            "sequence": sequence,
            "provider": result.provider,
            "model": result.model,
            "tasks": result.tasks,
            "correct": result.correct,
            "accuracy": result.accuracy,
            "per_task": result.per_task,
            "error": result.error,
            "ran_at": result.ran_at,
            "total_tokens": result.total_tokens,
            "est_cost_usd_upper_bound": result.est_cost_usd,
            "tokens_by_provider": result.tokens_by_provider,
            "provider_calls": result.provider_calls,
            "provider_attempts": result.provider_attempts,
            "provider_route_provenance": result.provider_route_provenance,
            "usage_verified": result.usage_verified,
            "prev_digest": _chain_prev_digest(root),
        }
        payload["digest"] = canonical_digest(payload)
        short = payload["digest"].removeprefix("sha256:")[:16]
        path = root / f"{BENCHMARK_ID}_{sequence:08d}__{stamp}__{short}.json"
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        directory = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return path


def verify_live_chain(state_root: Path) -> tuple[bool, str]:
    """Walk the live-receipt chain; return (ok, detail).

    Recomputes every digest and checks each ``prev_digest`` pointer. Any
    rewritten or deleted-in-the-middle receipt surfaces as a break.
    """
    from dharma_swarm.foundry.evaluator import canonical_digest

    root = Path(state_root) / "live_eval"
    receipts = _live_records(root)
    expected_prev = "genesis"
    expected_sequence = 1
    for path, data in receipts:
        if not data:
            return False, f"unreadable receipt at {path.name}"
        claimed = data.get("digest", "")
        if "prev_digest" not in data:
            # Pre-chain receipt (before this feature): treat as chain genesis.
            expected_prev = claimed or "genesis"
            continue
        sequence = int(data.get("sequence", 0) or 0)
        if sequence > 0:
            if sequence != expected_sequence:
                return False, (
                    f"chain break at {path.name}: sequence "
                    f"expected={expected_sequence} actual={sequence}"
                )
            expected_sequence += 1
        if data["prev_digest"] != expected_prev:
            return False, f"chain break at {path.name}: prev_digest mismatch"
        body = {k: v for k, v in data.items() if k != "digest"}
        if canonical_digest(body) != claimed:
            return False, f"tampered receipt at {path.name}: digest mismatch"
        expected_prev = claimed
    return True, f"chain intact over {len(receipts)} receipts"


def live_daemon_cycle(target_id: str, generations: int, budget_cap: float,
                      state_root: "Path | None"):
    """Daemon cycle that runs the live eval and maps it to a CampaignResult.

    ``mean_survival`` carries the model's accuracy so the standing kill-metrics
    treat an accuracy collapse as a real survival_collapse signal.
    ``spend_usd`` carries the metered upper-bound cost so the daemon's budget
    guard accounts for paid lanes honestly (free lanes stay $0).
    """
    from dharma_swarm.foundry.campaign import CampaignResult

    result = run_live_eval(budget_cap_usd=budget_cap)
    if not result.usage_verified:
        raise ProviderUsageUnverifiable(
            "live evaluation usage was not provider-reported or conservatively bounded"
        )
    sr = Path(state_root) if state_root is not None else Path.cwd()
    if not result.error:
        write_live_receipt(result, state_root=sr)
    return CampaignResult(
        target_id=f"live:{result.provider}:{result.model}",
        generations_run=1,
        proposed=max(0, result.tasks - result.provider_failures),
        provider_failures=result.provider_failures,
        ring1_wins=result.correct,
        ring2_checked=result.tasks,
        ring2_survivors=result.correct,
        best_fitness=result.accuracy,
        mean_survival=result.accuracy,
        spend_usd=result.est_cost_usd,
    )
