from __future__ import annotations

import pytest

from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.provider_policy import (
    ProviderRouteDecision,
    ProviderRouteRequest,
    RoutePath,
)
from dharma_swarm.providers import ModelRouter
from dharma_swarm.resilience import RetryPolicy
from dharma_swarm.runtime_provider import RuntimeProviderConfig, create_default_provider_map
from dharma_swarm.runtime_provider import (
    deduplicate_runtime_provider_configs,
    runtime_provider_transport_identity,
)


class _ManualClaudeCli:
    _cli_command = "claude"
    _resolved_command = "/fixture/bin/claude"

    def __init__(self, logical_label: str, attempts: list[str]) -> None:
        self.logical_label = logical_label
        self.attempts = attempts

    async def complete(self, _request: LLMRequest) -> LLMResponse:
        self.attempts.append(self.logical_label)
        raise RuntimeError(f"{self.logical_label} fixture failure")


class _DistinctApiTransport:
    def __init__(self, attempts: list[str]) -> None:
        self.attempts = attempts

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.attempts.append("groq")
        return LLMResponse(content="distinct transport ok", model=request.model)


class _ManualApiTransport:
    def __init__(
        self,
        logical_label: str,
        attempts: list[str],
        runtime_config: RuntimeProviderConfig,
    ) -> None:
        self.logical_label = logical_label
        self.attempts = attempts
        self.runtime_config = runtime_config

    async def complete(self, _request: LLMRequest) -> LLMResponse:
        self.attempts.append(self.logical_label)
        raise RuntimeError(f"{self.logical_label} fixture failure")


def _route_request() -> ProviderRouteRequest:
    return ProviderRouteRequest(
        action_name="physical_transport_fixture",
        risk_score=0.1,
        uncertainty=0.1,
        novelty=0.1,
        urgency=0.1,
        expected_impact=0.1,
    )


class _CapturingPolicyRouter:
    def __init__(self) -> None:
        self.available: list[ProviderType] = []

    def route(
        self,
        _request: ProviderRouteRequest,
        *,
        available_providers: list[ProviderType],
    ) -> ProviderRouteDecision:
        self.available = list(available_providers)
        return ProviderRouteDecision(
            path=RoutePath.REFLEX,
            selected_provider=available_providers[0],
            selected_model_hint=None,
            fallback_providers=list(available_providers[1:]),
            fallback_model_hints=[],
            confidence=1.0,
            requires_human=False,
            reasons=["capture_available"],
        )


def _configured_provider(config: RuntimeProviderConfig) -> _DistinctApiTransport:
    provider = _DistinctApiTransport([])
    provider.runtime_config = config
    return provider


def test_route_policy_sees_shared_claude_cli_once() -> None:
    policy = _CapturingPolicyRouter()
    router = ModelRouter(
        {
            ProviderType.ANTHROPIC: _configured_provider(
                RuntimeProviderConfig(
                    provider=ProviderType.ANTHROPIC,
                    transport_mode="claude_code",
                    binary_path="/fixture/bin/claude",
                    available=True,
                )
            ),
            ProviderType.CLAUDE_CODE: _configured_provider(
                RuntimeProviderConfig(
                    provider=ProviderType.CLAUDE_CODE,
                    binary_path="/fixture/bin/claude",
                    available=True,
                )
            ),
        },
        policy_router=policy,
    )

    router.route_request(
        _route_request(),
        available_provider_types=[ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE],
    )

    assert policy.available == [ProviderType.ANTHROPIC]


def test_default_provider_map_exposes_shared_claude_cli_once_to_policy(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "dharma_swarm.runtime_provider._resolve_cli_binary",
        lambda name: f"/fixture/bin/{name}",
    )
    policy = _CapturingPolicyRouter()
    router = ModelRouter(
        create_default_provider_map(env={}),
        policy_router=policy,
    )

    decision = router.route_request(
        _route_request(),
        available_provider_types=[ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE],
    )

    assert policy.available == [ProviderType.ANTHROPIC]
    assert decision.selected_provider == ProviderType.ANTHROPIC
    assert any("claude_code->anthropic" in reason for reason in decision.reasons)


