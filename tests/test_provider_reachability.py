"""In-session provider deadpool: connection-dead lanes are skipped for a TTL.

Session-verified failure: with no Ollama server every task re-walked the same
connection-refused lane, burning instant-fail LLM calls on each request.
The router now classifies connection-level failures
(provider_deadpool.py:is_connection_dead_error), deadpools the lane for
PROVIDER_DEADPOOL_TTL_SECONDS, and retries only after expiry. Auth/4xx
failures never deadpool — a key can be fixed mid-session.
"""

from __future__ import annotations

import errno
import time

import httpx
import pytest

from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.provider_policy import (
    ProviderRouteDecision,
    ProviderRouteRequest,
    RoutePath,
)
from dharma_swarm.provider_deadpool import ProviderDeadpool, is_connection_dead_error
from dharma_swarm.providers import ModelRouter
from dharma_swarm.resilience import RetryPolicy


class _ContentProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        return LLMResponse(content=self.content, model=request.model, usage={})

    async def stream(self, request: LLMRequest):
        yield self.content


class _RaisingProvider:
    def __init__(self, exc_factory) -> None:
        self._exc_factory = exc_factory
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        raise self._exc_factory()

    async def stream(self, request: LLMRequest):
        yield ""


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
        context={"session_id": "sess-dp", "task_id": task_id, "run_id": task_id},
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


def _build_router(
    providers: dict[ProviderType, object],
    tmp_path,
    monkeypatch,
) -> ModelRouter:
    # Keep the walk hermetic: no home-dir receipts, no audit/retrospective IO.
    monkeypatch.setenv("DGC_ROUTER_RECEIPT_DB", str(tmp_path / "no_receipts.db"))
    monkeypatch.setenv("DGC_ROUTER_AUDIT_DISABLE", "1")
    monkeypatch.setenv("DGC_ROUTER_RETROSPECTIVE_DISABLE", "1")
    return ModelRouter(
        providers,  # type: ignore[arg-type]
        key_liveness_provider=_fail_open_key_liveness,
        retry_policy=RetryPolicy(max_attempts=1),
    )


# ---------------------------------------------------------------------------
# is_connection_dead_error classification
# ---------------------------------------------------------------------------


def _wrapped_connection_error() -> Exception:
    wrapper = RuntimeError("provider transport failed")
    wrapper.__cause__ = ConnectionRefusedError("[Errno 111] Connection refused")
    return wrapper


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (ConnectionRefusedError("[Errno 111] Connection refused"), True),
        (ConnectionResetError("connection reset by peer"), True),
        (httpx.ConnectError("All connection attempts failed"), True),
        (httpx.ConnectTimeout("timed out while connecting"), True),
        (OSError(errno.EHOSTUNREACH, "No route to host"), True),
        (_wrapped_connection_error(), True),
        (RuntimeError("401 Unauthorized: invalid api key"), False),
        (RuntimeError("OPENROUTER_API_KEY not set"), False),
        (RuntimeError("HTTP 429 Too Many Requests"), False),
        (RuntimeError("403 Forbidden"), False),
    ],
)
def test_is_connection_dead_error_classification(exc: Exception, expected: bool) -> None:
    assert is_connection_dead_error(exc) is expected


# ---------------------------------------------------------------------------
# Deadpool behavior in the chain walk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deadpool_skips_connection_dead_provider_within_ttl(
    tmp_path, monkeypatch,
) -> None:
    dead = _RaisingProvider(
        lambda: ConnectionRefusedError("[Errno 111] Connection refused")
    )
    healthy = _ContentProvider("a fine answer")
    router = _build_router(
        {ProviderType.OLLAMA: dead, ProviderType.OPENROUTER: healthy},
        tmp_path,
        monkeypatch,
    )
    _pin_chain(router, ProviderType.OLLAMA, ProviderType.OPENROUTER)
    available = [ProviderType.OLLAMA, ProviderType.OPENROUTER]

    # Walk 1: the dead lane is attempted once, fails, and is deadpooled.
    _, response = await router.complete_for_task(
        _route_request("task-dp-1"), _llm_request(), available_provider_types=available,
    )
    assert response.content == "a fine answer"
    assert dead.calls == 1
    assert router._provider_deadpool.active(ProviderType.OLLAMA)

    # Walk 2 (within TTL): the corpse is skipped — no new instant-fail call.
    decision, response = await router.complete_for_task(
        _route_request("task-dp-2"), _llm_request(), available_provider_types=available,
    )
    assert response.content == "a fine answer"
    assert dead.calls == 1, "deadpooled provider must not be re-walked within TTL"
    assert "provider_deadpool_applied" in decision.reasons
    assert decision.selected_provider == ProviderType.OPENROUTER

    # After TTL expiry the lane is probed again.
    router._provider_deadpool._entries[ProviderType.OLLAMA] = time.monotonic() - 1.0
    _, response = await router.complete_for_task(
        _route_request("task-dp-3"), _llm_request(), available_provider_types=available,
    )
    assert response.content == "a fine answer"
    assert dead.calls == 2, "expired deadpool entry must allow a retry"


