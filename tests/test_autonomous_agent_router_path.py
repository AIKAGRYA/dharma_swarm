"""AutonomousAgent routing: ModelRouter for openrouter stack; codex keeps direct cwd."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import dharma_swarm.autonomous_agent as autonomous_agent_module
import dharma_swarm.runtime_provider as runtime_provider_module
from dharma_swarm.autonomous_agent import (
    AgentIdentity,
    AutonomousAgent,
    _llm_response_to_react_shape,
)
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.providers import ModelRouter
from dharma_swarm.runtime_provider import RuntimeProviderConfig


class _DummyCompleter:
    def __init__(self, label: str) -> None:
        self.label = label

    async def complete(self, request: LLMRequest) -> LLMResponse:
        del request
        return LLMResponse(
            content=self.label,
            model="dummy",
            usage={"prompt_tokens": 10, "completion_tokens": 2},
            stop_reason="end_turn",
        )


@patch(
    "dharma_swarm.autonomous_agent.preferred_runtime_provider_configs",
    return_value=[
        RuntimeProviderConfig(
            provider=ProviderType.OPENROUTER_FREE,
            default_model="test/model",
            available=True,
        )
    ],
)
@pytest.mark.asyncio
async def test_openrouter_turn_uses_model_router_complete_for_task(_) -> None:
    router = ModelRouter({ProviderType.OPENROUTER_FREE: _DummyCompleter("routed-open")})
    ident = AgentIdentity(
        name="unit",
        role="test",
        system_prompt="sys",
        provider="openrouter",
        model="mistral/test",
    )
    agent = AutonomousAgent(ident, model_router=router)
    out = await agent._call_openrouter("s", [{"role": "user", "content": "hi"}], [])
    assert out["text"] == ["routed-open"]


@patch(
    "dharma_swarm.autonomous_agent.preferred_runtime_provider_configs",
    return_value=[
        RuntimeProviderConfig(
            provider=ProviderType.ANTHROPIC,
            default_model="claude-test",
            available=True,
        )
    ],
)
@pytest.mark.asyncio
async def test_anthropic_turn_uses_model_router_complete_for_task(_) -> None:
    captured: dict[str, LLMRequest | None] = {"req": None}

    class _Capture(_DummyCompleter):
        async def complete(self, request: LLMRequest) -> LLMResponse:
            captured["req"] = request
            return await super().complete(request)

    router = ModelRouter({ProviderType.ANTHROPIC: _Capture("routed-anthropic")})
    ident = AgentIdentity(
        name="unit",
        role="test",
        system_prompt="sys",
        provider="anthropic",
        model="claude-test",
    )
    defs = [
        {
            "name": "read_file",
            "description": "Read a file",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
        }
    ]
    agent = AutonomousAgent(ident, model_router=router)
    out = await agent._call_anthropic("s", [{"role": "user", "content": "hi"}], defs)
    assert out["text"] == ["routed-anthropic"]
    inner = captured["req"]
    assert inner is not None
    assert inner.tools == defs


@patch(
    "dharma_swarm.autonomous_agent.preferred_runtime_provider_configs",
    return_value=[
        RuntimeProviderConfig(
            provider=ProviderType.OPENROUTER_FREE,
            default_model="test/model",
            available=True,
        )
    ],
)
@patch(
    "dharma_swarm.autonomous_agent.create_runtime_provider",
)
@pytest.mark.asyncio
async def test_openrouter_turn_falls_back_when_router_misses_providers(
    mock_factory, _
) -> None:
    orphan = AsyncMock()

    async def _complete(req: LLMRequest) -> LLMResponse:
        del req
        return LLMResponse(
            content="legacy-fallback",
            model="fallback",
            usage={"prompt_tokens": 1, "completion_tokens": 2},
            stop_reason="end_turn",
        )

    orphan.complete = AsyncMock(side_effect=_complete)

    mock_factory.side_effect = lambda *_a, **_k: orphan

    router = MagicMock(spec=ModelRouter)

    # Simulates a router with no overlapping providers versus preferred chain.
    def _raise(provider: ProviderType) -> MagicMock:
        del provider
        raise KeyError()

    router.get_provider.side_effect = _raise

    spy = AsyncMock(wraps=router.complete_for_task)

    router.complete_for_task = spy

    ident = AgentIdentity(
        name="unit",
        role="test",
        system_prompt="sys",
        provider="openrouter",
        model="mistral/test",
    )
    agent = AutonomousAgent(ident, model_router=router)
    out = await agent._call_openrouter("s", [{"role": "user", "content": "hi"}], [])
    assert out["text"] == ["legacy-fallback"]
    spy.assert_not_awaited()
    mock_factory.assert_called_once()


@patch(
    "dharma_swarm.autonomous_agent.preferred_runtime_provider_configs",
    return_value=[
        RuntimeProviderConfig(
            provider=ProviderType.ANTHROPIC,
            default_model="claude-test",
            available=True,
        )
    ],
)
@patch(
    "dharma_swarm.autonomous_agent.create_runtime_provider",
)
@pytest.mark.asyncio
async def test_anthropic_turn_falls_back_to_runtime_provider_factory(
    mock_factory, _
) -> None:
    orphan = AsyncMock()
    defs = [
        {
            "name": "bash",
            "description": "Run a command",
            "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}},
        }
    ]

    async def _complete(req: LLMRequest) -> LLMResponse:
        assert req.model == "claude-test"
        assert req.tools == defs
        return LLMResponse(
            content="factory-anthropic",
            model="claude-test",
            usage={"input_tokens": 1, "output_tokens": 2},
            stop_reason="end_turn",
        )

    orphan.complete = AsyncMock(side_effect=_complete)
    mock_factory.side_effect = lambda *_a, **_k: orphan

    ident = AgentIdentity(
        name="unit",
        role="test",
        system_prompt="sys",
        provider="anthropic",
        model="claude-test",
    )
    agent = AutonomousAgent(ident)
    out = await agent._call_anthropic("s", [{"role": "user", "content": "hi"}], defs)
    assert out["text"] == ["factory-anthropic"]
    mock_factory.assert_called_once()


@pytest.mark.asyncio
async def test_anthropic_direct_attempts_shared_claude_cli_once(monkeypatch) -> None:
    monkeypatch.delenv("DHARMA_FORCE_ANTHROPIC_API", raising=False)
    monkeypatch.setattr(
        runtime_provider_module,
        "_resolve_cli_binary",
        lambda _name: "/fixture/bin/claude",
    )
    attempted: list[ProviderType] = []

    class _FailingProvider:
        async def complete(self, _request: LLMRequest) -> LLMResponse:
            raise RuntimeError("fixture CLI failure")

        async def close(self) -> None:
            return None

    def _factory(config: RuntimeProviderConfig) -> _FailingProvider:
        attempted.append(config.provider)
        return _FailingProvider()

    monkeypatch.setattr(autonomous_agent_module, "create_runtime_provider", _factory)
    agent = AutonomousAgent(
        AgentIdentity(
            name="unit",
            role="test",
            system_prompt="sys",
            provider="anthropic",
            model="claude-test",
        )
    )

    with pytest.raises(RuntimeError, match="fixture CLI failure"):
        await agent._call_anthropic(
            "system",
            [{"role": "user", "content": "hi"}],
            [],
        )

    # anthropic + claude_code collapse to the one shared claude binary: tried
    # exactly once, first; funded low-cost lanes (env-dependent) may follow.
    assert attempted[0] == ProviderType.ANTHROPIC
    claude_lanes = [
        p for p in attempted
        if p in (ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE)
    ]
    assert claude_lanes == [ProviderType.ANTHROPIC]
    assert agent._last_provider_won is None


@patch(
    "dharma_swarm.autonomous_agent.preferred_runtime_provider_configs",
)
@patch(
    "dharma_swarm.autonomous_agent.create_runtime_provider",
)
@pytest.mark.asyncio
async def test_codex_always_uses_create_runtime_provider_with_working_dir(
    mock_create, mock_configs,
) -> None:
    wd = "/tmp/codex-working-dir-test"

    def _pref(**kwargs: object) -> list[RuntimeProviderConfig]:
        assert kwargs.get("working_dir") == wd
        return [
            RuntimeProviderConfig(
                provider=ProviderType.CODEX,
                default_model="gpt-5",
                available=True,
                working_dir=str(kwargs.get("working_dir")),
            )
        ]

    mock_configs.side_effect = _pref

    orphan = AsyncMock()

    async def _done(req: LLMRequest) -> LLMResponse:
        del req
        return LLMResponse(content="cwdsave", model="m", usage={}, stop_reason="end_turn")

    orphan.complete = AsyncMock(side_effect=_done)
    mock_create.return_value = orphan

    spy_router = AsyncMock()
    router = MagicMock(spec=ModelRouter)
    router.complete_for_task = spy_router

    ident = AgentIdentity(
        name="unit",
        role="test",
        system_prompt="sys",
        provider="codex",
        model="gpt-5",
        working_directory=wd,
    )
    agent = AutonomousAgent(ident, model_router=router)
    out = await agent._call_codex("s", [{"role": "user", "content": "hi"}], [])
    assert out["text"] == ["cwdsave"]
    spy_router.assert_not_called()
    mock_create.assert_called_once()
    cfg = mock_create.call_args[0][0]
    assert cfg.working_dir == wd


@patch(
    "dharma_swarm.autonomous_agent.preferred_runtime_provider_configs",
    return_value=[
        RuntimeProviderConfig(
            provider=ProviderType.OPENROUTER_FREE,
            default_model="test/model",
            available=True,
        )
    ],
)
@pytest.mark.asyncio
async def test_openrouter_via_router_passes_tools_on_llm_request(_) -> None:
    captured: dict[str, LLMRequest | None] = {"req": None}

    class _Capture(_DummyCompleter):
        async def complete(self, request: LLMRequest) -> LLMResponse:
            captured["req"] = request
            return await super().complete(request)

    router = ModelRouter({ProviderType.OPENROUTER_FREE: _Capture("done")})
    ident = AgentIdentity(
        name="unit",
        role="test",
        system_prompt="sys",
        provider="openrouter",
        model="mistral/test",
    )
    defs = [
        {
            "name": "read_file",
            "description": "Read a file",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
        }
    ]
    agent = AutonomousAgent(ident, model_router=router)
    out = await agent._call_openrouter("s", [{"role": "user", "content": "hi"}], defs)
    assert out["text"] == ["done"]
    inner = captured["req"]
    assert inner is not None
    assert isinstance(inner.tools, list)
    assert inner.tools[0]["function"]["name"] == "read_file"


def test_openapi_tools_payload_matches_openai_function_format() -> None:
    tools = [
        {
            "name": "read_file",
            "description": "Read",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
        }
    ]
    pl = AutonomousAgent._openapi_tools_payload(tools)
    assert pl is not None
    assert pl[0]["type"] == "function"
    assert pl[0]["function"]["name"] == "read_file"
    assert pl[0]["function"]["parameters"]["type"] == "object"


def test_llm_response_to_react_shape_preserves_tool_names_and_inputs() -> None:
    payload = {"path": "/etc/hosts", "limit": 3}
    resp = LLMResponse(
        content="",
        model="m",
        tool_calls=[
            {"id": "call_01", "name": "read_file", "input": payload},
            {
                "id": "call_02",
                "name": "bash",
                "arguments": json.dumps({"cmd": "echo hi"}),
            },
        ],
        stop_reason="tool_use",
    )
    got = _llm_response_to_react_shape(resp)
    assert len(got["tool_uses"]) == 2
    assert got["tool_uses"][0]["name"] == "read_file"
    assert got["tool_uses"][0]["input"] == payload
    assert got["tool_uses"][1]["name"] == "bash"
    assert got["tool_uses"][1]["input"] == {"cmd": "echo hi"}

    blocks = got["raw_content"]
    assert isinstance(blocks, list)
    tu = next(b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use")
    assert tu["name"] == "read_file"
    assert tu["input"] == payload