def test_route_policy_keeps_raw_anthropic_api_distinct_from_claude_cli() -> None:
    policy = _CapturingPolicyRouter()
    router = ModelRouter(
        {
            ProviderType.ANTHROPIC: _configured_provider(
                RuntimeProviderConfig(
                    provider=ProviderType.ANTHROPIC,
                    api_key="fixture-key-not-live",
                    available=True,
                )
            ),
            ProviderType.CLAUDE_CODE: _configured_provider(
                RuntimeProviderConfig(
                    provider=ProviderType.CLAUDE_CODE,
                    binary_path="/fixture/bin/claude",
                    available=True,
                )
            ),
        },
        policy_router=policy,
    )

    router.route_request(
        _route_request(),
        available_provider_types=[ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE],
    )

    assert policy.available == [ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE]


def test_url_transport_identity_metadata_and_audit_reason_exclude_secrets() -> None:
    secret_url = (
        "HTTPS://fixture-user:fixture-password@Proxy.Example.invalid:443/"
        "v1/token-fixture-secret;session=fixture-path-param/"
        "?api_key=fixture-secret#fixture-fragment"
    )
    first = RuntimeProviderConfig(
        provider=ProviderType.OPENROUTER,
        base_url=secret_url,
        available=True,
    )
    duplicate = RuntimeProviderConfig(
        provider=ProviderType.OPENROUTER_FREE,
        base_url=secret_url,
        available=True,
    )

    identity = runtime_provider_transport_identity(first)
    configs = deduplicate_runtime_provider_configs([first, duplicate])

    assert identity == (
        "provider:https://proxy.example.invalid/"
        ".path-sha256-577fe600c91f9f003d700eacb468f609be0908d9eb131d8c83392a43a8babbe3"
    )
    assert identity == runtime_provider_transport_identity(duplicate)
    assert configs[0].metadata == {
        "physical_transport_identity": identity,
        "logical_provider_aliases": [
            ProviderType.OPENROUTER.value,
            ProviderType.OPENROUTER_FREE.value,
        ],
    }

    policy = _CapturingPolicyRouter()
    router = ModelRouter(
        {
            ProviderType.OPENROUTER: _configured_provider(first),
            ProviderType.OPENROUTER_FREE: _configured_provider(duplicate),
        },
        policy_router=policy,
    )
    decision = router.route_request(
        _route_request(),
        available_provider_types=[
            ProviderType.OPENROUTER,
            ProviderType.OPENROUTER_FREE,
        ],
    )

    assert policy.available == [ProviderType.OPENROUTER]
    reason = next(
        item for item in decision.reasons if item.startswith("physical_transport_dedup=")
    )
    assert reason == (
        "physical_transport_dedup="
        f"openrouter_free->openrouter@{identity}"
    )
    for secret in (
        "fixture-user",
        "fixture-password",
        "token-fixture-secret",
        "fixture-path-param",
        "fixture-secret",
        "fixture-fragment",
        "?",
        "#",
    ):
        assert secret not in identity
        assert secret not in configs[0].metadata["physical_transport_identity"]
        assert secret not in reason

    different_path = RuntimeProviderConfig(
        provider=ProviderType.OPENROUTER_FREE,
        base_url="https://proxy.example.invalid/v2/another-secret",
        available=True,
    )
    assert runtime_provider_transport_identity(different_path) != identity


def test_api_transport_identity_without_endpoint_fails_open_by_logical_provider() -> None:
    paid = RuntimeProviderConfig(
        provider=ProviderType.OPENROUTER,
        available=True,
    )
    free = RuntimeProviderConfig(
        provider=ProviderType.OPENROUTER_FREE,
        available=True,
    )

    assert runtime_provider_transport_identity(paid) == "provider:openrouter"
    assert runtime_provider_transport_identity(free) == "provider:openrouter_free"

    malformed = RuntimeProviderConfig(
        provider=ProviderType.GROQ,
        base_url="/raw-path-fixture-secret",
        available=True,
    )
    malformed_identity = runtime_provider_transport_identity(malformed)
    assert malformed_identity == "provider:groq"
    assert "raw-path-fixture-secret" not in malformed_identity


