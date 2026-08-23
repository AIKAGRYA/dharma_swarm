"""Tests for dharma_swarm.providers."""

import ast
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dharma_swarm.model_hierarchy import default_model
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.campaign_provider_guard import (
    CampaignProviderEffectBoundary,
    build_campaign_exact_provider_call,
)
from dharma_swarm.providers import (
    AnthropicProvider,
    ClaudeCodeProvider,
    CodexProvider,
    FireworksProvider,
    GroqProvider,
    KimiCodeProvider,
    LLMProvider,
    ModelRouter,
    NVIDIANIMProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterFreeProvider,
    SiliconFlowProvider,
    TogetherProvider,
    _ollama_cloud_wire_model,
    create_default_router,
)
from dharma_swarm.provider_policy import ProviderRouteRequest
from dharma_swarm.resilience import RetryPolicy
from dharma_swarm.ollama_config import get_ollama_cloud_frontier_chain


_SADHANA_ADMITTED_OLLAMA_CLOUD_MODELS = (
    "glm-5.2:cloud",
    "kimi-k3:cloud",
    "deepseek-v4-pro:0813:cloud",
    "minimax-m3:cloud",
    "nemotron-3-ultra:cloud",
    "qwen3.5:397b:cloud",
    "mistral-large-3:675b:cloud",
)


def _allow_campaign_provider_effect() -> CampaignProviderEffectBoundary:
    async def fence() -> None:
        return None

    return CampaignProviderEffectBoundary(fence, lambda: None)


def test_campaign_provider_guard_import_leaf_both_orders() -> None:
    root = Path(__file__).resolve().parents[1]
    guard_path = root / "dharma_swarm" / "campaign_provider_guard.py"
    tree = ast.parse(guard_path.read_text(encoding="utf-8"))
    imported = {
        module
        for node in ast.walk(tree)
        for module in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module]
            if isinstance(node, ast.ImportFrom) and node.module is not None
            else []
        )
    }
    forbidden = {
        "dharma_swarm.providers",
        "dharma_swarm.agent_runner",
        "dharma_swarm.orchestrator",
    }
    assert not imported & forbidden
    assert not any(name.startswith("dharma_swarm.mission_control_") for name in imported)

    orders = (
        "import dharma_swarm.campaign_provider_guard; import dharma_swarm.providers",
        "import dharma_swarm.providers; import dharma_swarm.campaign_provider_guard",
    )
    for statement in orders:
        completed = subprocess.run(
            [sys.executable, "-c", statement],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr


def test_anthropic_provider_init():
    p = AnthropicProvider(api_key="test-key")
    assert p._api_key == "test-key"


def test_anthropic_provider_no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = AnthropicProvider(api_key=None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        p._client_or_raise()


def test_openai_provider_init():
    p = OpenAIProvider(api_key="test-key")
    assert p._api_key == "test-key"


def test_openai_provider_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = OpenAIProvider(api_key=None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        p._client_or_raise()


def test_strip_system():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    result = AnthropicProvider._strip_system(msgs)
    assert len(result) == 1
    assert result[0]["role"] == "user"


def test_build_messages():
    msgs = [{"role": "user", "content": "hi"}]
    result = OpenAIProvider._build_messages(msgs, system="be helpful")
    assert len(result) == 2
    assert result[0]["role"] == "system"


@pytest.mark.asyncio
async def test_kimi_code_stream_forwards_tools():
    captured: dict[str, object] = {}

    class _Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)

            async def _chunks():
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="ok"))])

            return _chunks()

    provider = KimiCodeProvider(api_key="test-key")
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
    tools = [{"type": "function", "function": {"name": "lookup", "parameters": {}}}]
    request = LLMRequest(
        model="kimi-code",
        messages=[{"role": "user", "content": "hi"}],
        tools=tools,
    )

    chunks = [chunk async for chunk in provider.stream(request)]

    assert chunks == ["ok"]
    assert captured["tools"] == tools


def test_model_router_missing():
    router = ModelRouter({})
    with pytest.raises(KeyError, match="No provider"):
        router.get_provider(ProviderType.ANTHROPIC)


def test_model_router_lookup():
    p = AnthropicProvider(api_key="test")
    router = ModelRouter({ProviderType.ANTHROPIC: p})
    assert router.get_provider(ProviderType.ANTHROPIC) is p


@pytest.mark.asyncio
async def test_campaign_inherited_provider_has_no_exact_model_fallback(
    tmp_path,
) -> None:
    class _InheritedProvider(LLMProvider):
        available = True

        def __init__(self) -> None:
            self.complete_calls = 0

        async def complete(self, _request):
            self.complete_calls += 1
            return LLMResponse(
                content="must not run",
                provider="ollama",
                model="fixture-model:cloud",
            )

        async def stream(self, _request):
            if False:
                yield ""

    provider = _InheritedProvider()
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    model = "fixture-model:cloud"
    fence = AsyncMock()
    ready = MagicMock()
    boundary = CampaignProviderEffectBoundary(fence, ready)

    with pytest.raises(RuntimeError, match="lacks exact-model execution"):
        await router.complete_for_task(
            _exact_ollama_route_request(model),
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "bounded evidence"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=boundary,
        )

    assert provider.complete_calls == 0
    fence.assert_not_awaited()
    ready.assert_not_called()
    assert boundary.started is False


