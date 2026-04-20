"""Tests for algedonic_bridge — the explicit bridge from non-organism callers
to the algedonic channel + on-disk fallback.

Covers:
- Always writes algedonic_signals.jsonl matching orchestrator.py:1698 schema
- Always writes witness mirror under ~/.dharma/witness/{date}/
- Falls back gracefully when no live organism (routed_to_live_handler=False)
- Routes to live organism when singleton resolvable
- Writes EMERGENCY_HOLD on the third critical within a 1h window
- Does NOT rewrite EMERGENCY_HOLD if it already exists (preserves first ts)
- Severity normalization (unknown → warning)
- jsonl write failure does not crash the bridge
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm import algedonic_bridge


@pytest.fixture
def tmp_dharma(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect every ~/.dharma path inside the bridge to ``tmp_path/dharma``."""
    dharma = tmp_path / "dharma"
    dharma.mkdir()
    monkeypatch.setattr(algedonic_bridge, "DHARMA_HOME", dharma)
    monkeypatch.setattr(algedonic_bridge, "SIGNALS_PATH", dharma / "algedonic_signals.jsonl")
    monkeypatch.setattr(algedonic_bridge, "WITNESS_DIR", dharma / "witness")
    monkeypatch.setattr(algedonic_bridge, "EMERGENCY_HOLD_PATH", dharma / "EMERGENCY_HOLD")
    return dharma


@pytest.fixture
def no_live_organism(monkeypatch: pytest.MonkeyPatch):
    """Force ``get_organism`` to return None so routing goes to fallback only."""
    monkeypatch.setattr("dharma_swarm.organism.get_organism", lambda: None)


# --------------------------------------------------------------------------
# Always-write semantics
# --------------------------------------------------------------------------


def test_fire_signal_always_writes_jsonl_and_witness(tmp_dharma: Path, no_live_organism):
    res = algedonic_bridge.fire_signal(
        kind="dispatcher_test",
        severity="warning",
        action="test action",
        value=42,
        description="test",
        source="opportunity_dispatcher",
    )
    assert res.jsonl_written is True
    assert res.witness_written is True
    assert res.routed_to_live_handler is False
    assert res.severity == "warning"

    # JSONL contains exactly one row matching orchestrator.py:1698 schema.
    rows = (tmp_dharma / "algedonic_signals.jsonl").read_text().splitlines()
    assert len(rows) == 1
    payload = json.loads(rows[0])
    for required in ("kind", "severity", "value", "action", "timestamp"):
        assert required in payload
    assert payload["kind"] == "dispatcher_test"
    assert payload["severity"] == "warning"
    assert isinstance(payload["timestamp"], (int, float))

    # Witness mirror lives under date-stamped folder.
    witness_files = list((tmp_dharma / "witness").rglob("opportunity_dispatcher_signal.jsonl"))
    assert len(witness_files) == 1
    wpayload = json.loads(witness_files[0].read_text().splitlines()[0])
    assert wpayload["signal_id"] == res.signal_id


def test_unknown_severity_normalizes_to_warning(tmp_dharma: Path, no_live_organism):
    res = algedonic_bridge.fire_signal(
        kind="x", severity="purple", action="a", value=0,
    )
    assert res.severity == "warning"
    payload = json.loads((tmp_dharma / "algedonic_signals.jsonl").read_text().splitlines()[0])
    assert payload["severity"] == "warning"


# --------------------------------------------------------------------------
# Live organism routing
# --------------------------------------------------------------------------


class _StubAlgChannel:
    fired: list[Any] = []

    async def fire(self, signal):
        type(self).fired.append(signal)


class _StubOrganism:
    algedonic = _StubAlgChannel()


def test_routes_to_live_organism_when_singleton_present(
    tmp_dharma: Path, monkeypatch: pytest.MonkeyPatch,
):
    _StubAlgChannel.fired = []
    monkeypatch.setattr("dharma_swarm.organism.get_organism", lambda: _StubOrganism())

    res = algedonic_bridge.fire_signal(
        kind="dispatcher_test",
        severity="critical",
        action="route check",
        value=1,
    )

    assert res.routed_to_live_handler is True
    # Wait for any pending coroutine in case asyncio.ensure_future was used.
    # In our path with no event loop, we used asyncio.run() — synchronous.
    assert len(_StubAlgChannel.fired) == 1
    sig = _StubAlgChannel.fired[0]
    assert sig.severity == "critical"
    assert "route check" in sig.title