@pytest.mark.asyncio
async def test_deadpool_clears_when_provider_recovers(tmp_path, monkeypatch) -> None:
    healthy = _ContentProvider("recovered answer")
    router = _build_router(
        {ProviderType.OLLAMA: healthy, ProviderType.OPENROUTER: _ContentProvider("other")},
        tmp_path,
        monkeypatch,
    )
    _pin_chain(router, ProviderType.OLLAMA, ProviderType.OPENROUTER)
    # Simulate an expired deadpool entry left over from an earlier outage.
    router._provider_deadpool._entries[ProviderType.OLLAMA] = time.monotonic() - 1.0

    _, response = await router.complete_for_task(
        _route_request("task-dp-recover"),
        _llm_request(),
        available_provider_types=[ProviderType.OLLAMA, ProviderType.OPENROUTER],
    )

    assert response.content == "recovered answer"
    assert ProviderType.OLLAMA not in router._provider_deadpool


@pytest.mark.asyncio
async def test_fully_deadpooled_chain_fails_open(tmp_path, monkeypatch) -> None:
    dead = _RaisingProvider(
        lambda: ConnectionRefusedError("[Errno 111] Connection refused")
    )
    router = _build_router({ProviderType.OLLAMA: dead}, tmp_path, monkeypatch)
    _pin_chain(router, ProviderType.OLLAMA, ProviderType.OLLAMA)
    available = [ProviderType.OLLAMA]

    with pytest.raises(RuntimeError, match="All providers failed"):
        await router.complete_for_task(
            _route_request("task-dp-open-1"),
            _llm_request(),
            available_provider_types=available,
        )
    assert dead.calls == 1
    assert router._provider_deadpool.active(ProviderType.OLLAMA)

    # The only lane is deadpooled — the walk fails open and re-probes it
    # rather than raising without any attempt.
    with pytest.raises(RuntimeError, match="All providers failed"):
        await router.complete_for_task(
            _route_request("task-dp-open-2"),
            _llm_request(),
            available_provider_types=available,
        )
    assert dead.calls == 2


@pytest.mark.asyncio
async def test_auth_failure_does_not_deadpool(tmp_path, monkeypatch) -> None:
    unauthorized = _RaisingProvider(
        lambda: RuntimeError("401 Unauthorized: invalid api key")
    )
    healthy = _ContentProvider("a fine answer")
    router = _build_router(
        {ProviderType.OPENAI: unauthorized, ProviderType.OPENROUTER: healthy},
        tmp_path,
        monkeypatch,
    )
    _pin_chain(router, ProviderType.OPENAI, ProviderType.OPENROUTER)
    available = [ProviderType.OPENAI, ProviderType.OPENROUTER]

    _, response = await router.complete_for_task(
        _route_request("task-auth-1"), _llm_request(), available_provider_types=available,
    )
    assert response.content == "a fine answer"
    assert unauthorized.calls == 1
    assert not router._provider_deadpool.active(ProviderType.OPENAI)
    assert ProviderType.OPENAI not in router._provider_deadpool

    # The auth-broken lane stays in the walk — a fixed key works mid-session.
    _, response = await router.complete_for_task(
        _route_request("task-auth-2"), _llm_request(), available_provider_types=available,
    )
    assert response.content == "a fine answer"
    assert unauthorized.calls == 2