@pytest.mark.asyncio
async def test_campaign_exact_provider_failure_is_single_attempt_without_fallback(
    tmp_path,
) -> None:
    class _FailingProvider:
        available = True

        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, _request):
            self.calls += 1
            raise RuntimeError("exact campaign provider failed")

        async def complete_exact_model(self, request):
            return await self.complete(request)

    exact = _FailingProvider()
    foreign = _FailingProvider()
    router = ModelRouter(
        {ProviderType.OLLAMA: exact, ProviderType.ANTHROPIC: foreign},
        retry_policy=RetryPolicy(
            max_attempts=5,
            base_delay_seconds=0,
            backoff_multiplier=1,
            max_delay_seconds=0,
            jitter_seconds=0,
        ),
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    model = "fixture-model:cloud"
    context = {
        "task_id": "campaign-task",
        "agent_id": "campaign-agent",
        "preferred_provider": "ollama",
        "preferred_model": model,
        "available_provider_types": ["ollama"],
        "preserve_requested_model": True,
        "campaign_exact_provider_call": build_campaign_exact_provider_call(
            task_id="campaign-task",
            principal_id="campaign-agent",
            provider="ollama",
            model=model,
        ),
    }
    route_request = ProviderRouteRequest(
        action_name="campaign-task",
        risk_score=0.1,
        uncertainty=0.1,
        novelty=0.1,
        urgency=0.1,
        expected_impact=0.1,
        context=context,
    )

    with pytest.raises(RuntimeError, match="All providers failed"):
        await router.complete_for_task(
            route_request,
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "bounded evidence"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=_allow_campaign_provider_effect(),
        )

    assert exact.calls == 1
    assert foreign.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("coordinate", ["task_id", "agent_id"])
async def test_campaign_provider_call_rejects_foreign_carrier_coordinate(
    coordinate: str,
    tmp_path,
) -> None:
    provider = AsyncMock()
    provider.available = True
    provider.complete = AsyncMock()
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    model = "fixture-model:cloud"
    context = {
        "task_id": "campaign-task",
        "agent_id": "campaign-agent",
        "preferred_provider": "ollama",
        "preferred_model": model,
        "available_provider_types": ["ollama"],
        "preserve_requested_model": True,
        "campaign_exact_provider_call": build_campaign_exact_provider_call(
            task_id="campaign-task",
            principal_id="campaign-agent",
            provider="ollama",
            model=model,
        ),
    }
    context[coordinate] = "foreign-coordinate"
    request = ProviderRouteRequest(
        action_name="campaign-task",
        risk_score=0.1,
        uncertainty=0.1,
        novelty=0.1,
        urgency=0.1,
        expected_impact=0.1,
        context=context,
    )

    with pytest.raises(RuntimeError, match="conflicts with routing request"):
        await router.complete_for_task(
            request,
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "bounded evidence"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=_allow_campaign_provider_effect(),
        )

    provider.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaign_provider_call_rejects_foreign_same_provider_canary_model(
    tmp_path,
) -> None:
    provider = AsyncMock()
    provider.available = True
    provider.complete = AsyncMock(
        return_value=LLMResponse(
            content="should not be called",
            provider="ollama",
            model="fixture-model:cloud",
        )
    )
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
        canary_percent=100,
        canary_provider=ProviderType.OLLAMA,
        canary_model_hint="foreign-canary-model",
    )
    model = "fixture-model:cloud"
    context = {
        "task_id": "campaign-task",
        "agent_id": "campaign-agent",
        "preferred_provider": "ollama",
        "preferred_model": model,
        "available_provider_types": ["ollama"],
        "preserve_requested_model": True,
        "campaign_exact_provider_call": build_campaign_exact_provider_call(
            task_id="campaign-task",
            principal_id="campaign-agent",
            provider="ollama",
            model=model,
        ),
    }
    request = ProviderRouteRequest(
        action_name="campaign-task",
        risk_score=0.1,
        uncertainty=0.1,
        novelty=0.1,
        urgency=0.1,
        expected_impact=0.1,
        context=context,
    )

    with pytest.raises(RuntimeError, match="fallback-free"):
        await router.complete_for_task(
            request,
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "bounded evidence"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=_allow_campaign_provider_effect(),
        )

    provider.complete.assert_not_awaited()


