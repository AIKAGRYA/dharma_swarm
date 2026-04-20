"""Tests for the PR3 stalled-frontier invariant in opportunity_dispatcher.

The invariant uses the dispatcher's HealthState + bridge.fire_signal to
make stalls loud for the solo operator. Tests cover:

- WARNING fires when last_success_at is older than 2× cron interval AND
  there is pending work or in-flight tasks.
- CRITICAL fires when consecutive_failures >= CRITICAL_FAILURE_THRESHOLD
  with active work, regardless of last_success_at staleness.
- No fire when pending+in_flight are both empty (silence is correct).
- The signal payload matches the orchestrator.py:1698 schema.
- Bridge errors don't escape the wrapper (best-effort fire).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm import algedonic_bridge, opportunity_dispatcher
from dharma_swarm.opportunity_dispatcher import HealthState


@pytest.fixture
def tmp_dharma(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dharma = tmp_path / "dharma"
    dharma.mkdir()
    monkeypatch.setattr(algedonic_bridge, "DHARMA_HOME", dharma)
    monkeypatch.setattr(algedonic_bridge, "SIGNALS_PATH", dharma / "algedonic_signals.jsonl")
    monkeypatch.setattr(algedonic_bridge, "WITNESS_DIR", dharma / "witness")
    monkeypatch.setattr(algedonic_bridge, "EMERGENCY_HOLD_PATH", dharma / "EMERGENCY_HOLD")
    return dharma


@pytest.fixture
def no_live_organism(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("dharma_swarm.organism.get_organism", lambda: None)


def _state_with_stale_success(seconds_ago: int) -> HealthState:
    last_iso = (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()
    return HealthState(
        last_run_at=datetime.now(timezone.utc).isoformat(),
        last_success_at=last_iso,
        consecutive_failures=0,
        run_count=10,
        success_count=8,
    )


# --------------------------------------------------------------------------
# detect_stalled_frontier — pure decision function
# --------------------------------------------------------------------------


def test_no_signal_when_no_pending_and_no_in_flight():
    state = _state_with_stale_success(seconds_ago=99999)  # very stale
    sig = opportunity_dispatcher.detect_stalled_frontier(
        state=state, pending_count=0, observed_in_flight=0,
    )
    assert sig is None


def test_warning_when_stale_and_pending_present():
    interval = 1800  # 30 min
    state = _state_with_stale_success(seconds_ago=2 * interval + 60)  # past 2x window
    sig = opportunity_dispatcher.detect_stalled_frontier(
        state=state, pending_count=5, observed_in_flight=0, interval_seconds=interval,
    )
    assert sig is not None
    assert sig["severity"] == "warning"
    assert sig["kind"] == "dispatcher_stale_success"
    assert sig["context"]["pending_count"] == 5


def test_warning_when_stale_and_in_flight_present_but_no_pending():
    interval = 1800
    state = _state_with_stale_success(seconds_ago=2 * interval + 60)
    sig = opportunity_dispatcher.detect_stalled_frontier(
        state=state, pending_count=0, observed_in_flight=3, interval_seconds=interval,
    )
    assert sig is not None
    assert sig["severity"] == "warning"


def test_no_warning_when_freshly_succeeded():
    interval = 1800
    state = _state_with_stale_success(seconds_ago=60)  # within window
    sig = opportunity_dispatcher.detect_stalled_frontier(
        state=state, pending_count=5, observed_in_flight=0, interval_seconds=interval,
    )
    assert sig is None


def test_critical_when_consecutive_failures_threshold_hit():
    state = HealthState(
        consecutive_failures=opportunity_dispatcher.CRITICAL_FAILURE_THRESHOLD,
        last_run_at=datetime.now(timezone.utc).isoformat(),
        last_success_at=None,
        last_run_errors=["err1", "err2", "err3"],
    )
    sig = opportunity_dispatcher.detect_stalled_frontier(
        state=state, pending_count=2, observed_in_flight=0,
    )
    assert sig is not None
    assert sig["severity"] == "critical"
    assert sig["kind"] == "dispatcher_consecutive_failures"
    assert sig["value"] == opportunity_dispatcher.CRITICAL_FAILURE_THRESHOLD


def test_critical_takes_precedence_over_warning():
    """Even if the success timestamp is stale, CRITICAL outranks WARNING."""
    interval = 1800
    state = HealthState(
        consecutive_failures=5,
        last_run_at=datetime.now(timezone.utc).isoformat(),
        last_success_at=(datetime.now(timezone.utc) - timedelta(seconds=99999)).isoformat(),
    )
    sig = opportunity_dispatcher.detect_stalled_frontier(
        state=state, pending_count=1, observed_in_flight=0, interval_seconds=interval,
    )
    assert sig["severity"] == "critical"


# --------------------------------------------------------------------------
# _maybe_fire_invariant — wraps detect + bridge.fire_signal
# --------------------------------------------------------------------------


def test_maybe_fire_invariant_writes_to_bridge_jsonl(
    tmp_dharma: Path, no_live_organism,
):
    interval = 1800
    state = _state_with_stale_success(seconds_ago=2 * interval + 60)
    opportunity_dispatcher._maybe_fire_invariant(
        state=state, pending_count=2, observed_in_flight=0,
    )
    rows = (tmp_dharma / "algedonic_signals.jsonl").read_text().splitlines()
    assert len(rows) == 1
    payload = json.loads(rows[0])
    # Schema match: orchestrator.py:1698 fields
    assert payload["kind"] == "dispatcher_stale_success"
    assert payload["severity"] == "warning"
    assert "timestamp" in payload
    assert payload["source"] == "opportunity_dispatcher"


def test_maybe_fire_invariant_silent_when_no_work(
    tmp_dharma: Path, no_live_organism,
):
    state = _state_with_stale_success(seconds_ago=99999)
    opportunity_dispatcher._maybe_fire_invariant(
        state=state, pending_count=0, observed_in_flight=0,
    )
    assert not (tmp_dharma / "algedonic_signals.jsonl").exists()


def test_maybe_fire_invariant_swallows_bridge_errors(
    tmp_dharma: Path, no_live_organism, monkeypatch: pytest.MonkeyPatch,
):
    """A broken bridge must not crash the dispatcher — health.json was
    already written by the time we try to fire."""
    def _boom(**kw):
        raise RuntimeError("bridge broken")
    monkeypatch.setattr(algedonic_bridge, "fire_signal", _boom)

    interval = 1800
    state = _state_with_stale_success(seconds_ago=2 * interval + 60)
    # Should not raise:
    opportunity_dispatcher._maybe_fire_invariant(
        state=state, pending_count=1, observed_in_flight=0,
    )