# ---------------------------------------------------------------------------
# Direct cheap-first walk (runtime_provider.complete_via_preferred_runtime_providers)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preferred_runtime_chain_deadpools_connection_dead_lane(
    monkeypatch,
) -> None:
    import dharma_swarm.runtime_provider as runtime_provider

    dead_config = runtime_provider.RuntimeProviderConfig(
        provider=ProviderType.OLLAMA, available=True,
    )
    healthy_config = runtime_provider.RuntimeProviderConfig(
        provider=ProviderType.GROQ, available=True, default_model="qwen3-32b",
    )
    calls = {"dead": 0, "healthy": 0}

    class _DeadLane:
        async def complete(self, request: LLMRequest) -> LLMResponse:
            calls["dead"] += 1
            raise ConnectionRefusedError("[Errno 111] Connection refused")

    class _HealthyLane:
        async def complete(self, request: LLMRequest) -> LLMResponse:
            calls["healthy"] += 1
            return LLMResponse(content="ok", model=request.model, usage={})

    monkeypatch.setattr(
        runtime_provider,
        "preferred_runtime_provider_configs",
        lambda **_kwargs: [dead_config, healthy_config],
    )
    monkeypatch.setattr(
        runtime_provider,
        "create_runtime_provider",
        lambda config: _DeadLane()
        if config.provider is ProviderType.OLLAMA
        else _HealthyLane(),
    )
    monkeypatch.setattr(
        runtime_provider, "_PREFERRED_CHAIN_DEADPOOL", ProviderDeadpool(),
    )
    messages = [{"role": "user", "content": "hello"}]

    # Walk 1: dead lane attempted once, deadpooled, healthy lane answers.
    response, used = await runtime_provider.complete_via_preferred_runtime_providers(
        messages=messages,
    )
    assert response.content == "ok"
    assert used.provider is ProviderType.GROQ
    assert calls["dead"] == 1

    # Walk 2 (within TTL): the corpse is skipped.
    response, used = await runtime_provider.complete_via_preferred_runtime_providers(
        messages=messages,
    )
    assert used.provider is ProviderType.GROQ
    assert calls["dead"] == 1, "deadpooled lane must not be re-walked within TTL"
    assert calls["healthy"] == 2

    # Expired entry: the lane is probed again.
    runtime_provider._PREFERRED_CHAIN_DEADPOOL._entries[ProviderType.OLLAMA] = (
        time.monotonic() - 1.0
    )
    await runtime_provider.complete_via_preferred_runtime_providers(messages=messages)
    assert calls["dead"] == 2


# ---------------------------------------------------------------------------
# Boot seeds (same session failure class: every API boot warned that gnani
# stigmergy seeding crashed on StigmergicMark's observation max_length)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gnani_stigmergy_seeding_truncates_long_observations(
    tmp_path, monkeypatch,
) -> None:
    import dharma_swarm.stigmergy as stigmergy_module
    from dharma_swarm.gnani_lodestone import _GNANI_MARKS, GnaniLodestone
    from dharma_swarm.stigmergy import StigmergicMark, StigmergyStore

    monkeypatch.setattr(stigmergy_module, "_DEFAULT_BASE", tmp_path / "stigmergy")
    observation_limit = next(
        constraint.max_length
        for constraint in StigmergicMark.model_fields["observation"].metadata
        if getattr(constraint, "max_length", None) is not None
    )
    # The seeded narrative really is longer than the schema allows — that is
    # the crash this guards against.
    assert any(len(m["observation"]) > observation_limit for m in _GNANI_MARKS)

    lodestone = GnaniLodestone(state_dir=tmp_path)
    injected = await lodestone._seed_stigmergy()

    assert injected == len(_GNANI_MARKS), "seeding must not crash on long content"
    store = StigmergyStore(tmp_path / "stigmergy")
    marks = await store.query_relevant(
        task_keywords=[m["file_path"] for m in _GNANI_MARKS],
        limit=50,
        channel="gnani",
    )
    seeded_ids = {mark.id for mark in marks}
    assert seeded_ids == {m["id"] for m in _GNANI_MARKS}
    for mark in marks:
        assert len(mark.observation) <= observation_limit

    # Idempotent: a second boot injects nothing new.
    assert await lodestone._seed_stigmergy() == 0


@pytest.mark.asyncio
async def test_gnani_concept_seeding_uses_semantic_gravity_graph(tmp_path) -> None:
    from dharma_swarm.gnani_lodestone import _GNANI_CONCEPTS, GnaniLodestone
    from dharma_swarm.semantic_gravity import ConceptGraph

    lodestone = GnaniLodestone(state_dir=tmp_path)
    added = await lodestone._seed_concepts()

    assert added == len(_GNANI_CONCEPTS)
    graph_path = tmp_path / "meta" / "concept_graph.json"
    assert graph_path.exists()
    graph = await ConceptGraph.load(graph_path)
    node = graph.get_node("gnani_layer")
    assert node is not None
    assert node.definition
    # Idempotent: a second boot adds nothing.
    assert await lodestone._seed_concepts() == 0