@pytest.mark.asyncio
async def test_model_router_attempts_shared_api_endpoint_once() -> None:
    attempts: list[str] = []
    endpoint = "https://openrouter.example.invalid/api/v1"
    router = ModelRouter(
        {
            ProviderType.OPENROUTER: _ManualApiTransport(
                "openrouter",
                attempts,
                RuntimeProviderConfig(
                    provider=ProviderType.OPENROUTER,
                    base_url=endpoint,
                    available=True,
                ),
            ),
            ProviderType.OPENROUTER_FREE: _ManualApiTransport(
                "openrouter_free",
                attempts,
                RuntimeProviderConfig(
                    provider=ProviderType.OPENROUTER_FREE,
                    base_url=endpoint,
                    available=True,
                ),
            ),
            ProviderType.GROQ: _DistinctApiTransport(attempts),
        },
        retry_policy=RetryPolicy(max_attempts=1),
        key_liveness_provider=lambda: None,
    )
    decision = ProviderRouteDecision(
        path=RoutePath.REFLEX,
        selected_provider=ProviderType.OPENROUTER,
        selected_model_hint="paid-fixture",
        fallback_providers=[ProviderType.OPENROUTER_FREE, ProviderType.GROQ],
        fallback_model_hints=["free-fixture", "groq-fixture"],
        confidence=1.0,
        requires_human=False,
        reasons=["fixture_order"],
    )
    router.route_request = lambda *_args, **_kwargs: decision  # type: ignore[method-assign]

    routed, response = await router.complete_for_task(
        _route_request(),
        LLMRequest(
            model="fixture-model",
            messages=[{"role": "user", "content": "hello"}],
        ),
        available_provider_types=[
            ProviderType.OPENROUTER,
            ProviderType.OPENROUTER_FREE,
            ProviderType.GROQ,
        ],
    )

    assert attempts == ["openrouter", "groq"]
    assert response.content == "distinct transport ok"
    assert routed.selected_provider == ProviderType.GROQ
    assert ProviderType.OPENROUTER_FREE not in routed.fallback_providers
    assert any("openrouter_free->openrouter" in reason for reason in routed.reasons)


@pytest.mark.asyncio
async def test_model_router_attempts_shared_manual_claude_cli_once() -> None:
    attempts: list[str] = []
    router = ModelRouter(
        {
            ProviderType.ANTHROPIC: _ManualClaudeCli("anthropic", attempts),
            ProviderType.CLAUDE_CODE: _ManualClaudeCli("claude_code", attempts),
            ProviderType.GROQ: _DistinctApiTransport(attempts),
        },
        retry_policy=RetryPolicy(max_attempts=1),
        key_liveness_provider=lambda: None,
    )
    decision = ProviderRouteDecision(
        path=RoutePath.REFLEX,
        selected_provider=ProviderType.ANTHROPIC,
        selected_model_hint="claude-test",
        fallback_providers=[ProviderType.CLAUDE_CODE, ProviderType.GROQ],
        fallback_model_hints=["claude-test", "groq-test"],
        confidence=1.0,
        requires_human=False,
        reasons=["fixture_order"],
    )
    router.route_request = lambda *_args, **_kwargs: decision  # type: ignore[method-assign]

    routed, response = await router.complete_for_task(
        _route_request(),
        LLMRequest(
            model="fixture-model",
            messages=[{"role": "user", "content": "hello"}],
        ),
        available_provider_types=[
            ProviderType.ANTHROPIC,
            ProviderType.CLAUDE_CODE,
            ProviderType.GROQ,
        ],
    )

    assert attempts == ["anthropic", "groq"]
    assert response.content == "distinct transport ok"
    assert routed.selected_provider == ProviderType.GROQ
    assert ProviderType.CLAUDE_CODE not in routed.fallback_providers
    assert any("physical_transport_dedup" in reason for reason in routed.reasons)
