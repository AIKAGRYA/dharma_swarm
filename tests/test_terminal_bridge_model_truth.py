"""Focused truth-boundary tests for the Helm model policy projection."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from dharma_swarm import model_status
from dharma_swarm.terminal_bridge import TerminalBridge
from dharma_swarm.terminal_bridge_external_preview import KIMI_K3_MODEL_ID


def _projected_opus(*, generic_verified: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id="claude-opus-4.8",
        route_statuses=[
            SimpleNamespace(
                provider="claude_code",
                model_id="claude-opus-4.8",
                status="live_routable",
                reason=None,
            )
        ],
        verification=SimpleNamespace(
            status="verified" if generic_verified else "unverified"
        ),
        unavailable_reason=None,
        tier="floor",
        lane="test",
        status="available",
        available_routes=["claude_code"],
    )


def _floor_projection(model: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        oracle_state="fresh",
        live_providers=["claude_code"],
        models=[model],
    )


def test_generic_live_receipt_cannot_claim_evaluator_identity(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_chat_policy.key_oracle.dispatchable_now",
        lambda: {"claude_code"},
    )
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_chat_policy.model_status.floor_model_status",
        lambda: _floor_projection(_projected_opus(generic_verified=True)),
    )
    bridge = TerminalBridge()
    try:
        policy = bridge._build_model_policy_summary(
            selected_provider="claude",
            selected_model="claude-opus-4.8",
            strategy="responsive",
        )
        opus = next(
            target for target in policy["targets"] if target["alias"] == "opus-4.8"
        )

        assert opus["usable_now"] is True
        assert opus["identity_verified"] is False
        assert opus["exact_model_proven"] is False
        assert opus["oracle_providers"] == ["claude_code"]
    finally:
        asyncio.run(bridge.close())


def test_no_dispatchable_terminal_lane_emits_typed_blocker(monkeypatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_chat_policy.key_oracle.dispatchable_now",
        lambda: set(),
    )
    bridge = TerminalBridge()
    try:
        policy = bridge._build_model_policy_summary(
            selected_provider="openrouter",
            selected_model="dead-model",
            strategy="responsive",
        )

        assert policy["fallback_notice"] == {
            "kind": "no_usable_lane",
            "configured_route": "openrouter:dead-model",
            "selected_route": None,
            "message": (
                "No usable model lane for openrouter:dead-model "
                "(no dispatchable terminal route)"
            ),
        }
        assert not any(target["usable_now"] for target in policy["targets"])
    finally:
        asyncio.run(bridge.close())


def test_only_on_call_evaluator_evidence_verifies_target_identity(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_chat_policy.key_oracle.dispatchable_now",
        lambda: {"claude_code"},
    )
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_chat_policy.model_status.floor_model_status",
        lambda: _floor_projection(_projected_opus(generic_verified=False)),
    )
    bridge = TerminalBridge()
    bridge._helm_on_call_projection = SimpleNamespace(
        seats=(
            SimpleNamespace(
                verdict=model_status.RouteVerdict.ON_CALL,
                evidence=SimpleNamespace(
                    served_provider="claude_code",
                    served_model="claude-opus-4.8",
                ),
            ),
        )
    )
    try:
        policy = bridge._build_model_policy_summary(
            selected_provider="claude",
            selected_model="claude-opus-4.8",
            strategy="responsive",
        )
        opus = next(
            target for target in policy["targets"] if target["alias"] == "opus-4.8"
        )

        assert opus["usable_now"] is True
        assert opus["identity_verified"] is True
        assert opus["exact_model_proven"] is True
    finally:
        asyncio.run(bridge.close())


def test_evaluator_identity_does_not_expand_preview_authority(monkeypatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_chat_policy.key_oracle.dispatchable_now",
        lambda: {"kimi_code"},
    )
    bridge = TerminalBridge()
    bridge._helm_on_call_projection = SimpleNamespace(
        seats=(
            SimpleNamespace(
                verdict=model_status.RouteVerdict.ON_CALL,
                evidence=SimpleNamespace(
                    served_provider="kimi_code",
                    served_model=KIMI_K3_MODEL_ID,
                ),
            ),
        )
    )
    try:
        policy = bridge._build_model_policy_summary(
            selected_provider="kimi_code",
            selected_model=KIMI_K3_MODEL_ID,
            strategy="responsive",
        )
        kimi = next(
            target
            for target in policy["targets"]
            if target["route_id"] == f"kimi_code:{KIMI_K3_MODEL_ID}"
        )

        assert kimi["identity_verified"] is True
        assert kimi["preview_only"] is True
        assert kimi["helm_on_call_eligible"] is False
    finally:
        asyncio.run(bridge.close())


def test_model_set_refuses_adapter_present_but_oracle_dead_preview(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_chat_policy.key_oracle.dispatchable_now",
        lambda: set(),
    )
    bridge = TerminalBridge()
    try:
        result = bridge._run_action(
            "model.set",
            {"provider": "kimi_code", "model": KIMI_K3_MODEL_ID},
        )

        assert result["ok"] is False
        assert result["requested_route"] == f"kimi_code:{KIMI_K3_MODEL_ID}"
        assert bridge._selected_provider_id is None
        assert bridge._selected_model_id is None
    finally:
        asyncio.run(bridge.close())
