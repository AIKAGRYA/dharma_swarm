"""Evolve auto/daemon provider resolution is honest, not hardwired OpenRouter.

Session-verified failure: dgc evolve daemon/auto called
swarm._router.get_provider(ProviderType.OPENROUTER) unconditionally, so
--single-model --model claude-code died on "OPENROUTER_API_KEY not set"
while the router's ClaudeCodeProvider lane worked in the same process.
The commands now resolve the lane serving the requested model
(terminal_commands/evolution.py:_resolve_evolution_provider).
"""

from __future__ import annotations

import pytest

from dharma_swarm.models import ProviderType
from dharma_swarm.terminal_commands import evolution
from dharma_swarm.terminal_commands.evolution import (
    _provider_candidates_for_model,
    _resolve_evolution_provider,
)


class _Provider:
    def __init__(self, available: bool = True) -> None:
        self.available = available


class _Router:
    def __init__(self, providers: dict[ProviderType, _Provider]) -> None:
        self._providers = providers

    def get_provider(self, provider_type: ProviderType) -> _Provider:
        return self._providers[provider_type]


# ---------------------------------------------------------------------------
# _provider_candidates_for_model
# ---------------------------------------------------------------------------


def test_claude_code_model_maps_only_to_claude_code_lane() -> None:
    assert _provider_candidates_for_model("claude-code") == [ProviderType.CLAUDE_CODE]
    assert _provider_candidates_for_model("claude_code") == [ProviderType.CLAUDE_CODE]


def test_claude_star_models_resolve_first_party_lanes() -> None:
    candidates = _provider_candidates_for_model("claude-sonnet-4-20250514")
    assert candidates[0] in {ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE}
    assert ProviderType.ANTHROPIC in candidates
    assert ProviderType.CLAUDE_CODE in candidates


def test_slash_model_falls_back_to_openrouter() -> None:
    assert ProviderType.OPENROUTER in _provider_candidates_for_model(
        "moonshotai/kimi-k2.5"
    )


# ---------------------------------------------------------------------------
# _resolve_evolution_provider
# ---------------------------------------------------------------------------


def test_single_model_claude_code_resolves_non_openrouter_lane() -> None:
    claude_lane = _Provider()
    router = _Router(
        {
            ProviderType.OPENROUTER: _Provider(available=False),
            ProviderType.CLAUDE_CODE: claude_lane,
        }
    )

    provider_type, provider = _resolve_evolution_provider(
        router, model="claude-code", single_model=True,
    )

    assert provider_type is ProviderType.CLAUDE_CODE
    assert provider is claude_lane


def test_single_model_fails_with_configured_provider_names() -> None:
    router = _Router(
        {
            ProviderType.GROQ: _Provider(),
            ProviderType.OPENROUTER: _Provider(available=False),
        }
    )

    with pytest.raises(RuntimeError) as excinfo:
        _resolve_evolution_provider(router, model="claude-code", single_model=True)

    message = str(excinfo.value)
    assert "claude-code" in message
    assert "groq" in message
    assert "openrouter" not in message.split("Configured providers")[1]


def test_multi_model_fallback_uses_first_available_registered_lane() -> None:
    ollama_lane = _Provider()
    router = _Router(
        {
            ProviderType.OLLAMA: ollama_lane,
            ProviderType.OPENROUTER: _Provider(available=False),
        }
    )

    provider_type, provider = _resolve_evolution_provider(
        router, model="", single_model=False,
    )

    assert provider_type is ProviderType.OLLAMA
    assert provider is ollama_lane


def test_no_available_providers_raises_clear_error() -> None:
    router = _Router({})

    with pytest.raises(RuntimeError, match=r"Configured providers: \[none\]"):
        _resolve_evolution_provider(router, model="", single_model=False)


# ---------------------------------------------------------------------------
# cmd_evolve_daemon wiring
# ---------------------------------------------------------------------------


def test_cmd_evolve_daemon_single_model_passes_router_resolved_lane(
    monkeypatch, capsys,
) -> None:
    captured: dict[str, object] = {}
    claude_lane = _Provider()

    class _Engine:
        _max_cycle_tokens = 0

        async def daemon_loop(self, think_provider, **kwargs) -> None:
            captured["think_provider"] = think_provider
            captured["router"] = kwargs.get("router")

    class _Swarm:
        _engine = _Engine()
        _router = _Router(
            {
                ProviderType.OPENROUTER: _Provider(available=False),
                ProviderType.CLAUDE_CODE: claude_lane,
            }
        )

        async def shutdown(self) -> None:
            return None

    async def _fake_get_swarm(state_dir: str = ".dharma") -> _Swarm:
        return _Swarm()

    monkeypatch.setattr(evolution, "_get_swarm", _fake_get_swarm)

    evolution.cmd_evolve_daemon(
        60.0, 0.6, "claude-code", 1, single_model=True, shadow=True,
    )

    assert captured["think_provider"] is claude_lane
    assert captured["router"] is None
    out = capsys.readouterr().out
    assert "claude-code via claude_code" in out


def test_cmd_evolve_daemon_reports_missing_provider_instead_of_key_error(
    monkeypatch, capsys,
) -> None:
    class _Engine:
        _max_cycle_tokens = 0

        async def daemon_loop(self, think_provider, **kwargs) -> None:
            raise AssertionError("daemon_loop must not run without a provider")

    class _Swarm:
        _engine = _Engine()
        _router = _Router({ProviderType.OPENROUTER: _Provider(available=False)})
        shutdown_called = False

        async def shutdown(self) -> None:
            _Swarm.shutdown_called = True

    async def _fake_get_swarm(state_dir: str = ".dharma") -> _Swarm:
        return _Swarm()

    monkeypatch.setattr(evolution, "_get_swarm", _fake_get_swarm)

    evolution.cmd_evolve_daemon(
        60.0, 0.6, "claude-code", 1, single_model=True, shadow=True,
    )

    out = capsys.readouterr().out
    assert "ERROR:" in out
    assert "claude-code" in out
    assert _Swarm.shutdown_called
