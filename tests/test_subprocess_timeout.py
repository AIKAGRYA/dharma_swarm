"""A hung claude/codex subprocess is a lane FAILURE, never a fake success.

Gate D: routing-canon PROGRAM_DESIGN.md PR-4.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from dharma_swarm.base_provider import ProviderTimeoutError
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.provider_policy import ProviderRouteRequest
from dharma_swarm.provider_transport import response_indicates_failure
from dharma_swarm.providers import ClaudeCodeProvider, ModelRouter
from dharma_swarm.resilience import RetryPolicy, is_retryable_exception
from dharma_swarm.routing_memory import RoutingMemoryStore
from dharma_swarm.runtime_provider import (
    RuntimeProviderConfig,
    complete_via_preferred_runtime_providers,
)

_REQUEST = LLMRequest(model="claude-code", messages=[{"role": "user", "content": "ping"}])


def _hanging_exec():
    """create_subprocess_exec replacement: communicate() never returns."""
    spawned: list[Mock] = []

    async def fake_exec(*args, **kwargs):
        proc = Mock()

        async def communicate():
            await asyncio.Event().wait()

        proc.communicate = communicate
        proc.terminate = Mock()
        proc.wait = AsyncMock(return_value=None)
        proc.returncode = None
        spawned.append(proc)
        return proc

    return fake_exec, spawned


@pytest.mark.asyncio
async def test_hung_subprocess_raises_timeout_error_after_terminating():
    fake_exec, spawned = _hanging_exec()
    provider = ClaudeCodeProvider(timeout=0.05)

    started = time.monotonic()
    with patch("dharma_swarm.providers.asyncio.create_subprocess_exec", side_effect=fake_exec):
        with pytest.raises(ProviderTimeoutError) as excinfo:
            await provider.complete(_REQUEST)
    elapsed = time.monotonic() - started

    assert elapsed < 2.0
    assert isinstance(excinfo.value, TimeoutError)
    assert excinfo.value.failure_kind == "provider_timeout"
    assert len(spawned) == 1
    spawned[0].terminate.assert_called_once()
    spawned[0].wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_preferred_chain_falls_through_hung_lane_to_next_lane(monkeypatch):
    fake_exec, _ = _hanging_exec()
    calls: list[str] = []

    class _PongProvider:
        async def complete(self, request: LLMRequest) -> LLMResponse:
            calls.append("pong")
            return LLMResponse(content="PONG", model=request.model)

    def _fake_configs(**kwargs):
        return [
            RuntimeProviderConfig(
                provider=ProviderType.CLAUDE_CODE, available=True, default_model="sonnet"
            ),
            RuntimeProviderConfig(
                provider=ProviderType.OLLAMA, available=True, default_model="pong-model"
            ),
        ]

    def _fake_create(config):
        if config.provider == ProviderType.CLAUDE_CODE:
            calls.append("claude_code")
            return ClaudeCodeProvider(timeout=0.05)
        return _PongProvider()

    monkeypatch.setattr(
        "dharma_swarm.runtime_provider.preferred_runtime_provider_configs", _fake_configs
    )
    monkeypatch.setattr("dharma_swarm.runtime_provider.create_runtime_provider", _fake_create)

    with patch("dharma_swarm.providers.asyncio.create_subprocess_exec", side_effect=fake_exec):
        response, config = await complete_via_preferred_runtime_providers(
            messages=[{"role": "user", "content": "Reply with exactly PONG"}],
            provider_order=(ProviderType.CLAUDE_CODE, ProviderType.OLLAMA),
        )

    assert response.content == "PONG"
    assert config.provider == ProviderType.OLLAMA
    assert calls == ["claude_code", "pong"]


@pytest.mark.asyncio
async def test_genuine_content_mentioning_timeout_is_not_misclassified():
    body = b"timeout exceeded, retrying later"

    async def fake_exec(*args, **kwargs):
        proc = Mock()
        proc.communicate = AsyncMock(return_value=(body, b""))
        proc.returncode = 0
        return proc

    provider = ClaudeCodeProvider(timeout=5)
    with patch("dharma_swarm.providers.asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = await provider.complete(_REQUEST)

    assert result.content == "timeout exceeded, retrying later"
    assert result.model == "claude-code"
    assert response_indicates_failure(result) is None


def test_provider_timeout_is_not_retried_by_router_policy():
    assert is_retryable_exception(ProviderTimeoutError("claude-code timed out after 300s")) is False


@pytest.mark.asyncio
async def test_model_router_treats_hung_lane_as_timeout_failure_without_retry(tmp_path):
    fake_exec, spawned = _hanging_exec()
    store = RoutingMemoryStore(tmp_path / "routing.sqlite3")
    outcomes: list[tuple[str, bool, str | None]] = []
    real_record = store.record_outcome

    def _spy(**kwargs):
        outcomes.append((kwargs["provider"].value, kwargs["success"], kwargs.get("error")))
        return real_record(**kwargs)

    store.record_outcome = _spy

    class _PongProvider:
        async def complete(self, request: LLMRequest) -> LLMResponse:
            return LLMResponse(content="PONG", model=request.model)

        async def stream(self, request: LLMRequest):
            yield "PONG"

    router = ModelRouter(
        {
            ProviderType.CLAUDE_CODE: ClaudeCodeProvider(timeout=0.05),
            ProviderType.OLLAMA: _PongProvider(),
        },
        routing_memory=store,
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.0, jitter_seconds=0.0),
        key_liveness_provider=lambda: None,
    )

    with patch("dharma_swarm.providers.asyncio.create_subprocess_exec", side_effect=fake_exec):
        decision, response = await router.complete_for_task(
            ProviderRouteRequest(
                action_name="ping",
                risk_score=0.05,
                uncertainty=0.05,
                novelty=0.05,
                urgency=0.2,
                expected_impact=0.1,
            ),
            LLMRequest(model="sonnet", messages=[{"role": "user", "content": "Reply PONG"}]),
            available_provider_types=[ProviderType.CLAUDE_CODE, ProviderType.OLLAMA],
        )

    assert response.content == "PONG"
    assert decision.selected_provider == ProviderType.OLLAMA
    assert len(spawned) == 1
    assert outcomes == [("claude_code", False, "provider_timeout"), ("ollama", True, None)]