class _OllamaHTTPResponse:
    def __init__(self, status_code: int, *, model: str = "") -> None:
        self.status_code = status_code
        self.text = "fixture failure" if status_code != 200 else ""
        self._model = model

    def json(self) -> dict:
        return {
            "model": self._model,
            "choices": [
                {
                    "message": {"content": "bounded fixture response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {},
        }


class _OllamaHTTPClient:
    is_closed = False

    def __init__(self, responses: list[_OllamaHTTPResponse]) -> None:
        self.responses = list(responses)
        self.payloads: list[dict] = []

    async def post(self, _url, *, json, headers):
        self.payloads.append(dict(json))
        return self.responses.pop(0)


def _exact_ollama_route_request(model: str) -> ProviderRouteRequest:
    return ProviderRouteRequest(
        action_name="campaign-task",
        risk_score=0.1,
        uncertainty=0.1,
        novelty=0.1,
        urgency=0.1,
        expected_impact=0.1,
        context={
            "task_id": "campaign-task",
            "agent_id": "campaign-agent",
            "preferred_provider": "ollama",
            "preferred_model": model,
            "available_provider_types": ["ollama"],
            "preserve_requested_model": True,
            "campaign_exact_provider_call": build_campaign_exact_provider_call(
                task_id="campaign-task",
                principal_id="campaign-agent",
                provider="ollama",
                model=model,
            ),
        },
    )


def _block_policy_telemetry(
    router: ModelRouter,
    entered: asyncio.Event,
    release: asyncio.Event,
) -> None:
    async def block(**_kwargs) -> None:
        entered.set()
        await release.wait()

    router._record_policy_telemetry = block


@pytest.mark.asyncio
async def test_campaign_ollama_cloud_failure_never_calls_foreign_frontier_model(
    tmp_path,
) -> None:
    locked = "minimax-m3:cloud"
    foreign = next(
        candidate
        for candidate in get_ollama_cloud_frontier_chain()
        if candidate != locked
    )
    locked_wire = _ollama_cloud_wire_model(locked)
    foreign_wire = _ollama_cloud_wire_model(foreign)
    provider = OllamaProvider(
        base_url="https://ollama.com",
        model=locked,
        api_key="fixture-key",
    )
    client = _OllamaHTTPClient(
        [
            _OllamaHTTPResponse(503),
            _OllamaHTTPResponse(200, model=foreign_wire),
        ]
    )
    provider._client = client
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        retry_policy=RetryPolicy(max_attempts=5),
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )

    with pytest.raises(RuntimeError, match="All providers failed"):
        await router.complete_for_task(
            _exact_ollama_route_request(locked),
            LLMRequest(
                model=locked,
                messages=[{"role": "user", "content": "bounded evidence"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=_allow_campaign_provider_effect(),
        )

    assert [payload["model"] for payload in client.payloads] == [locked_wire]


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["fixture-model:cloud", "fixture-local-model"])
async def test_campaign_ollama_exact_model_on_local_transport_makes_no_http_request(
    model: str,
    tmp_path,
) -> None:
    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model=model,
        api_key="fixture-key",
    )
    client = _OllamaHTTPClient(
        [_OllamaHTTPResponse(200, model=model)]
    )
    provider._client = client
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )

    with pytest.raises(RuntimeError, match="All providers failed"):
        await router.complete_for_task(
            _exact_ollama_route_request(model),
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "bounded evidence"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=_allow_campaign_provider_effect(),
        )

    assert client.payloads == []


@pytest.mark.asyncio
async def test_generic_ollama_cloud_failure_retains_frontier_model_fallback() -> None:
    locked = "minimax-m3:cloud"
    foreign = next(
        candidate
        for candidate in get_ollama_cloud_frontier_chain()
        if candidate != locked
    )
    locked_wire = _ollama_cloud_wire_model(locked)
    foreign_wire = _ollama_cloud_wire_model(foreign)
    provider = OllamaProvider(
        base_url="https://ollama.com",
        model=locked,
        api_key="fixture-key",
    )
    client = _OllamaHTTPClient(
        [
            _OllamaHTTPResponse(503),
            _OllamaHTTPResponse(200, model=foreign_wire),
        ]
    )
    provider._client = client

    response = await provider.complete(
        LLMRequest(
            model=locked,
            messages=[{"role": "user", "content": "generic evidence"}],
        )
    )

    assert [payload["model"] for payload in client.payloads] == [
        locked_wire,
        foreign_wire,
    ]
    assert response.model == foreign_wire


@pytest.mark.asyncio
async def test_campaign_ollama_rejects_mismatched_returned_wire_model(
    tmp_path,
) -> None:
    locked, foreign, *_ = get_ollama_cloud_frontier_chain()
    locked_wire = _ollama_cloud_wire_model(locked)
    foreign_wire = _ollama_cloud_wire_model(foreign)
    provider = OllamaProvider(
        base_url="https://ollama.com",
        model=locked,
        api_key="fixture-key",
    )
    client = _OllamaHTTPClient(
        [_OllamaHTTPResponse(200, model=foreign_wire)]
    )
    provider._client = client
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )

    with pytest.raises(RuntimeError, match="All providers failed"):
        await router.complete_for_task(
            _exact_ollama_route_request(locked),
            LLMRequest(
                model=locked,
                messages=[{"role": "user", "content": "bounded evidence"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=_allow_campaign_provider_effect(),
        )

    assert [payload["model"] for payload in client.payloads] == [locked_wire]


@pytest.mark.asyncio
@pytest.mark.parametrize("locked", _SADHANA_ADMITTED_OLLAMA_CLOUD_MODELS)
async def test_campaign_ollama_maps_attested_wire_model_to_locked_logical_identity(
    locked: str,
    tmp_path,
) -> None:
    locked_wire = _ollama_cloud_wire_model(locked)
    provider = OllamaProvider(
        base_url="https://ollama.com",
        model=locked,
        api_key="fixture-key",
    )
    client = _OllamaHTTPClient(
        [_OllamaHTTPResponse(200, model=locked_wire)]
    )
    provider._client = client
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )

    decision, response = await router.complete_for_task(
        _exact_ollama_route_request(locked),
        LLMRequest(
            model=locked,
            messages=[{"role": "user", "content": "bounded evidence"}],
        ),
        available_provider_types=[ProviderType.OLLAMA],
        campaign_effect_boundary=_allow_campaign_provider_effect(),
    )

    assert [payload["model"] for payload in client.payloads] == [locked_wire]
    assert decision.selected_model_hint == locked
    assert response.provider == ProviderType.OLLAMA.value
    assert response.model == locked


@pytest.mark.asyncio
async def test_campaign_ollama_hostile_cloud_prefix_never_builds_headers_or_calls_http(
    tmp_path,
) -> None:
    locked = "minimax-m3:cloud"
    provider = OllamaProvider(
        base_url="https://ollama.com.evil.invalid",
        model=locked,
        api_key="fixture-secret-must-not-leave-process",
    )
    client = _OllamaHTTPClient(
        [_OllamaHTTPResponse(200, model=_ollama_cloud_wire_model(locked))]
    )
    provider._client = client
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )

    assert provider.transport_mode == "cloud_api"
    with patch.object(
        provider,
        "_get_client",
        side_effect=AssertionError("HTTP client must not be built"),
    ) as get_client, patch.object(
        provider,
        "_headers_or_raise",
        side_effect=AssertionError("credential headers must not be built"),
    ) as headers:
        with pytest.raises(RuntimeError, match="All providers failed"):
            await router.complete_for_task(
                _exact_ollama_route_request(locked),
                LLMRequest(
                    model=locked,
                    messages=[{"role": "user", "content": "bounded evidence"}],
                ),
                available_provider_types=[ProviderType.OLLAMA],
                campaign_effect_boundary=_allow_campaign_provider_effect(),
            )

    get_client.assert_not_called()
    headers.assert_not_called()
    assert client.payloads == []


@pytest.mark.asyncio
async def test_campaign_ollama_rejects_noncanonical_cloud_suffix_before_effect() -> None:
    provider = OllamaProvider(
        base_url="https://ollama.com",
        model="minimax-m3:cloud",
        api_key="fixture-key",
    )
    with patch.object(
        provider,
        "_get_client",
        side_effect=AssertionError("HTTP client must not be built"),
    ) as get_client, patch.object(
        provider,
        "_headers_or_raise",
        side_effect=AssertionError("credential headers must not be built"),
    ) as headers:
        with pytest.raises(RuntimeError, match="explicit :cloud model"):
            await provider.complete_exact_model(
                LLMRequest(
                    model="minimax-m3:CLOUD",
                    messages=[{"role": "user", "content": "bounded evidence"}],
                )
            )

    get_client.assert_not_called()
    headers.assert_not_called()


@pytest.mark.asyncio
async def test_campaign_router_rejects_same_type_registry_substitution_after_await(
    tmp_path,
) -> None:
    model = "minimax-m3:cloud"
    original = OllamaProvider(
        base_url="https://ollama.com",
        model=model,
        api_key="fixture-key",
    )
    substitute = OllamaProvider(
        base_url="https://ollama.com",
        model=model,
        api_key="fixture-key",
    )
    original.complete_exact_model = AsyncMock()
    substitute.complete_exact_model = AsyncMock()
    router = ModelRouter(
        {ProviderType.OLLAMA: original},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    entered = asyncio.Event()
    release = asyncio.Event()
    _block_policy_telemetry(router, entered, release)

    pending = asyncio.create_task(
        router.complete_for_task(
            _exact_ollama_route_request(model),
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "bounded evidence"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=_allow_campaign_provider_effect(),
        )
    )
    await asyncio.wait_for(entered.wait(), timeout=1)
    router._providers[ProviderType.OLLAMA] = substitute
    release.set()

    with pytest.raises(RuntimeError, match="provider boundary changed"):
        await pending
    original.complete_exact_model.assert_not_awaited()
    substitute.complete_exact_model.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("coordinate", "mutated"),
    [
        ("_model", "foreign-model:cloud"),
        ("_transport_mode", "local_native"),
        ("_base_url", "https://ollama.com/"),
    ],
)
async def test_campaign_router_rejects_provider_coordinate_mutation_after_await(
    coordinate: str,
    mutated: str,
    tmp_path,
) -> None:
    model = "minimax-m3:cloud"
    provider = OllamaProvider(
        base_url="https://ollama.com",
        model=model,
        api_key="fixture-key",
    )
    provider.complete_exact_model = AsyncMock()
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    entered = asyncio.Event()
    release = asyncio.Event()
    _block_policy_telemetry(router, entered, release)

    pending = asyncio.create_task(
        router.complete_for_task(
            _exact_ollama_route_request(model),
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "bounded evidence"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=_allow_campaign_provider_effect(),
        )
    )
    await asyncio.wait_for(entered.wait(), timeout=1)
    setattr(provider, coordinate, mutated)
    release.set()

    with pytest.raises(RuntimeError, match="provider boundary changed"):
        await pending
    provider.complete_exact_model.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaign_router_rejects_nested_request_mutation_after_await(
    tmp_path,
) -> None:
    model = "minimax-m3:cloud"
    provider = OllamaProvider(
        base_url="https://ollama.com",
        model=model,
        api_key="fixture-key",
    )
    provider.complete_exact_model = AsyncMock()
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    request = LLMRequest(
        model=model,
        messages=[{"role": "user", "content": "bounded evidence"}],
    )
    entered = asyncio.Event()
    release = asyncio.Event()
    _block_policy_telemetry(router, entered, release)

    pending = asyncio.create_task(
        router.complete_for_task(
            _exact_ollama_route_request(model),
            request,
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=_allow_campaign_provider_effect(),
        )
    )
    await asyncio.wait_for(entered.wait(), timeout=1)
    request.messages[0]["content"] = "mutated after route capture"
    release.set()

    with pytest.raises(RuntimeError, match="routed coordinates changed"):
        await pending
    provider.complete_exact_model.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaign_router_enters_final_fence_only_after_telemetry(
    tmp_path,
) -> None:
    model = "minimax-m3:cloud"
    provider = OllamaProvider(
        base_url="https://ollama.com",
        model=model,
        api_key="fixture-key",
    )
    provider.complete_exact_model = AsyncMock(
        return_value=LLMResponse(content="ok", provider="ollama", model=model)
    )
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    telemetry_entered = asyncio.Event()
    telemetry_release = asyncio.Event()
    fence_entered = asyncio.Event()
    fence_release = asyncio.Event()
    ready = MagicMock()
    _block_policy_telemetry(router, telemetry_entered, telemetry_release)

    async def fence() -> None:
        fence_entered.set()
        await fence_release.wait()

    pending = asyncio.create_task(
        router.complete_for_task(
            _exact_ollama_route_request(model),
            LLMRequest(model=model, messages=[{"role": "user", "content": "work"}]),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=CampaignProviderEffectBoundary(fence, ready),
        )
    )
    await asyncio.wait_for(telemetry_entered.wait(), timeout=1)
    assert fence_entered.is_set() is False
    ready.assert_not_called()
    provider.complete_exact_model.assert_not_awaited()

    telemetry_release.set()
    await asyncio.wait_for(fence_entered.wait(), timeout=1)
    ready.assert_not_called()
    provider.complete_exact_model.assert_not_awaited()
    fence_release.set()
    await pending

    ready.assert_called_once_with()
    provider.complete_exact_model.assert_awaited_once()


@pytest.mark.asyncio
async def test_campaign_router_pause_in_final_fence_is_preeffect(
    tmp_path,
) -> None:
    model = "minimax-m3:cloud"
    provider = OllamaProvider(
        base_url="https://ollama.com",
        model=model,
        api_key="fixture-key",
    )
    provider.complete_exact_model = AsyncMock()
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    ready = MagicMock()

    async def paused() -> None:
        raise RuntimeError("campaign paused at final provider fence")

    boundary = CampaignProviderEffectBoundary(paused, ready)
    with pytest.raises(RuntimeError, match="paused at final provider fence"):
        await router.complete_for_task(
            _exact_ollama_route_request(model),
            LLMRequest(model=model, messages=[{"role": "user", "content": "work"}]),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=boundary,
        )

    assert boundary.started is False
    ready.assert_not_called()
    provider.complete_exact_model.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaign_router_rechecks_registry_after_final_fence(
    tmp_path,
) -> None:
    model = "minimax-m3:cloud"
    original = OllamaProvider(
        base_url="https://ollama.com", model=model, api_key="fixture-key"
    )
    substitute = OllamaProvider(
        base_url="https://ollama.com", model=model, api_key="fixture-key"
    )
    original.complete_exact_model = AsyncMock()
    substitute.complete_exact_model = AsyncMock()
    router = ModelRouter(
        {ProviderType.OLLAMA: original},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    ready = MagicMock()

    async def substitute_during_fence() -> None:
        router._providers[ProviderType.OLLAMA] = substitute

    boundary = CampaignProviderEffectBoundary(substitute_during_fence, ready)
    with pytest.raises(RuntimeError, match="provider boundary changed"):
        await router.complete_for_task(
            _exact_ollama_route_request(model),
            LLMRequest(model=model, messages=[{"role": "user", "content": "work"}]),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=boundary,
        )

    assert boundary.started is False
    ready.assert_not_called()
    original.complete_exact_model.assert_not_awaited()
    substitute.complete_exact_model.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaign_router_ready_callback_failure_remains_preeffect(
    tmp_path,
) -> None:
    model = "minimax-m3:cloud"
    provider = OllamaProvider(
        base_url="https://ollama.com", model=model, api_key="fixture-key"
    )
    provider.complete_exact_model = AsyncMock()
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    ready = MagicMock(side_effect=RuntimeError("reservation CAS failed"))
    boundary = CampaignProviderEffectBoundary(AsyncMock(), ready)

    with pytest.raises(RuntimeError, match="reservation CAS failed"):
        await router.complete_for_task(
            _exact_ollama_route_request(model),
            LLMRequest(model=model, messages=[{"role": "user", "content": "work"}]),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=boundary,
        )

    assert boundary.started is False
    ready.assert_called_once_with()
    provider.complete_exact_model.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaign_router_boundary_and_carrier_are_inseparable(
    tmp_path,
) -> None:
    provider = AsyncMock()
    provider.available = True
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    model = "minimax-m3:cloud"
    request = LLMRequest(model=model, messages=[{"role": "user", "content": "work"}])

    with pytest.raises(RuntimeError, match="inseparable"):
        await router.complete_for_task(
            _exact_ollama_route_request(model),
            request,
            available_provider_types=[ProviderType.OLLAMA],
        )
    with pytest.raises(RuntimeError, match="inseparable"):
        await router.complete_for_task(
            ProviderRouteRequest(
                action_name="generic",
                risk_score=0.1,
                uncertainty=0.1,
                novelty=0.1,
                urgency=0.1,
                expected_impact=0.1,
                context={"preferred_provider": "ollama"},
            ),
            request,
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=_allow_campaign_provider_effect(),
        )
    provider.complete.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("served_provider", "served_model", "message"),
    [
        ("anthropic", "minimax-m3:cloud", "response provider"),
        ("", "minimax-m3:cloud", "response provider"),
        ("ollama", "foreign-model:cloud", "response model"),
        ("ollama", "", "response model"),
    ],
)
async def test_campaign_router_rejects_wrong_identity_before_success_evidence(
    served_provider: str,
    served_model: str,
    message: str,
    tmp_path,
) -> None:
    class _IdentityProvider:
        available = True

        def __init__(self, provider: str, model: str) -> None:
            self.provider = provider
            self.model = model
            self.calls = 0
            self._model = "minimax-m3:cloud"
            self._transport_mode = "cloud_api"
            self._base_url = "https://ollama.com"

        async def complete_exact_model(self, _request):
            self.calls += 1
            return SimpleNamespace(
                content="untrusted served identity",
                provider=self.provider,
                model=self.model,
                usage={},
            )

    exact = _IdentityProvider(served_provider, served_model)
    foreign = _IdentityProvider("anthropic", "foreign-model")
    audit_path = tmp_path / "routing.jsonl"
    router = ModelRouter(
        {
            ProviderType.OLLAMA: exact,
            ProviderType.ANTHROPIC: foreign,
        },
        retry_policy=RetryPolicy(max_attempts=5),
        routing_audit_path=audit_path,
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    ready = MagicMock()
    boundary = CampaignProviderEffectBoundary(AsyncMock(), ready)

    with pytest.raises(RuntimeError, match=message):
        await router.complete_for_task(
            _exact_ollama_route_request("minimax-m3:cloud"),
            LLMRequest(
                model="minimax-m3:cloud",
                messages=[{"role": "user", "content": "bounded evidence"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=boundary,
        )

    assert exact.calls == 1
    assert foreign.calls == 0
    assert boundary.started is True
    ready.assert_called_once_with()
    assert router._session_affinity == {}
    assert all(reward <= 0 for reward in router._provider_rewards.values())
    audit = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert audit
    assert {record["result"] for record in audit} == {"failed"}


@pytest.mark.asyncio
async def test_campaign_router_snapshots_attested_response_before_success_await(
    tmp_path,
) -> None:
    model = "minimax-m3:cloud"
    trusted_response = LLMResponse(
        content="trusted campaign result",
        provider="ollama",
        model=model,
        usage={
            "prompt_tokens": 4,
            "completion_tokens": 6,
            "total_tokens": 10,
        },
        tool_calls=[{"id": "trusted", "name": "bounded", "arguments": "{}"}],
        stop_reason="stop",
    )

    class _RetainedResponseProvider:
        available = True
        _model = model
        _transport_mode = "cloud_api"
        _base_url = "https://ollama.com"

        def __init__(self) -> None:
            self.response = trusted_response
            self.calls = 0

        async def complete_exact_model(self, _request):
            self.calls += 1
            return self.response

    provider = _RetainedResponseProvider()
    audit_path = tmp_path / "routing.jsonl"
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        routing_audit_path=audit_path,
        learning_enabled=True,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    success_telemetry_entered = asyncio.Event()
    success_telemetry_release = asyncio.Event()
    attempt_outcomes: list[dict] = []
    route_outcomes: list[dict] = []

    async def block_success_telemetry(**kwargs) -> None:
        attempt_outcomes.append(dict(kwargs))
        if kwargs["success"]:
            success_telemetry_entered.set()
            await success_telemetry_release.wait()

    async def capture_route_telemetry(**kwargs) -> None:
        route_outcomes.append(dict(kwargs))

    router._record_provider_attempt_outcome = block_success_telemetry
    router._record_route_execution_telemetry = capture_route_telemetry
    route_request = _exact_ollama_route_request(model)
    route_request.context["session_id"] = "campaign-session"

    pending = asyncio.create_task(
        router.complete_for_task(
            route_request,
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "bounded evidence"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
            campaign_effect_boundary=_allow_campaign_provider_effect(),
        )
    )
    await asyncio.wait_for(success_telemetry_entered.wait(), timeout=1)

    trusted_response.content = "foreign mutation"
    trusted_response.provider = "anthropic"
    trusted_response.model = "foreign-model:cloud"
    trusted_response.usage["total_tokens"] = 199_999
    trusted_response.tool_calls[0]["name"] = "foreign"
    trusted_response.stop_reason = "mutated"
    success_telemetry_release.set()

    decision, response = await asyncio.wait_for(pending, timeout=1)

    assert provider.calls == 1
    assert response is not trusted_response
    assert response == LLMResponse(
        content="trusted campaign result",
        provider="ollama",
        model=model,
        usage={
            "prompt_tokens": 4,
            "completion_tokens": 6,
            "total_tokens": 10,
        },
        tool_calls=[{"id": "trusted", "name": "bounded", "arguments": "{}"}],
        stop_reason="stop",
    )
    assert decision.selected_provider is ProviderType.OLLAMA
    assert attempt_outcomes[-1]["provider"] is ProviderType.OLLAMA
    assert attempt_outcomes[-1]["model"] == model
    assert attempt_outcomes[-1]["total_tokens"] == 10
    assert route_outcomes[-1]["selected_provider"] is ProviderType.OLLAMA
    assert route_outcomes[-1]["selected_model"] == model
    assert route_outcomes[-1]["response_model"] == model
    assert router._provider_rewards[f"ollama:{model}"] == pytest.approx(0.99995)
    assert router._session_affinity["campaign-session"]["provider"] is ProviderType.OLLAMA
    assert router._session_affinity["campaign-session"]["model"] == model
    audit = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert audit[-1]["provider_selected"] == "ollama"
    assert audit[-1]["model_selected"] == model
    assert audit[-1]["result"] == "success"


@pytest.mark.asyncio
async def test_generic_provider_failure_retains_configured_retry_policy(tmp_path) -> None:
    class _FailingProvider:
        available = True

        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, _request):
            self.calls += 1
            raise RuntimeError("generic provider failed")

    provider = _FailingProvider()
    router = ModelRouter(
        {ProviderType.OLLAMA: provider},
        retry_policy=RetryPolicy(
            max_attempts=2,
            base_delay_seconds=0,
            backoff_multiplier=1,
            max_delay_seconds=0,
            jitter_seconds=0,
        ),
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    route_request = ProviderRouteRequest(
        action_name="generic-task",
        risk_score=0.1,
        uncertainty=0.1,
        novelty=0.1,
        urgency=0.1,
        expected_impact=0.1,
        context={"preferred_provider": "ollama"},
    )

    with pytest.raises(RuntimeError, match="All providers failed"):
        await router.complete_for_task(
            route_request,
            LLMRequest(
                model="generic-model",
                messages=[{"role": "user", "content": "generic work"}],
            ),
            available_provider_types=[ProviderType.OLLAMA],
        )

    assert provider.calls == 2


def test_create_default_router():
    router = create_default_router()
    assert router.get_provider(ProviderType.ANTHROPIC) is not None
    assert router.get_provider(ProviderType.OPENAI) is not None
    assert router.get_provider(ProviderType.GROQ) is not None
    assert router.get_provider(ProviderType.SILICONFLOW) is not None
    assert router.get_provider(ProviderType.TOGETHER) is not None
    assert router.get_provider(ProviderType.FIREWORKS) is not None
    assert router.get_provider(ProviderType.NVIDIA_NIM) is not None
    assert router.get_provider(ProviderType.CLAUDE_CODE) is not None
    assert router.get_provider(ProviderType.CODEX) is not None
    assert router.get_provider(ProviderType.OPENROUTER_FREE) is not None


def test_groq_provider_init():
    p = GroqProvider(api_key="test-key")
    assert p._api_key == "test-key"


def test_siliconflow_provider_init():
    p = SiliconFlowProvider(api_key="test-key")
    assert p._api_key == "test-key"


def test_together_provider_init():
    p = TogetherProvider(api_key="test-key")
    assert p._api_key == "test-key"


def test_fireworks_provider_init():
    p = FireworksProvider(api_key="test-key")
    assert p._api_key == "test-key"


def test_nvidia_nim_provider_no_key():
    p = NVIDIANIMProvider(api_key=None)
    p._api_key = None
    with pytest.raises(RuntimeError, match="NVIDIA_NIM_API_KEY"):
        p._headers_or_raise()


def test_nvidia_nim_provider_uses_canonical_default_model():
    p = NVIDIANIMProvider(api_key="test-key")
    assert p._default_model == default_model(ProviderType.NVIDIA_NIM)


def test_nvidia_nim_provider_resolves_default_via_canonical_helper(monkeypatch):
    monkeypatch.setattr(
        "dharma_swarm.providers.canonical_default_model",
        lambda provider: "nim-from-helper",
    )
    p = NVIDIANIMProvider(api_key="test-key")
    assert p._default_model == "nim-from-helper"


# --- ClaudeCodeProvider tests ---


def test_claude_code_provider_init():
    p = ClaudeCodeProvider(timeout=120, working_dir="/tmp/test")
    assert p._timeout == 120
    assert p._working_dir == "/tmp/test"


def test_claude_code_provider_default_dir():
    p = ClaudeCodeProvider()
    assert "dharma_swarm" in p._working_dir


@pytest.mark.asyncio
async def test_claude_code_provider_builds_prompt():
    """Verify prompt is assembled from system + user messages."""
    request = LLMRequest(
        model="claude-code",
        messages=[
            {"role": "user", "content": "Do the thing"},
            {"role": "assistant", "content": "OK"},
            {"role": "user", "content": "Now check results"},
        ],
        system="You are a test agent.",
    )

    captured_prompt = None

    async def fake_exec(*args, **kwargs):
        nonlocal captured_prompt
        # args: "claude", "-p", <prompt>, "--output-format", "text"
        captured_prompt = args[2]

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"done", b""))
        mock_proc.returncode = 0
        mock_proc.terminate = AsyncMock()
        return mock_proc

    provider = ClaudeCodeProvider(timeout=10)
    with patch("dharma_swarm.providers.asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = await provider.complete(request)

    assert captured_prompt is not None
    assert "You are a test agent." in captured_prompt
    assert "Do the thing" in captured_prompt
    assert "Now check results" in captured_prompt
    # Assistant messages should NOT be included
    assert "OK" not in captured_prompt
    assert result.content == "done"
    assert result.model == "claude-code"


@pytest.mark.asyncio
async def test_claude_code_provider_timeout():
    """Verify timeout returns a TIMEOUT response instead of raising."""

    async def fake_exec(*args, **kwargs):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_proc.terminate = AsyncMock()
        return mock_proc

    provider = ClaudeCodeProvider(timeout=1)
    with patch("dharma_swarm.providers.asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = await provider.complete(
            LLMRequest(model="claude-code", messages=[{"role": "user", "content": "test"}])
        )

    assert "TIMEOUT" in result.content
    assert result.model == "claude-code"


@pytest.mark.asyncio
async def test_claude_code_provider_error():
    """Verify non-zero exit code is a provider failure, not a fake completion."""

    async def fake_exec(*args, **kwargs):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"something broke"))
        mock_proc.returncode = 1
        mock_proc.terminate = AsyncMock()
        return mock_proc

    provider = ClaudeCodeProvider(timeout=10)
    with patch("dharma_swarm.providers.asyncio.create_subprocess_exec", side_effect=fake_exec):
        with pytest.raises(RuntimeError, match="claude-code exited 1"):
            await provider.complete(
                LLMRequest(model="claude-code", messages=[{"role": "user", "content": "test"}])
            )


@pytest.mark.asyncio
async def test_claude_code_provider_nonzero_stdout_is_failure():
    """Auth errors can arrive on stdout; they must not complete a task."""

    async def fake_exec(*args, **kwargs):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"Failed to authenticate. API Error: 401", b"")
        )
        mock_proc.returncode = 1
        mock_proc.terminate = AsyncMock()
        return mock_proc

    provider = ClaudeCodeProvider(timeout=10)
    with patch("dharma_swarm.providers.asyncio.create_subprocess_exec", side_effect=fake_exec):
        with pytest.raises(RuntimeError, match="Failed to authenticate"):
            await provider.complete(
                LLMRequest(model="claude-code", messages=[{"role": "user", "content": "test"}])
            )


@pytest.mark.asyncio
async def test_claude_code_provider_truncates_at_50000():
    """Verify output is truncated to 50000 chars (not the old 5000)."""
    big_output = b"x" * 100_000

    async def fake_exec(*args, **kwargs):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(big_output, b""))
        mock_proc.returncode = 0
        mock_proc.terminate = AsyncMock()
        return mock_proc

    provider = ClaudeCodeProvider(timeout=10)
    with patch("dharma_swarm.providers.asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = await provider.complete(
            LLMRequest(model="claude-code", messages=[{"role": "user", "content": "test"}])
        )

    assert len(result.content) == 50_000


