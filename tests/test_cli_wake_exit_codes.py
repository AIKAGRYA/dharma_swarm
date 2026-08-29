"""``cli_wake``: canonical fallback chain, ``--provider`` override, real exit codes, receipts.

Seam under test (Gate D routing-canon §2/§3): ``AutonomousAgent._call_anthropic``
must walk ``(ANTHROPIC, CLAUDE_CODE) + PREFERRED_LOW_COST_RUNTIME_PROVIDERS`` and
``cli_wake`` must return a real exit code and append one receipt row per wake.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import dharma_swarm.autonomous_agent as autonomous_agent_module
from dharma_swarm.agent_memory import AgentMemoryBank
from dharma_swarm.autonomous_agent import AutonomousAgent, cli_wake
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.runtime_provider import RuntimeProviderConfig

_CLAUDE_CFG = RuntimeProviderConfig(
    provider=ProviderType.ANTHROPIC,
    default_model="claude-test",
    transport_mode="claude_code",
    available=True,
)
_OLLAMA_CFG = RuntimeProviderConfig(
    provider=ProviderType.OLLAMA,
    default_model="glm-5.1:cloud",
    transport_mode="cloud_api",
    available=True,
)


class _AnswerProvider:
    def __init__(self, label: str, seen: list[LLMRequest]) -> None:
        self.label = label
        self.seen = seen

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.seen.append(request)
        return LLMResponse(
            content=self.label,
            model=request.model,
            usage={"prompt_tokens": 7, "completion_tokens": 3},
            stop_reason="end_turn",
        )

    async def close(self) -> None:
        return None


class _DeadProvider:
    def __init__(self, label: str) -> None:
        self.label = label

    async def complete(self, request: LLMRequest) -> LLMResponse:
        del request
        raise RuntimeError(f"{self.label} lane down")

    async def close(self) -> None:
        return None


@pytest.fixture
def receipts_path(monkeypatch, tmp_path: Path) -> Path:
    """Isolate every side effect of a real ``wake`` except the LLM chain."""
    path = tmp_path / "logs" / "wake_receipts.jsonl"
    monkeypatch.setattr(
        autonomous_agent_module, "_wake_receipts_path", lambda: path, raising=False,
    )
    for name in ("load", "save", "remember"):
        monkeypatch.setattr(AgentMemoryBank, name, AsyncMock())
    monkeypatch.setattr(AgentMemoryBank, "get_working_context", AsyncMock(return_value=""))
    monkeypatch.setattr(AutonomousAgent, "_check_inbox", AsyncMock(return_value=[]))
    monkeypatch.setattr(AutonomousAgent, "_ack_inbox", AsyncMock())
    monkeypatch.setattr(AutonomousAgent, "_save_run_report", AsyncMock())
    return path


def _receipt_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.asyncio
async def test_wake_falls_through_to_funded_lane_and_exits_zero(
    receipts_path: Path, monkeypatch,
) -> None:
    # Claude lanes unavailable (not in the resolved chain); one funded lane answers.
    monkeypatch.setattr(
        autonomous_agent_module,
        "preferred_runtime_provider_configs",
        lambda **_kw: [_OLLAMA_CFG],
    )
    seen: list[LLMRequest] = []
    attempted: list[ProviderType] = []

    def _factory(config: RuntimeProviderConfig) -> _AnswerProvider:
        attempted.append(config.provider)
        return _AnswerProvider("PONG", seen)

    monkeypatch.setattr(autonomous_agent_module, "create_runtime_provider", _factory)

    code = await cli_wake("witness", "Reply with exactly the word PONG and stop.")

    assert code == 0
    assert attempted == [ProviderType.OLLAMA]
    # The funded lane gets its own model_defaults model, never the Claude id.
    assert seen[0].model == "glm-5.1:cloud"
    rows = _receipt_rows(receipts_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["agent"] == "witness"
    assert row["provider_won"] == "ollama"
    assert row["model"] == "glm-5.1:cloud"
    assert row["exit_code"] == 0
    assert row["errors"]["count"] == 0
    assert row["turns"] == 1
    assert row["tokens"] == 10
    assert len(row["task_sha256"]) == 12


@pytest.mark.asyncio
async def test_wake_all_lanes_dead_exits_one_with_receipt(
    receipts_path: Path, monkeypatch,
) -> None:
    monkeypatch.setattr(
        autonomous_agent_module,
        "preferred_runtime_provider_configs",
        lambda **_kw: [_CLAUDE_CFG, _OLLAMA_CFG],
    )
    attempted: list[ProviderType] = []

    def _factory(config: RuntimeProviderConfig) -> _DeadProvider:
        attempted.append(config.provider)
        return _DeadProvider(config.provider.value)

    monkeypatch.setattr(autonomous_agent_module, "create_runtime_provider", _factory)

    code = await cli_wake("witness", "anything")

    assert code == 1
    assert attempted == [ProviderType.ANTHROPIC, ProviderType.OLLAMA]
    rows = _receipt_rows(receipts_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["exit_code"] == 1
    assert row["provider_won"] is None
    assert row["errors"]["count"] >= 1
    assert "ollama lane down" in row["errors"]["first"]


@pytest.mark.asyncio
async def test_identity_model_overrides_only_claude_lanes(
    receipts_path: Path, monkeypatch,
) -> None:
    captured: dict = {}

    def _pref(**kwargs) -> list[RuntimeProviderConfig]:
        captured.update(kwargs)
        return [_OLLAMA_CFG]

    monkeypatch.setattr(
        autonomous_agent_module, "preferred_runtime_provider_configs", _pref,
    )
    monkeypatch.setattr(
        autonomous_agent_module,
        "create_runtime_provider",
        lambda _cfg: _AnswerProvider("ok", []),
    )

    code = await cli_wake("witness", "t", model="claude-override-model")

    assert code == 0
    overrides = captured["model_overrides"]
    assert overrides[ProviderType.ANTHROPIC] == "claude-override-model"
    assert overrides[ProviderType.CLAUDE_CODE] == "claude-override-model"
    leaked = {
        k: v for k, v in overrides.items()
        if k not in (ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE) and v is not None
    }
    assert leaked == {}
    order = tuple(captured["provider_order"])
    assert order[:2] == (ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE)
    assert ProviderType.OLLAMA in order
    assert ProviderType.OPENROUTER in order
    assert len(order) == len(set(order))


@pytest.mark.asyncio
async def test_unknown_provider_exits_two_without_waking(
    receipts_path: Path, monkeypatch, capsys,
) -> None:
    wake = AsyncMock()
    monkeypatch.setattr(AutonomousAgent, "wake", wake)

    code = await cli_wake("witness", "t", provider="not-a-provider")

    assert code == 2
    wake.assert_not_awaited()
    assert "not-a-provider" in capsys.readouterr().out
    assert not receipts_path.exists()


@pytest.mark.asyncio
async def test_provider_override_routes_to_openrouter_lane(
    receipts_path: Path, monkeypatch,
) -> None:
    routed: list[str] = []

    async def _fake_openrouter(self, system, messages, tools):
        del system, messages, tools
        routed.append(self.identity.provider)
        return {
            "text": ["ok"],
            "tool_uses": [],
            "raw_content": "ok",
            "stop_reason": "end_turn",
            "tokens_in": 1,
            "tokens_out": 1,
        }

    async def _never(self, *_a, **_k):
        raise AssertionError("anthropic lane must not run under --provider openrouter")

    monkeypatch.setattr(AutonomousAgent, "_call_openrouter", _fake_openrouter)
    monkeypatch.setattr(AutonomousAgent, "_call_anthropic", _never)

    code = await cli_wake("witness", "t", provider="openrouter")

    assert code == 0
    assert routed == ["openrouter"]
    row = _receipt_rows(receipts_path)[0]
    assert row["provider_requested"] == "openrouter"
    assert row["exit_code"] == 0


@pytest.mark.asyncio
async def test_receipt_write_failure_never_masks_exit_code(
    receipts_path: Path, monkeypatch, tmp_path: Path,
) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        autonomous_agent_module,
        "_wake_receipts_path",
        lambda: blocker / "wake_receipts.jsonl",
        raising=False,
    )
    monkeypatch.setattr(
        autonomous_agent_module,
        "preferred_runtime_provider_configs",
        lambda **_kw: [_OLLAMA_CFG],
    )
    monkeypatch.setattr(
        autonomous_agent_module,
        "create_runtime_provider",
        lambda _cfg: _AnswerProvider("ok", []),
    )

    assert await cli_wake("witness", "t") == 0
