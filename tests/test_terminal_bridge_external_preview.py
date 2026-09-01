from __future__ import annotations

from dharma_swarm.terminal_bridge_external_preview import (
    CLAUDE_FABLE_5_MODEL_ID,
    CLAUDE_SONNET_5_MODEL_ID,
    EXTERNAL_PREVIEW_ROUTES,
    GPT_5_6_SOL_MODEL_ID,
    GROK_4_6_MODEL_ID,
    KIMI_K3_MODEL_ID,
    explicit_external_preview_lane,
    default_external_preview_route,
    external_preview_route,
    external_preview_targets,
)


def test_external_preview_route_literals_are_exact() -> None:
    assert GPT_5_6_SOL_MODEL_ID == "gpt-5.6-sol"
    assert CLAUDE_FABLE_5_MODEL_ID == "claude-fable-5"
    assert CLAUDE_SONNET_5_MODEL_ID == "claude-sonnet-5"
    assert KIMI_K3_MODEL_ID == "k3"
    assert GROK_4_6_MODEL_ID == "grok-4.6"
    assert {route.route_id for route in EXTERNAL_PREVIEW_ROUTES} == {
        "codex_text:gpt-5.6-sol",
        "claude:claude-fable-5",
        "claude:claude-sonnet-5",
        "kimi_code:k3",
        "grok_oauth:grok-4.6",
    }


def test_external_preview_routes_never_claim_proof_or_on_call() -> None:
    assert all(route.preview_only for route in EXTERNAL_PREVIEW_ROUTES)
    assert all(not route.exact_model_proven for route in EXTERNAL_PREVIEW_ROUTES)
    assert all(not route.helm_on_call_eligible for route in EXTERNAL_PREVIEW_ROUTES)

    targets = external_preview_targets(
        {"claude", "codex_text", "grok_oauth", "kimi_code", "openrouter"}
    )
    assert all(target["picker_visible"] for target in targets)
    assert all(not target["available"] for target in targets)
    assert all(not target["exact_model_proven"] for target in targets)
    assert all(not target["helm_on_call_eligible"] for target in targets)
    grok = next(target for target in targets if target["alias"] == "grok-4.6")
    assert grok["selectable"] is True
    assert grok["availability_reason"] == "exact_model_unproven"

    sonnet = next(
        target for target in targets if target["alias"] == "claude-sonnet-5"
    )
    assert sonnet["selectable"] is True
    assert sonnet["route_state"] == "unverified"
    assert sonnet["preview_only"] is True
    assert sonnet["helm_on_call_eligible"] is False
    assert sonnet["exact_model_proven"] is False


def test_explicit_external_preview_is_singleton_and_never_aliases() -> None:
    lane = explicit_external_preview_lane(
        "codex_text",
        GPT_5_6_SOL_MODEL_ID,
        {"codex_text"},
    )
    assert lane is not None
    assert lane[:2] == ("codex_text", GPT_5_6_SOL_MODEL_ID)
    assert "no fallback" in lane[3]
    assert explicit_external_preview_lane(
        "codex_text", "gpt-5.6", {"codex_text"}
    ) is None
    assert explicit_external_preview_lane(
        "grok_oauth", GROK_4_6_MODEL_ID, {"grok_oauth"}
    ) == (
        "grok_oauth",
        GROK_4_6_MODEL_ID,
        {},
        "explicit account preview; exact route; no fallback",
    )
    assert explicit_external_preview_lane(
        "claude", CLAUDE_SONNET_5_MODEL_ID, {"claude"}
    ) == (
        "claude",
        CLAUDE_SONNET_5_MODEL_ID,
        {},
        "explicit account preview; exact route; no fallback",
    )
    assert explicit_external_preview_lane(
        "claude", CLAUDE_SONNET_5_MODEL_ID, {"codex_text"}
    ) is None
    assert external_preview_route("openrouter", "grok-4.6") is None
    assert default_external_preview_route({"codex_text", "kimi_code"}) == (
        "codex_text",
        GPT_5_6_SOL_MODEL_ID,
    )
