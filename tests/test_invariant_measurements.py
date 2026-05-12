from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.operator_core.invariant_measurements import (
    build_invariant_measurements,
    build_invariant_measurements_from_db,
    linear_slope_per_day,
    record_measurements_as_workflow_scores,
    recursive_transition_anchor_coverage,
)
from dharma_swarm.telemetry_plane import (
    ExternalOutcomeRecord,
    TelemetryPlaneStore,
    WorkflowScoreRecord,
)


def _stamp(day: int) -> datetime:
    return datetime(2026, 5, 1, tzinfo=timezone.utc) + timedelta(days=day)


def test_linear_slope_per_day_computes_simple_trend() -> None:
    samples = [(_stamp(0), 0.50), (_stamp(1), 0.55), (_stamp(2), 0.60)]
    assert linear_slope_per_day(samples) == pytest.approx(0.05)


def test_build_measurements_marks_gauntlet_tier1_positive_slope_healthy(tmp_path) -> None:
    outcomes = [
        ExternalOutcomeRecord(
            outcome_id=f"out-{idx}",
            outcome_kind="gauntlet.tier1.correctness",
            value=value,
            created_at=_stamp(idx),
        )
        for idx, value in enumerate([0.70, 0.706, 0.712, 0.718])
    ]

    measurements = build_invariant_measurements(
        external_outcomes=outcomes,
        repo_root=tmp_path,
        now=_stamp(10),
    )
    by_id = {item.measurement_id: item for item in measurements}

    assert by_id["external_outcomes.coverage"].value == 4.0
    trend = by_id["external_outcome.gauntlet_tier1_correctness.slope"]
    assert trend.value == pytest.approx(0.006)
    assert trend.status == "healthy"
    assert trend.metadata["outcome_kind"] == "gauntlet.tier1.correctness"


def test_build_measurements_marks_gauntlet_tier1_regression() -> None:
    outcomes = [
        ExternalOutcomeRecord(
            outcome_id=f"out-{idx}",
            outcome_kind="gauntlet.tier1.correctness",
            value=value,
            created_at=_stamp(idx),
        )
        for idx, value in enumerate([0.80, 0.78, 0.76])
    ]

    measurements = build_invariant_measurements(external_outcomes=outcomes)
    by_id = {item.measurement_id: item for item in measurements}

    trend = by_id["external_outcome.gauntlet_tier1_correctness.slope"]
    assert trend.value == pytest.approx(-0.02)
    assert trend.status == "regression"


def test_recursive_transition_anchor_coverage_reports_missing_anchors(tmp_path) -> None:
    (tmp_path / "dharma_swarm").mkdir()
    (tmp_path / "dharma_swarm" / "cascade.py").write_text("# ok\n")

    measurement = recursive_transition_anchor_coverage(repo_root=tmp_path)

    assert measurement.value < 1.0
    assert measurement.status == "regression"
    assert any(code.startswith("missing_anchor:") for code in measurement.gap_codes)


@pytest.mark.asyncio
async def test_build_measurements_from_db_reads_existing_telemetry(tmp_path) -> None:
    db_path = tmp_path / "runtime.db"
    store = TelemetryPlaneStore(db_path)
    await store.init_db()
    for idx, value in enumerate([0.20, 0.30, 0.40]):
        await store.record_external_outcome(
            ExternalOutcomeRecord(
                outcome_id=f"outcome-{idx}",
                outcome_kind="provider_smoke_probe",
                value=value,
                created_at=_stamp(idx),
            )
        )
    for idx, value in enumerate([0.10, 0.15, 0.20]):
        await store.record_workflow_score(
            WorkflowScoreRecord(
                score_id=f"score-{idx}",
                workflow_id="wf",
                score_name="route_quality",
                score_value=value,
                recorded_at=_stamp(idx),
            )
        )

    measurements = build_invariant_measurements_from_db(db_path, repo_root=tmp_path)
    by_id = {item.measurement_id: item for item in measurements}

    assert by_id["external_outcome.provider_smoke_probe.slope"].value == pytest.approx(0.1)
    assert by_id["workflow_score.route_quality.slope"].value == pytest.approx(0.05)


@pytest.mark.asyncio
async def test_record_measurements_as_workflow_scores_is_explicit_opt_in(tmp_path) -> None:
    store = TelemetryPlaneStore(tmp_path / "runtime.db")
    await store.init_db()
    measurements = build_invariant_measurements(
        external_outcomes=[
            ExternalOutcomeRecord(
                outcome_id="outcome-1",
                outcome_kind="gauntlet.tier1.correctness",
                value=0.5,
                created_at=_stamp(0),
            ),
            ExternalOutcomeRecord(
                outcome_id="outcome-2",
                outcome_kind="gauntlet.tier1.correctness",
                value=0.6,
                created_at=_stamp(1),
            ),
        ],
        now=_stamp(2),
    )

    records = await record_measurements_as_workflow_scores(store, measurements)
    loaded = await store.list_workflow_scores(
        workflow_id="invariant_measurement_plane",
        limit=20,
    )

    assert len(records) == len(measurements)
    assert {row.score_name for row in loaded} == {item.measurement_id for item in measurements}
    trend_record = [
        row for row in loaded
        if row.score_name == "external_outcome.gauntlet_tier1_correctness.slope"
    ][0]
    assert trend_record.metadata["status"] == "healthy"
