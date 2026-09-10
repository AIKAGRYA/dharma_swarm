"""Focused truth-boundary tests for the Helm model policy projection."""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

from dharma_swarm import model_status
from dharma_swarm.terminal_bridge import TerminalBridge
from dharma_swarm.terminal_bridge_external_preview import KIMI_K3_MODEL_ID
from dharma_swarm.terminal_bridge_text import policy_target_key
from dharma_swarm.tui import model_routing

_FLOOR = model_routing.default_target()


def _projected_opus(*, generic_verified: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=_FLOOR.model_id,
        route_statuses=[
            SimpleNamespace(
                provider="claude_code",
                model_id=_FLOOR.model_id,
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
        "dharma_swarm.terminal_bridge_chat_policy.key_oracle.dispatchable_cached",
        lambda: {"claude_code"},
    )
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_chat_policy.model_status.floor_model_status",
        lambda: _floor_projection(_projected_opus(generic_verified=True)),
    )
    bridge = TerminalBridge()
    try:
        policy = bridge._build_model_policy_summary(
            selected_provider=_FLOOR.provider_id,
            selected_model=_FLOOR.model_id,
            strategy="responsive",
        )
        opus = next(
            target for target in policy["targets"] if target["alias"] == _FLOOR.alias
        )

        assert opus["usable_now"] is True
        assert opus["identity_verified"] is False
        assert opus["exact_model_proven"] is False
        assert opus["oracle_providers"] == ["claude_code"]
    finally:
        asyncio.run(bridge.close())


def test_no_dispatchable_terminal_lane_emits_typed_blocker(monkeypatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_chat_policy.key_oracle.dispatchable_cached",
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
        "dharma_swarm.terminal_bridge_chat_policy.key_oracle.dispatchable_cached",
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
                    served_model=_FLOOR.model_id,
                ),
            ),
        )
    )
    try:
        policy = bridge._build_model_policy_summary(
            selected_provider=_FLOOR.provider_id,
            selected_model=_FLOOR.model_id,
            strategy="responsive",
        )
        opus = next(
            target for target in policy["targets"] if target["alias"] == _FLOOR.alias
        )

        assert opus["usable_now"] is True
        assert opus["identity_verified"] is True
        assert opus["exact_model_proven"] is True
    finally:
        asyncio.run(bridge.close())


def test_evaluator_identity_does_not_expand_preview_authority(monkeypatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_chat_policy.key_oracle.dispatchable_cached",
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
        "dharma_swarm.terminal_bridge_chat_policy.key_oracle.dispatchable_cached",
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


def test_policy_build_never_spawns_claude_smoke(monkeypatch, tmp_path) -> None:
    """A fresh bridge renders from the dkeys cache; it never blocks on `claude -p`."""

    def _forbidden(**_kwargs):
        raise AssertionError("claude -p smoke spawned on the policy path")

    monkeypatch.setattr(
        "dharma_swarm.key_oracle._claude_code_dispatchable_now", _forbidden
    )
    monkeypatch.setattr("dharma_swarm.key_oracle.Path.home", lambda: tmp_path)
    monkeypatch.setattr("dharma_swarm.key_oracle.shutil.which", lambda name: None)
    monkeypatch.setattr("dharma_swarm.model_status._status_data", lambda: None)
    status_dir = tmp_path / ".dharma"
    status_dir.mkdir()
    (status_dir / "keys_status.json").write_text(
        json.dumps(
            {
                "last_test_ts": time.time(),
                "rows": [
                    {"name": "claude_code", "glyph": "✗", "status": "no session"},
                    {"name": "openrouter", "glyph": "✗", "status": "dead"},
                ],
            }
        ),
        encoding="utf-8",
    )
    bridge = TerminalBridge()
    try:
        policy = bridge._build_model_policy_summary(
            selected_provider=_FLOOR.provider_id,
            selected_model=_FLOOR.model_id,
            strategy="responsive",
        )
        assert policy["fallback_notice"]["kind"] == "no_usable_lane"
        assert bridge._chat_lanes(_FLOOR.provider_id, _FLOOR.model_id) == []
        assert "Unknown model target" in bridge._materialize_model_command("/model set zzz", "model:set zzz")
    finally:
        asyncio.run(bridge.close())


def test_model_set_key_resolves_against_listed_policy_order(monkeypatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.terminal_bridge_chat_policy.key_oracle.dispatchable_cached",
        lambda: {"claude_code", "kimi_code"},
    )
    monkeypatch.setattr("dharma_swarm.model_status._status_data", lambda: None)
    bridge = TerminalBridge()
    try:
        listing = bridge._materialize_model_command("/model list", "model:list")
        policy = bridge._build_model_policy_summary(
            selected_provider=_FLOOR.provider_id,
            selected_model=_FLOOR.model_id,
            strategy="responsive",
        )
        kimi_index = next(
            index
            for index, target in enumerate(policy["targets"])
            if target["route_id"] == f"kimi_code:{KIMI_K3_MODEL_ID}"
        )
        key = policy_target_key(kimi_index)
        assert key is not None and key not in {"j", "k"}
        assert f"({policy['targets'][kimi_index]['route_id']})" in listing
        assert f"| {key} |" in listing

        rendered = bridge._materialize_model_command(f"/model set {key}", f"model:set {key}")
        assert f"Route: kimi_code:{KIMI_K3_MODEL_ID}" in rendered
        assert "Unknown model target" in bridge._materialize_model_command("/model set j", "model:set j")
    finally:
        asyncio.run(bridge.close())