@pytest.mark.asyncio
async def test_subprocess_output_not_truncated_at_5000():
    """Verify that 10000-char output is preserved (old bug was truncating at 5000)."""
    big_output = b"y" * 10_000

    async def fake_exec(*args, **kwargs):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(big_output, b""))
        mock_proc.returncode = 0
        mock_proc.terminate = AsyncMock()
        return mock_proc

    provider = ClaudeCodeProvider(timeout=10)
    with patch("dharma_swarm.providers.asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = await provider.complete(
            LLMRequest(model="claude-code", messages=[{"role": "user", "content": "test"}])
        )

    assert len(result.content) > 5000
    assert len(result.content) == 10_000


# --- CodexProvider tests ---


def test_codex_provider_init():
    p = CodexProvider(timeout=60, working_dir="/tmp/test")
    assert p._timeout == 60
    assert p._cli_command == "codex"
    assert p._cli_label == "codex"


def test_codex_provider_cli_args():
    p = CodexProvider()
    args = p._build_cli_args("test prompt")
    # The resolved command may be an absolute path (e.g. /usr/local/bin/codex)
    assert args[0].endswith("codex")
    assert args[1] == "exec"
    assert "--dangerously-bypass-approvals-and-sandbox" in args
    assert "test prompt" in args


@pytest.mark.asyncio
async def test_codex_provider_complete():
    """Verify Codex spawns subprocess and returns result."""

    async def fake_exec(*args, **kwargs):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"codex result", b""))
        mock_proc.returncode = 0
        mock_proc.terminate = AsyncMock()
        return mock_proc

    provider = CodexProvider(timeout=10)
    with patch("dharma_swarm.providers.asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = await provider.complete(
            LLMRequest(model="codex", messages=[{"role": "user", "content": "test"}])
        )

    assert result.content == "codex result"
    assert result.model == "codex"


