"""Failure-class separation: rate-limit vs quota vs billing vs circuit.

Loop-closure campaign Phase 1a (track loop-closure-2026-06, dossier §3.3):
the three failure state classes are orthogonal — a quota exhaustion is not
a circuit failure, and a rate limit is neither. rate_limited must never
fast-trip a breaker; quota/billing/access must.
"""

from __future__ import annotations

import pytest

from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.provider_policy import (
    ProviderRouteDecision,
    ProviderRouteRequest,
    RoutePath,
)
from dharma_swarm.provider_smoke import _classify_error
from dharma_swarm.providers import ModelRouter
from dharma_swarm.resilience import CircuitState


class _ContentProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        return LLMResponse(content=self.content, model=request.model, usage={})

    async def stream(self, request: LLMRequest):
        yield self.content


def _fail_open_key_liveness() -> set[str] | None:
    return None


def _route_request(task_id: str) -> ProviderRouteRequest:
    return ProviderRouteRequest(
        action_name="summarize_notes",
        risk_score=0.1,
        uncertainty=0.1,
        novelty=0.1,
        urgency=0.4,
        expected_impact=0.2,
        estimated_latency_ms=200,
        estimated_tokens=300,
        context={"session_id": "sess-fc", "task_id": task_id, "run_id": task_id},
    )


def _llm_request() -> LLMRequest:
    return LLMRequest(
        model="gpt-4o",
        messages=[{"role": "user", "content": "hello"}],
    )


def _pin_chain(router: ModelRouter, first: ProviderType, second: ProviderType) -> None:
    decision = ProviderRouteDecision(
        path=RoutePath.REFLEX,
        selected_provider=first,
        selected_model_hint=None,
        fallback_providers=[second],
        fallback_model_hints=[],
        confidence=1.0,
        requires_human=False,
        reasons=["test_pinned_chain"],
    )
    router.route_request = lambda *args, **kwargs: decision  # type: ignore[method-assign]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("rate_limit_exceeded: slow down", "rate_limited"),
        ("HTTP 429 Too Many Requests", "rate_limited"),
        ("Rate limit reached for requests", "rate_limited"),
        ("insufficient_quota", "quota_exhausted"),
        ("You exceeded your current quota, please check your plan", "quota_exhausted"),
        ("Your credit balance is too low", "billing_exhausted"),
        ("billing hard limit reached", "billing_exhausted"),
        ("Your API key has been disabled", "billing_exhausted"),
        ("403 Forbidden", "access_denied"),
        ("timeout: upstream", "provider_timeout"),
        ("error: upstream broke", "provider_error"),
        ("ERROR(rc=1): subprocess failed", "provider_error"),
        ("", "empty_response"),
        ("a normal completion answer", None),
    ],
)
def test_response_failure_classes_are_separated(body: str, expected: str | None) -> None:
    response = LLMResponse(content=body, model="m", usage={})
    assert ModelRouter._response_indicates_failure(response) == expected


def test_long_structured_error_body_keeps_specific_failure_class() -> None:
    body = (
        '{"error":{"message":"You exceeded your current quota, please check your plan",'
        '"details":"'
        + ("x" * 700)
        + '"}}'
    )
    response = LLMResponse(content=body, model="m", usage={})

    assert ModelRouter._response_indicates_failure(response) == "quota_exhausted"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("HTTP error 429: too many requests", "rate_limited"),
        ("rate limit exceeded", "rate_limited"),
        ("insufficient_quota for this key", "quota_exhausted"),
        ("your credit balance is too low", "billing_exhausted"),
        ("OPENROUTER_API_KEY not set", "missing_config"),
        ("all connection attempts failed", "unreachable"),
    ],
)
def test_smoke_classifier_separates_rate_limit_and_quota(text: str, expected: str) -> None:
    assert _classify_error(text) == expected


@pytest.mark.asyncio
async def test_rate_limited_falls_through_without_fast_tripping_breaker() -> None:
    limited = _ContentProvider("rate_limit_exceeded: retry shortly")
    healthy = _ContentProvider("a fine answer")
    router = ModelRouter(
        {
            ProviderType.OPENAI: limited,
            ProviderType.OPENROUTER: healthy,
        },
        key_liveness_provider=_fail_open_key_liveness,
    )
    _pin_chain(router, ProviderType.OPENAI, ProviderType.OPENROUTER)

    decision, response = await router.complete_for_task(
        _route_request("task-rate-limit"),
        _llm_request(),
        available_provider_types=[ProviderType.OPENAI, ProviderType.OPENROUTER],
    )

    assert response.content == "a fine answer"
    assert limited.calls > 0, "the rate-limited lane must have been attempted"
    for lane in router._breaker_registry.snapshot_all():
        assert router._breaker_registry.get(lane).state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_quota_exhausted_fast_trips_breaker_open() -> None:
    exhausted = _ContentProvider("insufficient_quota")
    healthy = _ContentProvider("a fine answer")
    router = ModelRouter(
        {
            ProviderType.OPENAI: exhausted,
            ProviderType.OPENROUTER: healthy,
        },
        key_liveness_provider=_fail_open_key_liveness,
    )
    _pin_chain(router, ProviderType.OPENAI, ProviderType.OPENROUTER)

    decision, response = await router.complete_for_task(
        _route_request("task-quota"),
        _llm_request(),
        available_provider_types=[ProviderType.OPENAI, ProviderType.OPENROUTER],
    )

    assert response.content == "a fine answer"
    assert exhausted.calls > 0, "the exhausted lane must have been attempted"
    open_lanes = [
        key
        for key in router._breaker_registry.snapshot_all()
        if router._breaker_registry.get(key).state == CircuitState.OPEN
    ]
    assert open_lanes, "quota_exhausted must fast-trip the failing lane's breaker"