def test_falls_back_when_get_organism_raises(
    tmp_dharma: Path, monkeypatch: pytest.MonkeyPatch,
):
    def _boom():
        raise RuntimeError("import broken")
    monkeypatch.setattr("dharma_swarm.organism.get_organism", _boom)

    res = algedonic_bridge.fire_signal(
        kind="x", severity="warning", action="a", value=0,
    )
    assert res.routed_to_live_handler is False
    assert res.jsonl_written is True


# --------------------------------------------------------------------------
# EMERGENCY_HOLD escalation on critical×3-in-1h
# --------------------------------------------------------------------------


def test_emergency_hold_written_on_third_critical_in_one_hour(
    tmp_dharma: Path, no_live_organism,
):
    # First two criticals — no marker yet.
    r1 = algedonic_bridge.fire_signal(kind="x", severity="critical", action="a1", value=1)
    r2 = algedonic_bridge.fire_signal(kind="x", severity="critical", action="a2", value=2)
    assert r1.emergency_hold_written is False
    assert r2.emergency_hold_written is False
    assert not (tmp_dharma / "EMERGENCY_HOLD").exists()

    # Third critical → marker.
    r3 = algedonic_bridge.fire_signal(kind="x", severity="critical", action="a3", value=3)
    assert r3.emergency_hold_written is True
    marker = tmp_dharma / "EMERGENCY_HOLD"
    assert marker.exists()
    body = json.loads(marker.read_text())
    assert "trigger_signal_id" in body
    assert body["trigger_signal_id"] == r3.signal_id


def test_emergency_hold_not_rewritten_when_already_held(
    tmp_dharma: Path, no_live_organism,
):
    # Pre-create the marker.
    (tmp_dharma / "EMERGENCY_HOLD").write_text(
        json.dumps({"held_at": "2000-01-01", "reason": "preexisting"}),
        encoding="utf-8",
    )
    # Even with 3 criticals, marker stays untouched.
    for i in range(3):
        algedonic_bridge.fire_signal(kind="x", severity="critical", action=f"a{i}", value=i)
    body = json.loads((tmp_dharma / "EMERGENCY_HOLD").read_text())
    assert body["reason"] == "preexisting"


def test_warning_does_not_trigger_emergency_hold(
    tmp_dharma: Path, no_live_organism,
):
    for i in range(5):
        algedonic_bridge.fire_signal(kind="x", severity="warning", action=f"a{i}", value=i)
    assert not (tmp_dharma / "EMERGENCY_HOLD").exists()


def test_critical_outside_window_does_not_count(
    tmp_dharma: Path, no_live_organism, monkeypatch: pytest.MonkeyPatch,
):
    # Pre-seed two ancient criticals (>1h ago).
    ancient_ts = time.time() - 7200  # 2h ago
    for i in range(2):
        (tmp_dharma / "algedonic_signals.jsonl").parent.mkdir(parents=True, exist_ok=True)
        with (tmp_dharma / "algedonic_signals.jsonl").open("a") as fh:
            fh.write(json.dumps({
                "kind": "old", "severity": "critical", "value": i,
                "action": f"old{i}", "timestamp": ancient_ts,
            }) + "\n")
    # Fresh critical — count includes 1 (just-fired) + 0 recent (ancient 2 don't count).
    r = algedonic_bridge.fire_signal(kind="x", severity="critical", action="now", value=1)
    assert r.emergency_hold_written is False


# --------------------------------------------------------------------------
# Robustness
# --------------------------------------------------------------------------


def test_jsonl_write_failure_does_not_raise(
    tmp_dharma: Path, no_live_organism, monkeypatch: pytest.MonkeyPatch,
):
    # Replace SIGNALS_PATH with a path that mkdir cannot create — make the
    # parent be an existing file.
    bad_parent = tmp_dharma / "blocked"
    bad_parent.write_text("not a dir")
    monkeypatch.setattr(algedonic_bridge, "SIGNALS_PATH", bad_parent / "algedonic_signals.jsonl")

    res = algedonic_bridge.fire_signal(kind="x", severity="warning", action="a", value=0)
    # Witness still works because that's a different path.
    assert res.jsonl_written is False
    # And the bridge does not raise.
