from __future__ import annotations

import json
from pathlib import Path

import scripts.runtime.live_ops_census as live_ops_census
from scripts.runtime.live_ops_census import build_live_ops_census


def _surface(payload: dict, surface_id: str) -> dict:
    return {surface["id"]: surface for surface in payload["surfaces"]}[surface_id]


def _write(path: Path, content: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_nats_port_open_without_handler_ack_is_not_hot_contact_healthy(tmp_path: Path) -> None:
    payload = build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        run_probes=False,
        processes={"nats": [{"pid": "4242", "command": "nats-server local-nats.conf"}]},
        ports={"nats": {"port": 4222, "listening": True, "evidence": "LISTEN"}},
    )

    nats = _surface(payload, "transport.nats")
    assert nats["status"] == "live"
    assert nats["state"] == "degraded"
    assert nats["state_reason"] == "port/process evidence only; hot-contact ack not proven"
    assert nats["authority_tier"] == "direct_probe"
    assert nats["ack_tier"] == "PORT_OPEN_ONLY"


def test_filesystem_a2a_queue_is_mirror_only_not_live_authority(tmp_path: Path) -> None:
    state = tmp_path / "state"
    _write(state / "a2a_bus" / "tasks" / "queue.jsonl", "{}\n")
    _write(state / "a2a_bus" / "receipts" / "agent" / "receipt.json", "{}")

    payload = build_live_ops_census(
        repo_root=tmp_path,
        state_root=state,
        run_probes=False,
    )

    mirror = _surface(payload, "evidence.a2a_mirrors")
    assert mirror["status"] == "live"
    assert mirror["state"] == "mirror_only"
    assert mirror["authority_tier"] == "mirror_only"
    assert mirror["ack_tier"] == "MIRROR_ONLY"
    assert mirror["operator_action_policy"] == "observe_only"


def test_tmux_presence_is_terminal_persistence_not_completion(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        live_ops_census,
        "_tmux_sessions",
        lambda _run_probes: ["dharma-control", "dharma-agents", "dharma-vps"],
    )

    payload = build_live_ops_census(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        run_probes=True,
        processes={},
        ports={},
    )

    tmux = _surface(payload, "tmux.cockpit")
    assert tmux["status"] == "live"
    assert tmux["state"] == "healthy"
    assert tmux["authority_tier"] == "direct_probe"
    assert tmux["operator_action_policy"] == "terminal_persistence_only"
    assert "completion" not in tmux["state_reason"].lower()


def test_stale_agni_receipt_downgrades_remote_state(tmp_path: Path) -> None:
    state = tmp_path / "state"
    _write(
        state / "remote_nodes" / "agni" / "kaizen_agni_latest.json",
        json.dumps({"updated_at": "2026-01-01T00:00:00Z", "status": "watching"}),
    )

    payload = build_live_ops_census(
        repo_root=tmp_path,
        state_root=state,
        run_probes=False,
    )

    agni = _surface(payload, "remote.agni")
    assert agni["status"] == "stale"
    assert agni["state"] == "stale"
    assert agni["freshness_state"] == "stale"
    assert agni["authority_tier"] == "human_required"
