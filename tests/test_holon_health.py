"""Verifier for the holon health/observability surface (U9).

Pure read-only projection: given a holon name, project its status from files/state ONLY.
NO live model calls, NO animation. Every test uses a tmp ``agents_root`` so nothing
touches the real ``~/.dharma/agents`` home. Reuses holon_killswitch + holon_bridge.
"""
from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm import holon_health, holon_killswitch as ks
from dharma_swarm.holon_service_liveness import record_service_heartbeat


def _register(agents_root: Path, name: str, model: str = "claude-opus", provider: str = "anthropic_max") -> Path:
    """Create a minimal registered agent home (identity.json + active.txt) like load_holon expects."""
    agent_dir = agents_root / name
    (agent_dir / "prompt_variants").mkdir(parents=True, exist_ok=True)
    (agent_dir / "identity.json").write_text(
        json.dumps({"name": name, "model": model, "provider": provider}), encoding="utf-8"
    )
    (agent_dir / "prompt_variants" / "active.txt").write_text("You are " + name + ".", encoding="utf-8")
    return agent_dir


def test_status_unregistered_holon(tmp_path):
    """A name with no identity.json projects registered=False and never raises."""
    st = holon_health.holon_status("ghost", agents_root=tmp_path)
    assert st["name"] == "ghost"
    assert st["registered"] is False
    assert st["model"] is None
    assert st["kill_requested"] is False
    assert st["compass_signal_count"] == 0
    assert st["service_alive"] is False
    assert st["service_liveness"]["heartbeat_seen"] is False


def test_status_registered_holon(tmp_path):
    _register(tmp_path, "h", model="claude-opus")
    st = holon_health.holon_status("h", agents_root=tmp_path)
    assert st["name"] == "h"
    assert st["registered"] is True
    assert st["model"] == "claude-opus"
    assert st["kill_requested"] is False
    assert st["compass_signal_count"] == 0
    assert st["service_alive"] is False
    assert st["service_liveness"]["heartbeat_seen"] is False


def test_status_projects_service_liveness_read_only(tmp_path):
    _register(tmp_path, "h")
    record_service_heartbeat(
        "h",
        agents_root=tmp_path,
        session_id="health-projection",
        service_id="test-service",
        status="running",
    )

    st = holon_health.holon_status("h", agents_root=tmp_path)

    assert st["service_alive"] is True
    assert st["service_liveness"]["heartbeat_seen"] is True
    assert st["service_liveness"]["latest_session_id"] == "health-projection"


def test_status_reflects_kill_signal(tmp_path):
    _register(tmp_path, "h")
    assert holon_health.holon_status("h", agents_root=tmp_path)["kill_requested"] is False
    ks.request_kill("h", reason="operator stop", agents_root=tmp_path)
    assert holon_health.holon_status("h", agents_root=tmp_path)["kill_requested"] is True
    ks.clear_kill("h", agents_root=tmp_path)
    assert holon_health.holon_status("h", agents_root=tmp_path)["kill_requested"] is False


def test_status_counts_compass_signals(tmp_path):
    _register(tmp_path, "h")
    sig_path = tmp_path / "h" / "compass_signals.jsonl"
    sig_path.write_text(
        json.dumps({"holon": "h", "telos_alignment": 0.9}) + "\n"
        + json.dumps({"holon": "h", "telos_alignment": 0.8}) + "\n",
        encoding="utf-8",
    )
    st = holon_health.holon_status("h", agents_root=tmp_path)
    assert st["compass_signal_count"] == 2


def test_status_ignores_blank_lines_in_compass_log(tmp_path):
    _register(tmp_path, "h")
    sig_path = tmp_path / "h" / "compass_signals.jsonl"
    sig_path.write_text(
        json.dumps({"telos_alignment": 0.9}) + "\n\n   \n" + json.dumps({"telos_alignment": 0.5}) + "\n",
        encoding="utf-8",
    )
    assert holon_health.holon_status("h", agents_root=tmp_path)["compass_signal_count"] == 2


def test_status_malformed_identity_is_registered_but_no_model(tmp_path):
    """A present-but-broken identity.json: still 'registered' (file exists), model degrades to None — never raises."""
    agent_dir = tmp_path / "broken"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "identity.json").write_text("{not json", encoding="utf-8")
    st = holon_health.holon_status("broken", agents_root=tmp_path)
    assert st["registered"] is True
    assert st["model"] is None


def test_status_identity_without_model(tmp_path):
    agent_dir = tmp_path / "nomodel"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "identity.json").write_text(json.dumps({"name": "nomodel"}), encoding="utf-8")
    st = holon_health.holon_status("nomodel", agents_root=tmp_path)
    assert st["registered"] is True
    assert st["model"] is None


def test_status_is_pure_read_only(tmp_path):
    """Calling holon_status must not create any files (no side effects)."""
    before = set(p.name for p in tmp_path.iterdir())
    holon_health.holon_status("ghost", agents_root=tmp_path)
    after = set(p.name for p in tmp_path.iterdir())
    assert before == after


def test_health_rows_empty_when_no_agents(tmp_path):
    assert holon_health.holon_health_rows(agents_root=tmp_path) == []


def test_health_rows_missing_root_returns_empty(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert holon_health.holon_health_rows(agents_root=missing) == []


def test_health_rows_lists_all_registered(tmp_path):
    _register(tmp_path, "alpha", model="m1")
    _register(tmp_path, "beta", model="m2")
    # a stray non-agent dir (no identity.json) must be skipped
    (tmp_path / "not_an_agent").mkdir()
    # a stray file at root must be skipped
    (tmp_path / "loose.txt").write_text("x", encoding="utf-8")

    rows = holon_health.holon_health_rows(agents_root=tmp_path)
    names = sorted(r["name"] for r in rows)
    assert names == ["alpha", "beta"]
    models = {r["name"]: r["model"] for r in rows}
    assert models == {"alpha": "m1", "beta": "m2"}
    assert all(r["registered"] is True for r in rows)


def test_health_rows_sorted_deterministic(tmp_path):
    for n in ["zeta", "alpha", "mu"]:
        _register(tmp_path, n)
    rows = holon_health.holon_health_rows(agents_root=tmp_path)
    assert [r["name"] for r in rows] == ["alpha", "mu", "zeta"]


def test_health_rows_reflects_kill_and_signals(tmp_path):
    _register(tmp_path, "a", model="m1")
    _register(tmp_path, "b", model="m2")
    ks.request_kill("a", agents_root=tmp_path)
    (tmp_path / "b" / "compass_signals.jsonl").write_text(
        json.dumps({"telos_alignment": 0.7}) + "\n", encoding="utf-8"
    )
    rows = {r["name"]: r for r in holon_health.holon_health_rows(agents_root=tmp_path)}
    assert rows["a"]["kill_requested"] is True
    assert rows["a"]["compass_signal_count"] == 0
    assert rows["b"]["kill_requested"] is False
    assert rows["b"]["compass_signal_count"] == 1
