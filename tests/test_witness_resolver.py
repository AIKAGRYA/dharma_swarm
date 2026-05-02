"""Tests for dharma_swarm.witness_resolver (Component 1.2).

Covers:
1. enqueue + idempotency.
2. tick: window not elapsed -> nothing resolved.
3. tick: window elapsed -> resolution mark written, queue drained.
4. classify_outcome: stable (no follow-up marks), degraded (severity
   warn after enqueue), reversed (post_deployment_drift mark).
5. Force-unknown on backlog (cycle delta > MAX_BACKLOG_CYCLES).
6. Persistence: rehydrate queue from disk after restart.
7. R_M repair-rate compatibility: stable -> repaired, reversed -> not.

Run: pytest tests/test_witness_resolver.py -q
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm import causal_ledger, witness_resolver


@pytest.fixture
def paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "pending": tmp_path / "_pending.jsonl",
        "register_marks": tmp_path / "register_marks.jsonl",
        "witness_dir": tmp_path / "witness",
    }


def _make_resolver(paths: dict[str, Path]) -> witness_resolver.WitnessResolver:
    return witness_resolver.WitnessResolver(
        pending_path=paths["pending"],
        register_marks_path=paths["register_marks"],
        witness_dir=paths["witness_dir"],
    )


def _seed_prediction(
    paths: dict[str, Path],
    *,
    subject_kind: str = "gate",
    subject_id: str = "subj-1",
    expected: dict[str, float] = None,
    window: int = 5,
):
    """Seed a real causal_ledger prediction so the resolver has something
    to resolve. Returns the prediction mark."""
    return causal_ledger.declare_prediction(
        subject_kind=subject_kind,
        subject_id=subject_id,
        expected=expected or {"k": 1.0},
        window_heartbeats=window,
        log_path=paths["register_marks"],
    )


# ---------------------------------------------------------------------------
# 1. enqueue + idempotency
# ---------------------------------------------------------------------------


def test_enqueue_basic(paths: dict[str, Path]) -> None:
    pred = _seed_prediction(paths)
    assert pred is not None
    resolver = _make_resolver(paths)
    ok = resolver.enqueue(
        prediction_mark_id=pred.mark_id,
        subject_kind="gate",
        subject_id="subj-1",
        expected={"k": 1.0},
        window_heartbeats=5,
        current_cycle=0,
    )
    assert ok is True
    assert resolver.queue_size() == 1


def test_enqueue_idempotent(paths: dict[str, Path]) -> None:
    pred = _seed_prediction(paths)
    resolver = _make_resolver(paths)
    resolver.enqueue(
        prediction_mark_id=pred.mark_id,
        subject_kind="gate",
        subject_id="subj-1",
        expected={"k": 1.0},
        window_heartbeats=5,
        current_cycle=0,
    )
    second = resolver.enqueue(
        prediction_mark_id=pred.mark_id,
        subject_kind="gate",
        subject_id="subj-1",
        expected={"k": 1.0},
        window_heartbeats=5,
        current_cycle=0,
    )
    assert second is False
    assert resolver.queue_size() == 1


def test_enqueue_empty_id_rejected(paths: dict[str, Path]) -> None:
    resolver = _make_resolver(paths)
    ok = resolver.enqueue(
        prediction_mark_id="",
        subject_kind="gate",
        subject_id="x",
        expected={"k": 1.0},
        window_heartbeats=5,
        current_cycle=0,
    )
    assert ok is False
    assert resolver.queue_size() == 0


# ---------------------------------------------------------------------------
# 2-3. tick: window timing
# ---------------------------------------------------------------------------


def test_tick_window_not_elapsed_does_not_resolve(paths: dict[str, Path]) -> None:
    pred = _seed_prediction(paths, window=5)
    resolver = _make_resolver(paths)
    resolver.enqueue(
        prediction_mark_id=pred.mark_id,
        subject_kind="gate",
        subject_id="subj-1",
        expected={"k": 1.0},
        window_heartbeats=5,
        current_cycle=0,
    )
    # Tick before window elapses
    resolutions = resolver.tick(current_cycle=3)
    assert resolutions == []
    assert resolver.queue_size() == 1


def test_tick_window_elapsed_resolves(paths: dict[str, Path]) -> None:
    pred = _seed_prediction(paths, window=5)
    resolver = _make_resolver(paths)
    resolver.enqueue(
        prediction_mark_id=pred.mark_id,
        subject_kind="gate",
        subject_id="subj-1",
        expected={"k": 1.0},
        window_heartbeats=5,
        current_cycle=0,
    )
    resolutions = resolver.tick(current_cycle=10)
    assert len(resolutions) == 1
    assert resolutions[0]["prediction_mark_id"] == pred.mark_id
    assert resolutions[0]["actual_outcome"] in {"stable", "degraded", "reversed"}
    assert resolver.queue_size() == 0  # drained


# ---------------------------------------------------------------------------
# 4. classify_outcome variants
# ---------------------------------------------------------------------------


def test_classify_stable_when_no_follow_up_marks(paths: dict[str, Path]) -> None:
    pred = _seed_prediction(paths)
    resolver = _make_resolver(paths)
    resolver.enqueue(
        prediction_mark_id=pred.mark_id,
        subject_kind="gate",
        subject_id="subj-stable",
        expected={"k": 1.0},
        window_heartbeats=2,
        current_cycle=0,
    )
    resolutions = resolver.tick(current_cycle=5)
    assert len(resolutions) == 1
    assert resolutions[0]["actual_outcome"] == "stable"


def test_classify_degraded_when_severity_mark_after_enqueue(
    paths: dict[str, Path],
) -> None:
    pred = _seed_prediction(paths, subject_id="subj-deg")
    # Append a degraded-severity mark on same subject AFTER enqueue ts
    with paths["register_marks"].open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": "2099-01-01T00:00:00+00:00",  # well after now
            "subject_id": "subj-deg",
            "severity": "warn",
            "plane": "register",
            "discipline": "friction_detector",
        }) + "\n")
    resolver = _make_resolver(paths)
    resolver.enqueue(
        prediction_mark_id=pred.mark_id,
        subject_kind="gate",
        subject_id="subj-deg",
        expected={"k": 1.0},
        window_heartbeats=2,
        current_cycle=0,
    )
    resolutions = resolver.tick(current_cycle=5)
    assert len(resolutions) == 1
    assert resolutions[0]["actual_outcome"] == "degraded"


def test_classify_reversed_on_post_deployment_drift_mark(
    paths: dict[str, Path],
) -> None:
    pred = _seed_prediction(paths, subject_id="subj-rev")
    # Append a drift mark with corrects pointing at our prediction
    with paths["register_marks"].open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": "2099-01-01T00:00:00+00:00",
            "subject_id": "subj-rev",
            "severity": "block",
            "plane": "register",
            "discipline": "post_deployment_drift",
            "corrects": pred.mark_id,
        }) + "\n")
    resolver = _make_resolver(paths)
    resolver.enqueue(
        prediction_mark_id=pred.mark_id,
        subject_kind="mutation",
        subject_id="subj-rev",
        expected={"k": 1.0},
        window_heartbeats=2,
        current_cycle=0,
    )
    resolutions = resolver.tick(current_cycle=5)
    assert len(resolutions) == 1
    assert resolutions[0]["actual_outcome"] == "reversed"


# ---------------------------------------------------------------------------
# 5. Backlog -> force unknown
# ---------------------------------------------------------------------------


def test_backlog_force_unknown(paths: dict[str, Path]) -> None:
    pred = _seed_prediction(paths)
    resolver = _make_resolver(paths)
    resolver.enqueue(
        prediction_mark_id=pred.mark_id,
        subject_kind="gate",
        subject_id="subj-1",
        expected={"k": 1.0},
        window_heartbeats=5,
        current_cycle=0,
    )
    # Tick way in the future, beyond MAX_BACKLOG_CYCLES
    far_future = witness_resolver.MAX_BACKLOG_CYCLES + 100
    resolutions = resolver.tick(current_cycle=far_future)
    assert len(resolutions) == 1
    assert resolutions[0]["actual_outcome"] == "unknown"
    assert resolutions[0].get("reason") == "backlog_exceeded"
    assert resolver.queue_size() == 0


# ---------------------------------------------------------------------------
# 6. Persistence
# ---------------------------------------------------------------------------


def test_pending_queue_rehydrates_on_construction(paths: dict[str, Path]) -> None:
    pred1 = _seed_prediction(paths, subject_id="s1")
    pred2 = _seed_prediction(paths, subject_id="s2")

    r1 = _make_resolver(paths)
    r1.enqueue(
        prediction_mark_id=pred1.mark_id,
        subject_kind="gate",
        subject_id="s1",
        expected={"k": 1.0},
        window_heartbeats=10,
        current_cycle=0,
    )
    r1.enqueue(
        prediction_mark_id=pred2.mark_id,
        subject_kind="gate",
        subject_id="s2",
        expected={"k": 2.0},
        window_heartbeats=10,
        current_cycle=0,
    )
    assert r1.queue_size() == 2

    # Simulate daemon restart
    r2 = _make_resolver(paths)
    assert r2.queue_size() == 2
    s1_entries = r2.pending_for_subject("s1")
    assert len(s1_entries) == 1
    assert s1_entries[0].prediction_mark_id == pred1.mark_id


def test_corrupted_pending_lines_skipped(paths: dict[str, Path]) -> None:
    paths["pending"].parent.mkdir(parents=True, exist_ok=True)
    pred = _seed_prediction(paths)
    # Manual seed: one valid line + corruption
    valid = witness_resolver.PendingResolution(
        prediction_mark_id=pred.mark_id,
        subject_kind="gate",
        subject_id="x",
        expected={"k": 1.0},
        enqueued_at_cycle=0,
        resolves_at_cycle=5,
        enqueued_at_iso="2026-05-01T00:00:00+00:00",
    )
    paths["pending"].write_text(
        json.dumps(valid.to_dict()) + "\n"
        + "not json\n"
        + "{partial\n"
        + "\n",
        encoding="utf-8",
    )
    r = _make_resolver(paths)
    assert r.queue_size() == 1


# ---------------------------------------------------------------------------
# 7. End-to-end: stable resolution feeds R_M repair correctly
# ---------------------------------------------------------------------------


def test_stable_resolution_yields_repaired_in_repair_rate(
    paths: dict[str, Path],
) -> None:
    """The resolver writes resolution marks via causal_ledger. A "stable"
    outcome should produce actual ≈ expected, which causal_ledger's
    _is_repaired heuristic accepts as repaired.

    NOTE: prediction.expected and resolver.enqueue's expected MUST match
    or _is_repaired key check fails. This is a real design constraint
    documented in WitnessResolver.enqueue."""
    pred = _seed_prediction(
        paths,
        subject_kind="mutation",
        subject_id="m1",
        expected={"score": 0.80},
    )
    resolver = _make_resolver(paths)
    resolver.enqueue(
        prediction_mark_id=pred.mark_id,
        subject_kind="mutation",
        subject_id="m1",
        expected={"score": 0.80},
        window_heartbeats=2,
        current_cycle=0,
    )
    resolver.tick(current_cycle=5)

    # Now compute repair rate via causal_ledger
    rate, n_pred, n_resolved = causal_ledger.compute_repair_rate_for_kind(
        "mutation", log_path=paths["register_marks"],
    )
    assert n_pred == 1
    assert n_resolved == 1
    assert rate == pytest.approx(1.0)


def test_reversed_resolution_yields_not_repaired(paths: dict[str, Path]) -> None:
    pred = _seed_prediction(
        paths,
        subject_kind="mutation",
        subject_id="m-rev",
        expected={"score": 0.80},
    )
    # Inject the drift mark BEFORE enqueueing so classify_outcome sees it
    with paths["register_marks"].open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": "2099-01-01T00:00:00+00:00",
            "subject_id": "m-rev",
            "severity": "block",
            "plane": "register",
            "discipline": "post_deployment_drift",
            "corrects": pred.mark_id,
        }) + "\n")
    resolver = _make_resolver(paths)
    resolver.enqueue(
        prediction_mark_id=pred.mark_id,
        subject_kind="mutation",
        subject_id="m-rev",
        expected={"score": 0.80},
        window_heartbeats=2,
        current_cycle=0,
    )
    resolver.tick(current_cycle=5)

    rate, n_pred, n_resolved = causal_ledger.compute_repair_rate_for_kind(
        "mutation", log_path=paths["register_marks"],
    )
    assert n_pred == 1
    assert n_resolved == 1
    assert rate == 0.0  # sign flip -> not repaired
