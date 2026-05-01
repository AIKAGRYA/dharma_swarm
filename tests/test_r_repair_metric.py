"""Tests for dharma_swarm.r_repair_metric (Component 1.7).

Covers:
1. Cold start (no predictions) returns NaN aggregate, confidence=0.
2. Geometric mean computed correctly across three kinds.
3. Zero in one kind pulls aggregate to zero.
4. NaN handling (one kind has no data) excludes from aggregate.
5. Provisional flag during first 90 days.
6. near_eigenform alarm fires on synthesized 30-day sustained > 0.95.
7. Persistence round-trip (score + history).

Run: pytest tests/test_r_repair_metric.py -q
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm import causal_ledger, r_repair_metric


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_log(tmp_path: Path) -> Path:
    return tmp_path / "register_marks.jsonl"


@pytest.fixture
def tmp_history(tmp_path: Path) -> Path:
    return tmp_path / "r_repair_history.jsonl"


@pytest.fixture
def tmp_score(tmp_path: Path) -> Path:
    return tmp_path / "r_repair_score.json"


def _seed_predict_resolve(
    log_path: Path,
    *,
    subject_kind: str,
    n_total: int,
    n_repaired: int,
    base_metric_name: str = "k",
) -> None:
    """Seed a fixture: create n_total predictions; resolve n_repaired of
    them with actual matching expected; resolve the rest with sign-flipped
    actual so they read as NOT repaired."""
    assert n_repaired <= n_total
    expected_value = 1.0
    for i in range(n_total):
        pred = causal_ledger.declare_prediction(
            subject_kind=subject_kind,
            subject_id=f"{subject_kind}-{i}",
            expected={base_metric_name: expected_value},
            window_heartbeats=1,
            log_path=log_path,
        )
        assert pred is not None
        # First n_repaired get a "good" resolution; rest get sign-flipped
        actual = expected_value if i < n_repaired else -expected_value
        causal_ledger.resolve_prediction(
            prediction_mark_id=pred.mark_id,
            actual={base_metric_name: actual},
            expected={base_metric_name: expected_value},
            log_path=log_path,
        )


# ---------------------------------------------------------------------------
# 1. Cold start
# ---------------------------------------------------------------------------


def test_cold_start_returns_nan_aggregate_zero_confidence(
    tmp_log: Path, tmp_history: Path
) -> None:
    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log,
        history_path=tmp_history,
    )
    assert math.isnan(score.r_aggregate)
    assert math.isnan(score.r_gate)
    assert math.isnan(score.r_mutation)
    assert math.isnan(score.r_welfare)
    assert score.n_predictions_total == 0
    assert score.confidence == 0.0
    assert any("no causal predictions" in n for n in score.notes)


# ---------------------------------------------------------------------------
# 2. Geometric mean across kinds
# ---------------------------------------------------------------------------


def test_geometric_mean_across_three_kinds(
    tmp_log: Path, tmp_history: Path
) -> None:
    # gate: 8/10 repaired -> 0.8
    # mutation: 6/10 repaired -> 0.6
    # welfare: 5/10 repaired -> 0.5
    # geometric mean = (0.8 * 0.6 * 0.5) ** (1/3)
    _seed_predict_resolve(tmp_log, subject_kind="gate", n_total=10, n_repaired=8)
    _seed_predict_resolve(tmp_log, subject_kind="mutation", n_total=10, n_repaired=6)
    _seed_predict_resolve(
        tmp_log, subject_kind="welfare_proposal", n_total=10, n_repaired=5
    )

    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log, history_path=tmp_history
    )
    assert score.r_gate == pytest.approx(0.8)
    assert score.r_mutation == pytest.approx(0.6)
    assert score.r_welfare == pytest.approx(0.5)
    expected_geo = (0.8 * 0.6 * 0.5) ** (1.0 / 3.0)
    assert score.r_aggregate == pytest.approx(expected_geo)
    assert score.n_predictions_total == 30
    assert score.n_resolved_total == 30
    assert score.n_repaired_total == 19  # 8+6+5
    assert score.confidence == 1.0  # 30 predictions hits CONFIDENCE_FULL_AT_N


# ---------------------------------------------------------------------------
# 3. Zero in one kind pulls aggregate to zero
# ---------------------------------------------------------------------------


def test_zero_in_one_kind_pulls_aggregate_to_zero(
    tmp_log: Path, tmp_history: Path
) -> None:
    _seed_predict_resolve(tmp_log, subject_kind="gate", n_total=10, n_repaired=10)
    _seed_predict_resolve(tmp_log, subject_kind="mutation", n_total=10, n_repaired=10)
    # Welfare: 0/10 repaired -> 0.0 -> aggregate must be 0
    _seed_predict_resolve(
        tmp_log, subject_kind="welfare_proposal", n_total=10, n_repaired=0
    )

    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log, history_path=tmp_history
    )
    assert score.r_gate == pytest.approx(1.0)
    assert score.r_mutation == pytest.approx(1.0)
    assert score.r_welfare == pytest.approx(0.0)
    assert score.r_aggregate == 0.0  # geometric: any zero kills the product


# ---------------------------------------------------------------------------
# 4. NaN: one kind has no data, excluded from aggregate
# ---------------------------------------------------------------------------


def test_nan_kind_excluded_from_aggregate(tmp_log: Path, tmp_history: Path) -> None:
    # Only gate has data; mutation and welfare have nothing.
    _seed_predict_resolve(tmp_log, subject_kind="gate", n_total=10, n_repaired=7)

    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log, history_path=tmp_history
    )
    assert score.r_gate == pytest.approx(0.7)
    assert math.isnan(score.r_mutation)
    assert math.isnan(score.r_welfare)
    # Aggregate is just gate's rate (single valid kind, geo mean of one)
    assert score.r_aggregate == pytest.approx(0.7)
    # Confidence ~ 10/30 = 0.333 (rounded to 3 decimals by impl)
    assert score.confidence == pytest.approx(1 / 3, abs=0.001)


# ---------------------------------------------------------------------------
# 5. Provisional flag
# ---------------------------------------------------------------------------


def test_provisional_true_within_90_day_window(
    tmp_log: Path, tmp_history: Path
) -> None:
    launched = datetime(2026, 1, 1, tzinfo=timezone.utc)
    inside = datetime(2026, 2, 15, tzinfo=timezone.utc)  # day 45

    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log,
        history_path=tmp_history,
        launched_at=launched,
        now=inside,
    )
    assert score.provisional is True
    assert any("provisional" in n for n in score.notes)


def test_provisional_false_after_90_days(tmp_log: Path, tmp_history: Path) -> None:
    launched = datetime(2026, 1, 1, tzinfo=timezone.utc)
    after = datetime(2026, 5, 1, tzinfo=timezone.utc)  # day 120

    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log,
        history_path=tmp_history,
        launched_at=launched,
        now=after,
    )
    assert score.provisional is False


def test_provisional_default_true_when_launched_at_unknown(
    tmp_log: Path, tmp_history: Path
) -> None:
    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log,
        history_path=tmp_history,
        launched_at=None,  # unknown launch
    )
    # Safer default
    assert score.provisional is True


# ---------------------------------------------------------------------------
# 6. near_eigenform alarm
# ---------------------------------------------------------------------------


def test_near_eigenform_fires_on_sustained_high(
    tmp_log: Path, tmp_history: Path
) -> None:
    # Synthesize 35 days of history all > 0.95
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    with tmp_history.open("w", encoding="utf-8") as f:
        for day_offset in range(35, 0, -1):
            ts = (now - timedelta(days=day_offset)).isoformat()
            rec = {"computed_at": ts, "r_aggregate": 0.97}
            f.write(json.dumps(rec) + "\n")

    # Seed enough recent data for a real current score with high aggregate.
    _seed_predict_resolve(tmp_log, subject_kind="gate", n_total=10, n_repaired=10)
    _seed_predict_resolve(tmp_log, subject_kind="mutation", n_total=10, n_repaired=10)
    _seed_predict_resolve(
        tmp_log, subject_kind="welfare_proposal", n_total=10, n_repaired=10
    )

    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log,
        history_path=tmp_history,
        now=now,
    )
    assert score.r_aggregate == pytest.approx(1.0)
    assert score.near_eigenform is True
    assert any("near_eigenform" in n for n in score.notes)


def test_near_eigenform_does_not_fire_when_recent_dip(
    tmp_log: Path, tmp_history: Path
) -> None:
    # Sustained-high in OLD records but recent records are below threshold.
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    with tmp_history.open("w", encoding="utf-8") as f:
        # Old high
        for day_offset in range(60, 30, -1):
            ts = (now - timedelta(days=day_offset)).isoformat()
            rec = {"computed_at": ts, "r_aggregate": 0.97}
            f.write(json.dumps(rec) + "\n")
        # Recent dip (still in 30-day window)
        for day_offset in range(29, 0, -1):
            ts = (now - timedelta(days=day_offset)).isoformat()
            rec = {"computed_at": ts, "r_aggregate": 0.60}
            f.write(json.dumps(rec) + "\n")

    _seed_predict_resolve(tmp_log, subject_kind="gate", n_total=10, n_repaired=10)
    _seed_predict_resolve(tmp_log, subject_kind="mutation", n_total=10, n_repaired=10)
    _seed_predict_resolve(
        tmp_log, subject_kind="welfare_proposal", n_total=10, n_repaired=10
    )

    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log,
        history_path=tmp_history,
        now=now,
    )
    # current is 1.0 (above threshold) but in-window history has 0.60 dips
    assert score.near_eigenform is False


def test_near_eigenform_requires_enough_history(
    tmp_log: Path, tmp_history: Path
) -> None:
    # Only 5 days of history; can't conclude sustained-high
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    with tmp_history.open("w", encoding="utf-8") as f:
        for day_offset in range(5, 0, -1):
            ts = (now - timedelta(days=day_offset)).isoformat()
            rec = {"computed_at": ts, "r_aggregate": 0.97}
            f.write(json.dumps(rec) + "\n")

    _seed_predict_resolve(tmp_log, subject_kind="gate", n_total=10, n_repaired=10)
    _seed_predict_resolve(tmp_log, subject_kind="mutation", n_total=10, n_repaired=10)
    _seed_predict_resolve(
        tmp_log, subject_kind="welfare_proposal", n_total=10, n_repaired=10
    )

    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log,
        history_path=tmp_history,
        now=now,
    )
    assert score.near_eigenform is False  # insufficient history


# ---------------------------------------------------------------------------
# 7. Persistence round-trip
# ---------------------------------------------------------------------------


def test_persist_round_trip(
    tmp_log: Path, tmp_history: Path, tmp_score: Path
) -> None:
    _seed_predict_resolve(tmp_log, subject_kind="gate", n_total=5, n_repaired=4)

    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log, history_path=tmp_history
    )
    ok = r_repair_metric.persist_repair_score(
        score, score_path=tmp_score, history_path=tmp_history
    )
    assert ok is True

    # Score file is parseable and round-trips key fields
    payload = json.loads(tmp_score.read_text(encoding="utf-8"))
    assert payload["r_gate"] == pytest.approx(0.8)
    assert payload["n_predictions_total"] == 5

    # History gained one line
    history_lines = tmp_history.read_text(encoding="utf-8").splitlines()
    assert len(history_lines) >= 1
    last = json.loads(history_lines[-1])
    assert last["r_gate"] == pytest.approx(0.8)


def test_to_dict_serializes_nan_as_null(
    tmp_log: Path, tmp_history: Path
) -> None:
    # No data -> all r_* are NaN. to_dict() must produce json-loadable output.
    score = r_repair_metric.compute_repair_score(
        log_path=tmp_log, history_path=tmp_history
    )
    d = score.to_dict()
    # Round-trip through json.dumps must not raise (NaN is invalid JSON
    # under stdlib defaults; we replace with None).
    s = json.dumps(d)
    parsed = json.loads(s)
    assert parsed["r_aggregate"] is None
    assert parsed["r_gate"] is None