# --- OpenRouterFreeProvider tests ---


def test_openrouter_free_provider_init():
    p = OpenRouterFreeProvider(api_key="test-key")
    assert p._api_key == "test-key"
    # Without explicit model, _preferred_model is None (resolved at call time)
    assert p._preferred_model is None
    # With explicit model, it's stored
    p2 = OpenRouterFreeProvider(api_key="test-key", model="meta-llama/llama-3.3-70b-instruct:free")
    assert p2._preferred_model == "meta-llama/llama-3.3-70b-instruct:free"


def test_openrouter_free_no_key():
    p = OpenRouterFreeProvider(api_key=None)
    # Clear env to test
    with patch.dict("os.environ", {}, clear=True):
        p._api_key = None
        with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
            p._client_or_raise()


def test_openrouter_free_auto_discovery():
    """OpenRouterFreeProvider should auto-discover free models at runtime."""
    import asyncio

    async def _discover():
        return await OpenRouterFreeProvider.get_free_models()

    models = asyncio.run(_discover())
    assert len(models) >= 3, f"Expected >=3 free models, got {len(models)}"
    for model in models:
        assert model.endswith(":free"), f"Non-free model: {model}"


# --- Memory Survival Directive Tests (IMPL-SAFETY) ---


def test_memory_survival_directive_in_subprocess_prompt():
    """Memory survival directive is injected into subprocess prompts."""
    provider = ClaudeCodeProvider(timeout=10)
    request = LLMRequest(
        model="claude-code",
        messages=[{"role": "user", "content": "Do a thing"}],
        system="You are a test agent.",
    )
    prompt = provider._build_prompt(request)
    assert "CONTEXT WILL BE DESTROYED" in prompt
    assert "externalize" in prompt.lower()


