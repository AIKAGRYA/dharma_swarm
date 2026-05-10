from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dharma_swarm.runtime_artifacts import (
    dgc_health_snapshot_summary,
    write_dgc_health_snapshot,
)


def test_write_dgc_health_snapshot_persists_fresh_runtime_metadata(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    (state_dir / "daemon.pid").parent.mkdir(parents=True, exist_ok=True)
    (state_dir / "daemon.pid").write_text("4242\n", encoding="utf-8")

    path = write_dgc_health_snapshot(
        state_dir,
        daemon_pid=4242,
        agent_count=7,
        task_count=11,
        anomaly_count=2,
        source="orchestrate_live",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["daemon_pid"] == 4242
    assert payload["agent_count"] == 7
    assert payload["task_count"] == 11
    assert payload["anomaly_count"] == 2
    assert payload["source"] == "orchestrate_live"

    summary = dgc_health_snapshot_summary(state_dir)
    assert summary["status"] == "fresh"
    assert summary["daemon_pid_mismatch"] is False


def test_write_dgc_health_snapshot_preserves_existing_liveness_when_omitted(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"

    write_dgc_health_snapshot(
        state_dir,
        daemon_pid=4242,
        agent_count=1,
        task_count=2,
        anomaly_count=0,
        source="swarm.run",
        liveness={
            "bootstrap_phase": "bootstrap_complete",
            "last_tick_number": 7,
            "last_tick_completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    path = write_dgc_health_snapshot(
        state_dir,
        daemon_pid=4242,
        agent_count=3,
        task_count=4,
        anomaly_count=1,
        source="orchestrate_live",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["source"] == "orchestrate_live"
    assert payload["liveness"]["bootstrap_phase"] == "bootstrap_complete"
    assert payload["liveness"]["last_tick_number"] == 7


def test_dgc_health_snapshot_summary_classifies_stalled_ticks_from_liveness(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    stale_tick = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    write_dgc_health_snapshot(
        state_dir,
        daemon_pid=4242,
        agent_count=5,
        task_count=8,
        anomaly_count=0,
        source="swarm.run",
        liveness={
            "bootstrap_phase": "bootstrap_complete",
            "bootstrap_started_at": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
            "bootstrap_completed_at": (datetime.now(timezone.utc) - timedelta(minutes=29)).isoformat(),
            "last_tick_started_at": stale_tick,
            "last_tick_completed_at": stale_tick,
            "last_tick_number": 16,
            "tick_interval_s": 0.5,
            "coordination_refresh_interval_s": 0.5,
        },
    )

    summary = dgc_health_snapshot_summary(state_dir)
    assert summary["status"] == "fresh"
    assert summary["liveness"]["bootstrap_complete"] is True
    assert summary["liveness"]["tick_fresh"] is False
    assert summary["liveness"]["status"] == "stalled"
    assert summary["liveness"]["stall_state"] == "tick_stalled"
