"""Hermetic routing decision matrix for model-router hardening.

The matrix exercises policy selection and runtime fallback behavior with fake
providers only. It is safe to run in CI and does not read keys or call models.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, AsyncIterator, Iterator

from dharma_swarm.decision_router import RoutePath
from dharma_swarm.model_hierarchy import DEFAULT_MODELS
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.provider_policy import (
    ProviderPolicyRouter,
    ProviderRouteDecision,
    ProviderRouteRequest,
    ProviderRoutingConfig,
)
from dharma_swarm.providers import ModelRouter
from dharma_swarm.resilience import RetryPolicy

ROUTING_DECISION_MATRIX_SCHEMA_VERSION = "dharma.routing_decision_matrix.v1"


@dataclass(frozen=True, slots=True)
class PolicyScenario:
    name: str
    request: ProviderRouteRequest
    available_providers: tuple[ProviderType, ...]
    expected_path: RoutePath
    expected_provider: ProviderType
    expected_reason_fragments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionScenario:
    name: str
    pinned_chain: tuple[ProviderType, ...]
    provider_outputs: dict[ProviderType, str]
    expected_provider: ProviderType
    expected_content: str
    expected_open_breakers: tuple[ProviderType, ...] = ()
    key_liveness: set[str] | None = None


class _MatrixProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            content=self.content,
            model=request.model,
            provider="matrix",
            usage={"total_tokens": len(self.content.split())},
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        yield self.content


@contextmanager
def _temporary_env(updates: dict[str, str]) -> Iterator[None]:
    previous: dict[str, str | None] = {}
    for key, value in updates.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _base_request(**overrides: Any) -> ProviderRouteRequest:
    payload: dict[str, Any] = {
        "action_name": "matrix_probe",
        "risk_score": 0.08,
        "uncertainty": 0.10,
        "novelty": 0.12,
        "urgency": 0.4,
        "expected_impact": 0.2,
        "estimated_latency_ms": 200,
        "estimated_tokens": 300,
        "preferred_low_cost": True,
        "context": {},
    }
    payload.update(overrides)
    return ProviderRouteRequest(**payload)


def _policy_scenarios() -> tuple[PolicyScenario, ...]:
    return (
        PolicyScenario(
            name="reflex_low_cost_prefers_free_lane",
            request=_base_request(action_name="summarize_logs"),
            available_providers=(
                ProviderType.OPENROUTER_FREE,
                ProviderType.ANTHROPIC,
                ProviderType.CODEX,
            ),
            expected_path=RoutePath.REFLEX,
            expected_provider=ProviderType.OPENROUTER_FREE,
        ),
        PolicyScenario(
            name="frontier_precision_forces_escalation",
            request=_base_request(
                action_name="security_hotfix",
                risk_score=0.30,
                uncertainty=0.25,
                novelty=0.20,
                urgency=0.95,
                expected_impact=0.92,
                requires_frontier_precision=True,
                privileged_action=True,
                requires_human_consent=True,
            ),
            available_providers=(
                ProviderType.OPENROUTER_FREE,
                ProviderType.ANTHROPIC,
                ProviderType.OPENAI,
            ),
            expected_path=RoutePath.ESCALATE,
            expected_provider=ProviderType.ANTHROPIC,
            expected_reason_fragments=("frontier_precision_requested",),
        ),
        PolicyScenario(
            name="tooling_context_prefers_tooling_lane",
            request=_base_request(
                action_name="apply_patch",
                risk_score=0.35,
                uncertainty=0.30,
                novelty=0.25,
                urgency=0.6,
                expected_impact=0.4,
                context={"requires_tooling": True},
            ),
            available_providers=(
                ProviderType.CLAUDE_CODE,
                ProviderType.CODEX,
                ProviderType.OPENROUTER,
            ),
            expected_path=RoutePath.DELIBERATIVE,
            expected_provider=ProviderType.CLAUDE_CODE,
        ),
        PolicyScenario(
            name="reasoning_context_prefers_delegated_research",
            request=_base_request(
                action_name="architecture_scout",
                risk_score=0.34,
                uncertainty=0.46,
                novelty=0.44,
                urgency=0.58,
                expected_impact=0.48,
                preferred_low_cost=False,
                context={
                    "complexity_tier": "REASONING",
                    "last_user_message": "Compare alternatives carefully.",
                },
            ),
            available_providers=(
                ProviderType.OPENROUTER,
                ProviderType.OLLAMA,
                ProviderType.ANTHROPIC,
                ProviderType.CODEX,
            ),
            expected_path=RoutePath.DELIBERATIVE,
            expected_provider=ProviderType.OPENROUTER,
        ),
    )


def _execution_scenarios() -> tuple[ExecutionScenario, ...]:
    long_quota_error = json.dumps(
        {
            "error": {
                "message": "You exceeded your current quota, please check your plan.",
                "details": "x" * 700,
            }
        }
    )
    return (
        ExecutionScenario(
            name="empty_response_falls_through",
            pinned_chain=(ProviderType.OPENAI, ProviderType.OPENROUTER),
            provider_outputs={
                ProviderType.OPENAI: "",
                ProviderType.OPENROUTER: "healthy completion",
            },
            expected_provider=ProviderType.OPENROUTER,
            expected_content="healthy completion",
        ),
        ExecutionScenario(
            name="rate_limit_falls_through_without_fast_trip",
            pinned_chain=(ProviderType.OPENAI, ProviderType.OPENROUTER),
            provider_outputs={
                ProviderType.OPENAI: "rate_limit_exceeded: retry shortly",
                ProviderType.OPENROUTER: "healthy completion",
            },
            expected_provider=ProviderType.OPENROUTER,
            expected_content="healthy completion",
        ),
        ExecutionScenario(
            name="long_structured_quota_fast_trips",
            pinned_chain=(ProviderType.OPENAI, ProviderType.OPENROUTER),
            provider_outputs={
                ProviderType.OPENAI: long_quota_error,
                ProviderType.OPENROUTER: "healthy completion",
            },
            expected_provider=ProviderType.OPENROUTER,
            expected_content="healthy completion",
            expected_open_breakers=(ProviderType.OPENAI,),
        ),
        ExecutionScenario(
            name="key_liveness_prunes_dead_primary",
            pinned_chain=(ProviderType.OPENAI, ProviderType.OPENROUTER),
            provider_outputs={
                ProviderType.OPENAI: "dead key lane should not be called",
                ProviderType.OPENROUTER: "healthy completion",
            },
            expected_provider=ProviderType.OPENROUTER,
            expected_content="healthy completion",
            key_liveness={ProviderType.OPENROUTER.value},
        ),
    )


def _request_for_execution(name: str) -> ProviderRouteRequest:
    return ProviderRouteRequest(
        action_name=name,
        risk_score=0.1,
        uncertainty=0.1,
        novelty=0.1,
        urgency=0.4,
        expected_impact=0.2,
        estimated_latency_ms=200,
        estimated_tokens=300,
        context={
            "session_id": f"routing-matrix-{name}",
            "task_id": name,
            "run_id": name,
        },
    )


def _llm_request() -> LLMRequest:
    return LLMRequest(
        model=DEFAULT_MODELS[ProviderType.OPENAI],
        messages=[{"role": "user", "content": "Return a short completion."}],
        max_tokens=64,
        temperature=0.0,
    )


def _pin_chain(router: ModelRouter, scenario: ExecutionScenario) -> None:
    decision = ProviderRouteDecision(
        path=RoutePath.REFLEX,
        selected_provider=scenario.pinned_chain[0],
        selected_model_hint=None,
        fallback_providers=list(scenario.pinned_chain[1:]),
        fallback_model_hints=[],
        confidence=1.0,
        requires_human=False,
        reasons=["routing_decision_matrix_pinned_chain"],
    )
    router.route_request = lambda *args, **kwargs: decision  # type: ignore[method-assign]


def _policy_case_to_dict(scenario: PolicyScenario, decision: Any) -> dict[str, Any]:
    reasons = list(decision.reasons)
    checks = {
        "path": decision.path == scenario.expected_path,
        "selected_provider": decision.selected_provider == scenario.expected_provider,
        "reason_fragments": all(
            any(fragment in reason for reason in reasons)
            for fragment in scenario.expected_reason_fragments
        ),
    }
    return {
        "name": scenario.name,
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "expected": {
            "path": scenario.expected_path.value,
            "selected_provider": scenario.expected_provider.value,
            "reason_fragments": list(scenario.expected_reason_fragments),
        },
        "observed": {
            "path": decision.path.value,
            "selected_provider": decision.selected_provider.value,
            "selected_model_hint": decision.selected_model_hint,
            "fallback_providers": [item.value for item in decision.fallback_providers],
            "reasons": reasons,
        },
    }


async def _run_execution_case(
    scenario: ExecutionScenario,
    *,
    tmp_dir: Path,
) -> dict[str, Any]:
    providers = {
        provider: _MatrixProvider(content)
        for provider, content in scenario.provider_outputs.items()
    }

    def _key_liveness() -> set[str] | None:
        return scenario.key_liveness

    router = ModelRouter(
        providers,
        retry_policy=RetryPolicy(max_attempts=1, base_delay_seconds=0.0, jitter_seconds=0.0),
        routing_audit_path=tmp_dir / f"{scenario.name}.routing.jsonl",
        key_liveness_provider=_key_liveness,
    )
    _pin_chain(router, scenario)
    decision, response = await router.complete_for_task(
        _request_for_execution(scenario.name),
        _llm_request(),
        available_provider_types=list(scenario.pinned_chain),
    )
    breaker_states = {
        lane: router._breaker_registry.get(lane).state.value
        for lane in router._breaker_registry.snapshot_all()
    }
    calls = {provider.value: fake.calls for provider, fake in providers.items()}
    open_breakers = {
        lane.split(":", 1)[0]
        for lane, state in breaker_states.items()
        if state == "open"
    }
    expected_open = {provider.value for provider in scenario.expected_open_breakers}
    checks = {
        "selected_provider": decision.selected_provider == scenario.expected_provider,
        "response_content": response.content == scenario.expected_content,
        "open_breakers": expected_open.issubset(open_breakers),
        "dead_key_primary_not_called": (
            calls.get(scenario.pinned_chain[0].value, 0) == 0
            if scenario.key_liveness is not None
            else True
        ),
    }
    return {
        "name": scenario.name,
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "expected": {
            "selected_provider": scenario.expected_provider.value,
            "response_content": scenario.expected_content,
            "open_breaker_providers": sorted(expected_open),
            "key_liveness": sorted(scenario.key_liveness) if scenario.key_liveness is not None else None,
        },
        "observed": {
            "selected_provider": decision.selected_provider.value,
            "selected_model_hint": decision.selected_model_hint,
            "response_content": response.content,
            "calls": calls,
            "breaker_states": breaker_states,
            "reasons": list(decision.reasons),
        },
    }


async def _run_execution_cases(tmp_dir: Path) -> list[dict[str, Any]]:
    return [
        await _run_execution_case(scenario, tmp_dir=tmp_dir)
        for scenario in _execution_scenarios()
    ]


def build_routing_decision_matrix() -> dict[str, Any]:
    """Build a deterministic matrix receipt without external model calls."""
    generated_at = datetime.now(timezone.utc).isoformat()
    env_updates = {
        "DGC_SMART_ROUTER_ENABLED": "0",
        "DGC_ROUTER_TELEMETRY_ENABLE": "0",
        "DGC_ROUTER_AUDIT_DISABLE": "1",
        "DGC_ROUTER_RETROSPECTIVE_DISABLE": "1",
    }
    with _temporary_env(env_updates):
        router = ProviderPolicyRouter(
            config=ProviderRoutingConfig(telemetry_optimization_enabled=False)
        )
        policy_cases = [
            _policy_case_to_dict(
                scenario,
                router.route(
                    scenario.request,
                    available_providers=list(scenario.available_providers),
                ),
            )
            for scenario in _policy_scenarios()
        ]
        with tempfile.TemporaryDirectory(prefix="dharma-routing-matrix-") as tmp:
            execution_cases = asyncio.run(_run_execution_cases(Path(tmp)))

    cases = policy_cases + execution_cases
    counts = {
        "policy_cases": len(policy_cases),
        "execution_cases": len(execution_cases),
        "passed": sum(1 for case in cases if case["status"] == "passed"),
        "failed": sum(1 for case in cases if case["status"] != "passed"),
    }
    return {
        "schema_version": ROUTING_DECISION_MATRIX_SCHEMA_VERSION,
        "generated_at": generated_at,
        "live_calls_attempted": 0,
        "hermetic": True,
        "status": "passed" if counts["failed"] == 0 else "failed",
        "counts": counts,
        "policy_cases": policy_cases,
        "execution_cases": execution_cases,
    }


def write_routing_decision_matrix(path: str | Path) -> dict[str, Any]:
    payload = build_routing_decision_matrix()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