def test_memory_survival_directive_content():
    """Directive contains all required elements."""
    from dharma_swarm.providers import MEMORY_SURVIVAL_DIRECTIVE
    assert "MEMORY SURVIVAL" in MEMORY_SURVIVAL_DIRECTIVE
    assert "~/.dharma/shared/" in MEMORY_SURVIVAL_DIRECTIVE
    assert "~/.dharma/witness/" in MEMORY_SURVIVAL_DIRECTIVE
    assert "knowledge loss" in MEMORY_SURVIVAL_DIRECTIVE.lower()


@pytest.mark.asyncio
async def test_model_router_injects_survival_directive():
    """ModelRouter.complete injects survival directive into system prompt."""
    captured_request = None

    class CapturingProvider(AnthropicProvider):
        async def complete(self, request):
            nonlocal captured_request
            captured_request = request
            return LLMResponse(content="ok", model="mock")

    router = ModelRouter({ProviderType.ANTHROPIC: CapturingProvider(api_key="test")})
    request = LLMRequest(
        model="test",
        messages=[{"role": "user", "content": "hi"}],
        system="You are a coder.",
    )
    await router.complete(ProviderType.ANTHROPIC, request)
    assert captured_request is not None
    assert "CONTEXT WILL BE DESTROYED" in captured_request.system


@pytest.mark.asyncio
async def test_ollama_keyless_local_degrades_cloud_model(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    p = OllamaProvider()
    seen: dict[str, str] = {}

    async def fake_native(model, messages, request):
        seen["model"] = model
        return SimpleNamespace(content="ok")

    monkeypatch.setattr(p, "_complete_native", fake_native)
    request = LLMRequest(
        model="glm-5:cloud",
        messages=[{"role": "user", "content": "hi"}],
    )
    await p.complete(request)
    assert seen["model"] == p.default_model
    assert not seen["model"].endswith(":cloud")


def test_ollama_native_messages_coerce_string_tool_arguments():
    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "f", "arguments": '{"x": 1}'}}],
        },
        {"role": "tool", "content": "42"},
    ]
    fixed = OllamaProvider._native_messages(messages)
    assert fixed[1]["tool_calls"][0]["function"]["arguments"] == {"x": 1}
    assert fixed[0] == messages[0]


def test_ollama_native_messages_bad_json_arguments_become_empty_object():
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "f", "arguments": "{broken"}}],
        }
    ]
    fixed = OllamaProvider._native_messages(messages)
    assert fixed[0]["tool_calls"][0]["function"]["arguments"] == {}
