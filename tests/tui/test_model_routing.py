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


def test_default_target_is_floor_claude() -> None:
    target = default_target()
    # The default chat brain is a current FLOOR Claude (claude-opus-5.0) on the
    # Claude-Max oauth lane — never a sub-floor model (operator demarcation).
    assert target.provider_id == "claude"
    assert target.model_id == "claude-opus-5.0"


def test_resolve_alias_and_model_id() -> None:
    assert resolve_model_target("opus 5") is not None
    assert resolve_model_target("claude-opus-5.0") is not None
    assert resolve_model_target("sonnet 5") is not None
    # gpt-5.5 floor lane resolvable.
    assert resolve_model_target("gpt-5.5") is not None
    kimi = resolve_model_target("kimi")
    assert kimi is not None
    assert kimi.alias == "kimi-k3"
    assert kimi.provider_id == "kimi_code"
    assert kimi.model_id == "k3"
    assert [provider.value for provider in kimi.pool_providers] == [
        "kimi_code",
        "moonshot",
        "openrouter",
    ]
    # minimax now resolves to the FLOOR M3, not the sub-floor M2.7.
    minimax = resolve_model_target("minimax")
    assert minimax is not None
    assert minimax.model_id == "minimax-m3:cloud"
    # No picker target ever resolves ONTO a sub-floor model_id — the grunt
    # path is unreachable from the picker. (Fuzzy alias matches may land on a
    # nearby FLOOR target, but never on a sub-floor model_id.)
    for probe in ("kimi-k2.5", "kimi-k2.7", "glm-5", "deepseek-v3.2", "minimax-m2.7"):
        hit = resolve_model_target(probe)
        if hit is not None:
            assert hit.model_id not in (
                "kimi-k2.5:cloud",
                "glm-5:cloud",
                "deepseek-v3.2:cloud",
                "minimax-m2.7:cloud",
            ), f"{probe!r} resolved onto sub-floor {hit.model_id!r}"
    assert resolve_model_target("not-a-real-model") is None


def test_inline_switch_detection() -> None:
    target = detect_inline_switch_intent("hey, switch to gpt 5.5")
    assert target is not None
    assert target.provider_id == "codex"
    assert target.model_id == "gpt-5.5"

    assert detect_inline_switch_intent("can you summarize this text?") is None


def test_fallback_chain_excludes_current() -> None:
    chain = fallback_chain("claude", "claude-opus-5.0")
    assert chain
    assert all(
        not (t.provider_id == "claude" and t.model_id == "claude-opus-5.0")
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
    # First target (default chat brain) is the current FLOOR Claude Opus 5.0.
    assert first.alias == "opus-5.0"
    assert target_by_index(999) is None


def test_picker_main_list_is_floor_only() -> None:
    """No target in the picker's main list projects a sub-floor pool entry —
    the operator's UNMISTAKABLE demarcation, enforced at the surface."""
    from dharma_swarm import model_pool
    from dharma_swarm.tui.model_routing import MODEL_TARGETS

    for t in MODEL_TARGETS:
        entry = model_pool.entry_for_model_id(t.model_id)
        if entry is not None:
            assert not entry.below_floor, (
                f"picker target {t.alias!r} leaks sub-floor entry {entry.id!r}"
            )


def test_kimi_k3_alias_prefers_first_party_route() -> None:
    kimi = resolve_model_target("k3")

    assert kimi is not None
    assert kimi.alias == "kimi-k3"
    assert kimi.provider_id == "kimi_code"
    assert kimi.model_id == "k3"
    assert [provider.value for provider in kimi.pool_providers] == [
        "kimi_code",
        "moonshot",
        "openrouter",
    ]
