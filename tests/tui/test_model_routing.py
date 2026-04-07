"""Tests for TUI model routing helpers."""

from __future__ import annotations

from dharma_swarm.tui.model_routing import (
    default_target,
    detect_inline_switch_intent,
    fallback_chain,
    resolve_strategy,
    resolve_model_target,
    target_by_index,
)
from dharma_swarm.model_hierarchy import DEFAULT_MODELS
from dharma_swarm.models import ProviderType
from dharma_swarm.tui.model_routing import (
    ADAPTER_MAP,
    MODEL_TARGETS,
    all_targets,
)


def test_default_target_is_claude_sonnet() -> None:
    target = default_target()
    # Default is now GLM-5 (free frontier) per model_hierarchy.py
    assert target.provider_id == "ollama"
    assert target.model_id == "glm-5:cloud"


def test_resolve_alias_and_model_id() -> None:
    assert resolve_model_target("opus 4.6") is not None
    assert resolve_model_target("claude-opus-4-6") is not None
    assert resolve_model_target("openai/gpt-5-codex") is not None
    minimax = resolve_model_target("minimax")
    assert minimax is not None
    assert minimax.model_id == "minimax-m2.7:cloud"
    assert resolve_model_target("not-a-real-model") is None


def test_inline_switch_detection() -> None:
    target = detect_inline_switch_intent("hey, switch to codex 5.4")
    assert target is not None
    assert target.provider_id == "codex"
    assert target.model_id == "gpt-5.4"

    assert detect_inline_switch_intent("can you summarize this text?") is None


def test_fallback_chain_excludes_current() -> None:
    chain = fallback_chain("claude", "claude-sonnet-4-5")
    assert chain
    assert all(
        not (t.provider_id == "claude" and t.model_id == "claude-sonnet-4-5")
        for t in chain
    )


def test_strategy_aliases_resolve() -> None:
    assert resolve_strategy("fast") == "responsive"
    assert resolve_strategy("budget") == "cost"
    assert resolve_strategy("best") == "genius"
    assert resolve_strategy("unknown") is None


def test_target_by_index_maps_in_model_list_order() -> None:
    first = target_by_index(1)
    assert first is not None
    # First target is now GLM-5 (free frontier) per model_hierarchy.py
    assert first.alias == "glm-5"
    assert target_by_index(999) is None


def test_adapter_map_covers_all_terminal_adapters() -> None:
    adapter_ids = set(ADAPTER_MAP.values())
    assert adapter_ids == {"claude", "codex", "openrouter", "ollama"}


def test_targets_derived_from_hierarchy() -> None:
    targets = all_targets()
    assert len(targets) > 0
    for t in targets:
        matching_providers = [
            pt for pt, adapter in ADAPTER_MAP.items() if adapter == t.provider_id
        ]
        assert matching_providers, f"No ProviderType maps to adapter '{t.provider_id}'"
        hierarchy_models = {DEFAULT_MODELS.get(pt, "") for pt in matching_providers}
        assert t.model_id in hierarchy_models, (
            f"Target {t.alias} ({t.provider_id}:{t.model_id}) not found in "
            f"DEFAULT_MODELS for providers {matching_providers}. "
            f"Hierarchy has: {hierarchy_models}"
        )


def test_no_unreachable_targets() -> None:
    for t in all_targets():
        assert t.provider_id in {"claude", "codex", "openrouter", "ollama"}, (
            f"Target {t.alias} has provider_id '{t.provider_id}' "
            f"which has no terminal adapter"
        )


def test_ollama_targets_present() -> None:
    targets = all_targets()
    ollama_targets = [t for t in targets if t.provider_id == "ollama"]
    assert len(ollama_targets) >= 1, "No Ollama Cloud targets found"
    aliases = {t.alias for t in ollama_targets}
    assert "glm-5" in aliases, "GLM-5 missing from targets"
