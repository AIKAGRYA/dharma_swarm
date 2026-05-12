"""Tests for dharma_swarm.gauntlet_telemetry — the gauntlet → ExternalOutcome
→ supervisor trend wiring added by the 2026-05-12 SOTA rewire.

These tests cover:
    - build_outcome_records: shape, confidence assignment, per-tier grouping
    - compute_trend_slope: pure math (positive, negative, flat, edge cases)
    - record_gauntlet_outcome: round-trip persist + load via real
      TelemetryPlaneStore on a tmp_path SQLite file.
    - check_gauntlet_trend: regressing / improving / flat / insufficient classifications.

Style mirrors tests/test_telemetry_plane.py (pytest-asyncio, tmp_path DB).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from benchmarks.gauntlet import GauntletReport
from dharma_swarm.gauntlet_telemetry import (
    OUTCOME_KIND_GAUNTLET_COMPOSITE,
    OUTCOME_KIND_GAUNTLET_TIER1,
    OUTCOME_KIND_GAUNTLET_TIER2,
    build_outcome_records,
    check_gauntlet_trend,
    compute_trend_slope,
    load_recent_outcomes,
    record_gauntlet_outcome,
)
from dharma_swarm.telemetry_plane import ExternalOutcomeRecord, TelemetryPlaneStore


def _make_report(
    *,
    run_id: str = "run_test_1",
    composite: float = 0.75,
    delta: float = 0.05,
    tiers: list[int] | None = None,
    task_scores: list[dict] | None = None,
    timestamp: str | None = None,
) -> GauntletReport:
    return GauntletReport(
        run_id=run_id,
        timestamp=timestamp or "2026-05-12T00:00:00+00:00",
        tiers_run=tiers or [1, 2],
        task_scores=task_scores or [
            {"task_id": "t1-a", "tier": 1, "correctness": 1.0,
             "quality": 0.8, "telos_alignment": 0.9, "speed_score": 0.7,
             "passed": True},
            {"task_id": "t1-b", "tier": 1, "correctness": 0.5,
             "quality": 0.6, "telos_alignment": 0.5, "speed_score": 0.4,
             "passed": False},
            {"task_id": "t2-a", "tier": 2, "correctness": 0.7,
             "quality": 0.7, "telos_alignment": 0.7, "speed_score": 0.5,
             "passed": True},
        ],
        gauntlet_score=composite,
        previous_score=composite - delta,
        delta=delta,
        top_failure_modes=["wrong_answer"],
        dgm_targets=["dharma_swarm/web_search.py"],
        duration_seconds=42.0,
    )


# ---------------------------------------------------------------------------
# build_outcome_records
# ---------------------------------------------------------------------------


def test_build_outcome_records_emits_composite_plus_per_tier() -> None:
    report = _make_report()
    records = build_outcome_records(report)
    # 1 composite + tier 1 + tier 2 = 3 records
    assert len(records) == 3
    kinds = {r.outcome_kind for r in records}
    assert OUTCOME_KIND_GAUNTLET_COMPOSITE in kinds
    assert OUTCOME_KIND_GAUNTLET_TIER1 in kinds
    assert OUTCOME_KIND_GAUNTLET_TIER2 in kinds


def test_build_outcome_records_tier1_confidence_is_one() -> None:
    """Tier 1 = verifiable ground truth → confidence 1.0. Higher tiers = 0.7."""
    report = _make_report()
    by_kind = {r.outcome_kind: r for r in build_outcome_records(report)}
    assert by_kind[OUTCOME_KIND_GAUNTLET_TIER1].confidence == 1.0
    assert by_kind[OUTCOME_KIND_GAUNTLET_TIER2].confidence == 0.7
    # Composite stays at 0.9 (mixed tier sources)
    assert by_kind[OUTCOME_KIND_GAUNTLET_COMPOSITE].confidence == 0.9


def test_build_outcome_records_composite_value_matches_report() -> None:
    report = _make_report(composite=0.612)
    records = build_outcome_records(report)
    composite = next(r for r in records
                     if r.outcome_kind == OUTCOME_KIND_GAUNTLET_COMPOSITE)
    assert composite.value == pytest.approx(0.612)
    assert composite.unit == "score_0_1"
    assert composite.status == "observed"
    assert composite.run_id == report.run_id


def test_build_outcome_records_per_tier_value_is_mean_composite() -> None:
    """Per-tier value should be mean of TaskScore.composite (35/30/25/10 mix)."""
    report = _make_report()
    by_kind = {r.outcome_kind: r for r in build_outcome_records(report)}
    # Tier 1 manual computation:
    # task a: 1.0*.35 + .8*.3 + .9*.25 + .7*.1 = .35 + .24 + .225 + .07 = 0.885
    # task b: .5*.35 + .6*.3 + .5*.25 + .4*.1 = .175 + .18 + .125 + .04 = 0.520
    # mean = (0.885 + 0.520) / 2 = 0.7025
    assert by_kind[OUTCOME_KIND_GAUNTLET_TIER1].value == pytest.approx(0.7025)


def test_build_outcome_records_skips_tiers_with_no_tasks() -> None:
    report = _make_report(
        tiers=[1],
        task_scores=[
            {"task_id": "t1-only", "tier": 1, "correctness": 0.9,
             "quality": 0.9, "telos_alignment": 0.9, "speed_score": 0.9,
             "passed": True},
        ],
    )
    records = build_outcome_records(report)
    # composite + tier 1 only
    assert len(records) == 2
    kinds = {r.outcome_kind for r in records}
    assert OUTCOME_KIND_GAUNTLET_TIER2 not in kinds


# ---------------------------------------------------------------------------
# compute_trend_slope
# ---------------------------------------------------------------------------


def test_compute_trend_slope_positive() -> None:
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    samples = [
        (base + timedelta(days=0), 0.50),
        (base + timedelta(days=1), 0.55),
        (base + timedelta(days=2), 0.60),
        (base + timedelta(days=3), 0.65),
    ]
    slope = compute_trend_slope(samples)
    assert slope == pytest.approx(0.05, abs=1e-9)


def test_compute_trend_slope_negative() -> None:
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    samples = [
        (base + timedelta(days=0), 0.80),
        (base + timedelta(days=1), 0.70),
        (base + timedelta(days=2), 0.60),
    ]
    slope = compute_trend_slope(samples)
    assert slope == pytest.approx(-0.10, abs=1e-9)


def test_compute_trend_slope_flat() -> None:
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    samples = [
        (base + timedelta(days=i), 0.60) for i in range(5)
    ]
    assert compute_trend_slope(samples) == pytest.approx(0.0, abs=1e-9)


def test_compute_trend_slope_handles_too_few_samples() -> None:
    assert compute_trend_slope([]) == 0.0
    assert compute_trend_slope(
        [(datetime(2026, 5, 1, tzinfo=timezone.utc), 0.5)]
    ) == 0.0


def test_compute_trend_slope_handles_duplicate_timestamps() -> None:
    """All samples at the same instant → slope undefined → 0.0."""
    t = datetime(2026, 5, 1, tzinfo=timezone.utc)
    samples = [(t, 0.5), (t, 0.6), (t, 0.7)]
    assert compute_trend_slope(samples) == 0.0


def test_compute_trend_slope_is_unaffected_by_ordering() -> None:
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    forward = [
        (base + timedelta(days=i), 0.5 + 0.02 * i) for i in range(5)
    ]
    backward = list(reversed(forward))
    assert math.isclose(
        compute_trend_slope(forward),
        compute_trend_slope(backward),
        abs_tol=1e-9,
    )


# ---------------------------------------------------------------------------
# record_gauntlet_outcome + load_recent_outcomes (round-trip)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_gauntlet_outcome_round_trip(tmp_path) -> None:
    store = TelemetryPlaneStore(tmp_path / "runtime.db")
    report = _make_report()
    persisted = await record_gauntlet_outcome(report, store=store)
    # 1 composite + tier 1 + tier 2
    assert len(persisted) == 3

    loaded_composite = await load_recent_outcomes(
        OUTCOME_KIND_GAUNTLET_COMPOSITE, days=7, store=store,
    )
    assert len(loaded_composite) == 1
    assert loaded_composite[0].run_id == report.run_id
    assert loaded_composite[0].value == pytest.approx(report.gauntlet_score)

    loaded_tier1 = await load_recent_outcomes(
        OUTCOME_KIND_GAUNTLET_TIER1, days=7, store=store,
    )
    assert len(loaded_tier1) == 1
    assert loaded_tier1[0].confidence == 1.0


@pytest.mark.asyncio
async def test_load_recent_outcomes_respects_day_window(tmp_path) -> None:
    """An outcome older than the window should not be returned."""
    store = TelemetryPlaneStore(tmp_path / "runtime.db")
    old = ExternalOutcomeRecord(
        outcome_id="oc_old",
        outcome_kind=OUTCOME_KIND_GAUNTLET_TIER1,
        value=0.5,
        unit="score_0_1",
        confidence=1.0,
        status="observed",
        subject_id="dharma_swarm.system",
        summary="old",
        run_id="run_old",
        metadata={},
        created_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    fresh = ExternalOutcomeRecord(
        outcome_id="oc_new",
        outcome_kind=OUTCOME_KIND_GAUNTLET_TIER1,
        value=0.8,
        unit="score_0_1",
        confidence=1.0,
        status="observed",
        subject_id="dharma_swarm.system",
        summary="new",
        run_id="run_new",
        metadata={},
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    await store.record_external_outcome(old)
    await store.record_external_outcome(fresh)

    window = await load_recent_outcomes(
        OUTCOME_KIND_GAUNTLET_TIER1, days=7, store=store,
    )
    ids = {o.outcome_id for o in window}
    assert "oc_new" in ids
    assert "oc_old" not in ids


# ---------------------------------------------------------------------------
# check_gauntlet_trend
# ---------------------------------------------------------------------------


async def _seed_outcomes(
    store: TelemetryPlaneStore, values: list[float], *,
    kind: str = OUTCOME_KIND_GAUNTLET_TIER1,
) -> None:
    """Seed nightly outcomes one day apart, oldest first."""
    now = datetime.now(timezone.utc)
    n = len(values)
    for i, v in enumerate(values):
        await store.record_external_outcome(
            ExternalOutcomeRecord(
                outcome_id=f"oc_seed_{i}",
                outcome_kind=kind,
                value=v,
                unit="score_0_1",
                confidence=1.0,
                status="observed",
                subject_id="dharma_swarm.system",
                summary=f"seed {i}",
                run_id=f"run_seed_{i}",
                metadata={},
                created_at=now - timedelta(days=(n - 1 - i)),
            )
        )


@pytest.mark.asyncio
async def test_check_gauntlet_trend_detects_regression(tmp_path) -> None:
    store = TelemetryPlaneStore(tmp_path / "runtime.db")
    await _seed_outcomes(store, [0.80, 0.70, 0.60, 0.50, 0.40])
    result = await check_gauntlet_trend(days=7, store=store)
    assert result.n_samples == 5
    assert result.is_regressing is True
    assert result.is_improving is False
    assert result.slope_per_day < 0
    assert "REGRESSING" in result.message


@pytest.mark.asyncio
async def test_check_gauntlet_trend_detects_improvement(tmp_path) -> None:
    store = TelemetryPlaneStore(tmp_path / "runtime.db")
    await _seed_outcomes(store, [0.50, 0.55, 0.60, 0.65, 0.70])
    result = await check_gauntlet_trend(days=7, store=store)
    assert result.is_improving is True
    assert result.is_regressing is False
    assert result.slope_per_day > 0
    assert "IMPROVING" in result.message


@pytest.mark.asyncio
async def test_check_gauntlet_trend_flat_is_neither(tmp_path) -> None:
    store = TelemetryPlaneStore(tmp_path / "runtime.db")
    await _seed_outcomes(store, [0.70, 0.70, 0.70, 0.70])
    result = await check_gauntlet_trend(days=7, store=store)
    assert result.is_regressing is False
    assert result.is_improving is False


@pytest.mark.asyncio
async def test_check_gauntlet_trend_insufficient_samples(tmp_path) -> None:
    store = TelemetryPlaneStore(tmp_path / "runtime.db")
    await _seed_outcomes(store, [0.10, 0.20])  # only 2 < min_samples=3
    result = await check_gauntlet_trend(days=7, store=store)
    assert result.is_regressing is False
    assert result.is_improving is False
    assert "INSUFFICIENT" in result.message


@pytest.mark.asyncio
async def test_check_gauntlet_trend_no_data_is_safe(tmp_path) -> None:
    store = TelemetryPlaneStore(tmp_path / "runtime.db")
    result = await check_gauntlet_trend(days=7, store=store)
    assert result.n_samples == 0
    assert result.is_regressing is False
    assert result.is_improving is False
