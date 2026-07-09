"""Tests for conductor configurations."""

from __future__ import annotations

from dharma_swarm.conductors import (
    CONDUCTOR_CLAUDE_CONFIG,
    CONDUCTOR_CODEX_CONFIG,
    CONDUCTOR_CONFIGS,
    materialize_conductor_config,
)
from dharma_swarm.model_hierarchy import default_model as canonical_default_model
from dharma_swarm.models import AgentRole, ProviderType


class TestConductorConfigs:
    def test_two_conductors(self):
        assert len(CONDUCTOR_CONFIGS) == 2

    def test_claude_config(self):
        cfg = CONDUCTOR_CLAUDE_CONFIG
        assert cfg["name"] == "conductor_claude"
        assert cfg["role"] == AgentRole.CONDUCTOR
        # provider_type in the template is a static placeholder; the runtime
        # value is resolved at instantiation time by materialize_conductor_config.
        assert cfg["provider_type"] == ProviderType.CLAUDE_CODE
        assert cfg["model"] == canonical_default_model(ProviderType.ANTHROPIC)
        assert cfg["wake_interval_seconds"] == 3600.0
        assert cfg["max_turns"] == 15
        assert "v7" in cfg["system_prompt"].lower() or "non-negotiable" in cfg["system_prompt"].lower()

    def test_codex_config(self):
        cfg = CONDUCTOR_CODEX_CONFIG
        assert cfg["name"] == "conductor_codex"
        assert cfg["role"] == AgentRole.CONDUCTOR
        assert cfg["provider_type"] == ProviderType.CLAUDE_CODE
        # Both conductors derive model from canonical_default_model(); codex
        # (CLAUDE_CODE) resolves to the same opus default as the claude config.
        assert cfg["model"] == "claude-opus-4-6"
        assert cfg["wake_interval_seconds"] == 1800.0
        assert cfg["max_turns"] == 10

    def test_unique_names(self):
        names = [c["name"] for c in CONDUCTOR_CONFIGS]
        assert len(names) == len(set(names))

    def test_all_have_required_keys(self):
        required = {"name", "role", "provider_type", "model", "wake_interval_seconds", "system_prompt", "max_turns"}
        for cfg in CONDUCTOR_CONFIGS:
            assert required.issubset(cfg.keys()), f"Missing keys in {cfg['name']}"

    def test_system_prompts_nonempty(self):
        for cfg in CONDUCTOR_CONFIGS:
            assert len(cfg["system_prompt"]) > 100

    def test_materialize_conductor_config_resolves_runtime_provider(self, monkeypatch):
        monkeypatch.setattr("dharma_swarm.conductors.env_has_value", lambda *_args, **_kwargs: True)

        cfg = materialize_conductor_config(CONDUCTOR_CLAUDE_CONFIG)

        assert cfg["provider_type"] == ProviderType.ANTHROPIC
        assert cfg["model"] == canonical_default_model(ProviderType.ANTHROPIC)
        assert cfg["provider_fallbacks"] == [ProviderType.CLAUDE_CODE]

    def test_materialize_conductor_config_preserves_codex_lane(self, monkeypatch):
        monkeypatch.setattr("dharma_swarm.conductors.env_has_value", lambda *_args, **_kwargs: True)

        cfg = materialize_conductor_config(CONDUCTOR_CODEX_CONFIG)

        assert cfg["provider_type"] == ProviderType.ANTHROPIC
        assert cfg["model"] == canonical_default_model(ProviderType.CLAUDE_CODE)
        assert cfg["provider_fallbacks"] == [ProviderType.CLAUDE_CODE]

    def test_materialize_does_not_mutate_template(self, monkeypatch):
        monkeypatch.setattr("dharma_swarm.conductors.env_has_value", lambda *_args, **_kwargs: True)

        before = dict(CONDUCTOR_CLAUDE_CONFIG)
        materialize_conductor_config(CONDUCTOR_CLAUDE_CONFIG)

        assert CONDUCTOR_CLAUDE_CONFIG == before
        assert "provider_fallbacks" not in CONDUCTOR_CLAUDE_CONFIG
