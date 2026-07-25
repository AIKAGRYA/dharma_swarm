from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

import pytest

from dharma_swarm.forge_lab import campaign_watchdog as watchdog


CAMPAIGN = "forge-lab-n30-to-1000-v1"
MANIFEST = f"sha256:{'a' * 64}"


def _stamp(delta_s: float = 0) -> str:
    value = datetime.now(timezone.utc) + timedelta(seconds=delta_s)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _config(
    state_root: Path,
    *,
    fence: int = 7,
    deadline_delta_s: float = 60,
    heartbeat_timeout_s: float = 1,
) -> watchdog.WatchdogConfig:
    return watchdog.WatchdogConfig(
        state_root=state_root,
        campaign_id=CAMPAIGN,
        manifest_digest=MANIFEST,
        fence=fence,
        deadline=_stamp(deadline_delta_s),
        heartbeat_timeout_s=heartbeat_timeout_s,
        poll_interval_s=min(0.02, heartbeat_timeout_s),
    )


def _arm(config: watchdog.WatchdogConfig, *, heartbeat_delta_s: float = 0) -> Path:
    control = watchdog.campaign_control_dir(config.state_root, config.campaign_id)
    control.mkdir(parents=True)
    gate = {
        "schema": watchdog.GATE_SCHEMA,
        "campaign_id": config.campaign_id,
        "manifest_digest": config.manifest_digest,
        "fence": config.fence,
        "dispatch_allowed": True,
        "authority_mode": "active",
        "revision": 1,
        "updated_at": _stamp(),
    }
    watchdog.authority_gate_path(config.state_root, config.campaign_id).write_text(
        json.dumps(gate), encoding="utf-8"
    )
    heartbeat = {
        "schema": watchdog.HEARTBEAT_SCHEMA,
        "campaign_id": config.campaign_id,
        "manifest_digest": config.manifest_digest,
        "fence": config.fence,
        "sequence": 1,
        "observed_at": _stamp(heartbeat_delta_s),
    }
    watchdog.heartbeat_path(config.state_root, config.campaign_id).write_text(
        json.dumps(heartbeat), encoding="utf-8"
    )
    return control


def test_requires_explicit_absolute_state_and_path_safe_identity(tmp_path: Path) -> None:
    with pytest.raises(watchdog.WatchdogError, match="explicit and absolute"):
        _config(Path("relative"))
    with pytest.raises(watchdog.WatchdogError, match="path-safe"):
        watchdog.WatchdogConfig(
            state_root=tmp_path,
            campaign_id="../escape",
            manifest_digest=MANIFEST,
            fence=1,
            deadline=_stamp(10),
            heartbeat_timeout_s=1,
        )


def test_external_process_closes_gate_at_deadline_and_is_idempotent(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path, deadline_delta_s=-1)
    control = _arm(config)

    process = watchdog.spawn_watchdog(config)
    assert process.pid != os.getpid()
    assert process.wait(timeout=5) == watchdog.EXIT_TRIPPED

    gate_path = watchdog.authority_gate_path(tmp_path, CAMPAIGN)
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    assert gate["dispatch_allowed"] is False
    assert gate["authority_mode"] == "closed"
    assert gate["revision"] == 2
    receipt_path = control / "watchdog_trip.json"
    before = receipt_path.read_bytes()
    receipt = json.loads(before)
    assert receipt["schema"] == watchdog.TRIP_SCHEMA
    assert receipt["reason"] == "DEADLINE_EXCEEDED"
    assert receipt["watchdog_pid"] == process.pid
    assert receipt["provider_dispatch_authority"] is False

    second = watchdog.spawn_watchdog(config)
    assert second.wait(timeout=5) == watchdog.EXIT_OK
    assert receipt_path.read_bytes() == before
    assert json.loads(gate_path.read_text(encoding="utf-8"))["revision"] == 2
    events = list((control.parent / "events").glob("watchdog-*.json"))
    assert len(events) == 1


def test_heartbeat_timeout_is_a_hard_trip(tmp_path: Path) -> None:
    config = _config(tmp_path, heartbeat_timeout_s=0.1)
    _arm(config, heartbeat_delta_s=-5)

    code, decision = watchdog.run_watchdog(config, once=True)

    assert code == watchdog.EXIT_TRIPPED
    assert decision["reason"] == "HEARTBEAT_TIMEOUT"
    gate = json.loads(
        watchdog.authority_gate_path(tmp_path, CAMPAIGN).read_text(encoding="utf-8")
    )
    assert gate["dispatch_allowed"] is False


def test_stale_watchdog_cannot_mutate_newer_fence(tmp_path: Path) -> None:
    current = _config(tmp_path, fence=9, deadline_delta_s=-1)
    _arm(current)
    stale = _config(tmp_path, fence=8, deadline_delta_s=-1)
    gate_path = watchdog.authority_gate_path(tmp_path, CAMPAIGN)
    heartbeat = watchdog.heartbeat_path(tmp_path, CAMPAIGN)
    gate_before = gate_path.read_bytes()
    heartbeat_before = heartbeat.read_bytes()
    names_before = sorted(path.name for path in gate_path.parent.iterdir())

    code, decision = watchdog.run_watchdog(stale, once=True)

    assert code == watchdog.EXIT_STALE
    assert decision["reason"] == "stale_watchdog_fence"
    assert gate_path.read_bytes() == gate_before
    assert heartbeat.read_bytes() == heartbeat_before
    assert sorted(path.name for path in gate_path.parent.iterdir()) == names_before
    assert not (gate_path.parent / "watchdog_trip.json").exists()


def test_controller_heartbeat_is_fenced_monotonic_and_never_reopens(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    _arm(config)
    heartbeat = watchdog.record_heartbeat(config, sequence=2)
    assert heartbeat["sequence"] == 2
    assert watchdog.record_heartbeat(config, sequence=2) == heartbeat
    with pytest.raises(watchdog.WatchdogError, match="sequence must increase"):
        watchdog.record_heartbeat(config, sequence=1)

    watchdog.watch_once(
        config, observed_at=datetime.now(timezone.utc) + timedelta(minutes=2)
    )
    with pytest.raises(watchdog.WatchdogError, match="closed authority"):
        watchdog.record_heartbeat(config, sequence=3)
