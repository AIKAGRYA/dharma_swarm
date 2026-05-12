"""Read-only invariant measurement plane.

This module is the small, boring first version of the "Invariant Observatory"
idea.  It does not own state, route work, gate execution, or introduce a new
control plane.  It reads existing telemetry/runtime evidence and projects that
evidence into typed measurements that can be shown by operator projections or,
when explicitly requested by a caller, persisted as ``workflow_scores``.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import uuid4

from dharma_swarm.telemetry_plane import (
    DEFAULT_TELEMETRY_DB,
    ExternalOutcomeRecord,
    TelemetryPlaneStore,
    WorkflowScoreRecord,
)
from dharma_swarm.telemetry_plane import (
    _row_to_external_outcome,
    _row_to_workflow_score,
)


SECONDS_PER_DAY = 86_400.0

DEFAULT_RTN_ANCHORS: dict[str, str] = {
    "universal_phase_loop": "dharma_swarm/cascade.py",
    "workflow_dag": "dharma_swarm/workflow_graph.py",
    "credibility_layers": "dharma_swarm/jk_subteams.py",
    "catalytic_graph": "dharma_swarm/catalytic_graph.py",
    "fitness_landscape": "dharma_swarm/landscape.py",
    "recognition_value": "dharma_swarm/rv.py",
    "evolution_archive": "dharma_swarm/archive.py",
    "selection_pressure": "dharma_swarm/selector.py",
    "telemetry_plane": "dharma_swarm/telemetry_plane.py",
    "loop_supervisor": "dharma_swarm/loop_supervisor.py",
}


@dataclass(frozen=True)
class InvariantMeasurement:
    """One computed invariant-plane reading.

    The fields are intentionally close to the control-surface row language:
    status and gap_codes let downstream projections show "declared vs observed"
    without granting this measurement layer any authority.
    """

    measurement_id: str
    family: str
    name: str
    value: float
    unit: str = ""
    status: str = "unknown"
    window: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    gap_codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["computed_at"] = self.computed_at.isoformat()
        return payload

    def to_workflow_score_record(
        self,
        *,
        workflow_id: str = "invariant_measurement_plane",
        score_id: str | None = None,
    ) -> WorkflowScoreRecord:
        """Project this measurement into the existing workflow_scores table."""

        return WorkflowScoreRecord(
            score_id=score_id or f"invariant_{uuid4().hex[:16]}",
            workflow_id=workflow_id,
            score_name=self.measurement_id,
            score_value=float(self.value),
            evidence=list(self.evidence),
            metadata={
                "family": self.family,
                "name": self.name,
                "status": self.status,
                "window": self.window,
                "unit": self.unit,
                "gap_codes": list(self.gap_codes),
                **self.metadata,
            },
            recorded_at=self.computed_at,
        )


def build_invariant_measurements(
    *,
    external_outcomes: Sequence[ExternalOutcomeRecord] = (),
    workflow_scores: Sequence[WorkflowScoreRecord] = (),
    repo_root: Path | None = None,
    max_series: int = 8,
    now: datetime | None = None,
) -> list[InvariantMeasurement]:
    """Build invariant measurements from already-loaded records.

    This pure-ish function is the main testing seam.  It avoids async, network
    calls, and writes.  Callers can feed it temp telemetry rows or production
    telemetry rows.
    """

    computed_at = now or datetime.now(timezone.utc)
    measurements: list[InvariantMeasurement] = [
        recursive_transition_anchor_coverage(repo_root=repo_root, now=computed_at),
        external_outcome_coverage(external_outcomes, now=computed_at),
    ]
    measurements.extend(
        _external_outcome_trends(
            external_outcomes,
            max_series=max_series,
            now=computed_at,
        )
    )
    measurements.extend(
        _workflow_score_trends(
            workflow_scores,
            max_series=max_series,
            now=computed_at,
        )
    )
    return measurements


def build_invariant_measurements_from_db(
    db_path: Path | None = None,
    *,
    repo_root: Path | None = None,
    limit: int = 500,
    max_series: int = 8,
) -> list[InvariantMeasurement]:
    """Read the canonical telemetry DB and build invariant measurements.

    The connection is opened read-only.  Missing DBs/tables are treated as
    missing evidence, not as an error.
    """

    if limit < 1 or limit > 10_000:
        raise ValueError("limit must be between 1 and 10000")

    resolved = db_path or DEFAULT_TELEMETRY_DB
    if not resolved.exists():
        return build_invariant_measurements(repo_root=repo_root, max_series=max_series)

    outcomes: list[ExternalOutcomeRecord] = []
    scores: list[WorkflowScoreRecord] = []
    try:
        uri = f"file:{resolved}?mode=ro"
        with sqlite3.connect(uri, uri=True) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=30000")
            outcome_rows = db.execute(
                "SELECT outcome_id, session_id, task_id, run_id, outcome_kind,"
                " subject_id, value, unit, confidence, status, summary,"
                " metadata_json, created_at"
                " FROM external_outcomes ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            score_rows = db.execute(
                "SELECT score_id, workflow_id, session_id, task_id, run_id,"
                " score_name, score_value, weighting, evidence_json,"
                " metadata_json, recorded_at"
                " FROM workflow_scores ORDER BY recorded_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        outcomes = [_row_to_external_outcome(row) for row in outcome_rows]
        scores = [_row_to_workflow_score(row) for row in score_rows]
    except sqlite3.Error:
        outcomes = []
        scores = []

    return build_invariant_measurements(
        external_outcomes=outcomes,
        workflow_scores=scores,
        repo_root=repo_root,
        max_series=max_series,
    )


async def record_measurements_as_workflow_scores(
    store: TelemetryPlaneStore,
    measurements: Iterable[InvariantMeasurement],
    *,
    workflow_id: str = "invariant_measurement_plane",
) -> list[WorkflowScoreRecord]:
    """Persist explicit measurement readings into workflow_scores.

    This is opt-in.  Importing or projecting invariant measurements never writes
    to disk by itself.
    """

    records: list[WorkflowScoreRecord] = []
    for measurement in measurements:
        record = measurement.to_workflow_score_record(workflow_id=workflow_id)
        await store.record_workflow_score(record)
        records.append(record)
    return records


def recursive_transition_anchor_coverage(
    *,
    repo_root: Path | None = None,
    anchors: dict[str, str] | None = None,
    now: datetime | None = None,
) -> InvariantMeasurement:
    """Measure whether the known RTN anchor modules are present."""

    root = repo_root or _repo_root()
    expected = anchors or DEFAULT_RTN_ANCHORS
    present: list[str] = []
    missing: list[str] = []
    for anchor_id, rel_path in expected.items():
        if (root / rel_path).exists():
            present.append(anchor_id)
        else:
            missing.append(anchor_id)

    total = len(expected)
    value = len(present) / total if total else 0.0
    status = "healthy" if value == 1.0 else "degraded" if value >= 0.75 else "regression"
    gap_codes = [f"missing_anchor:{item}" for item in missing]
    return InvariantMeasurement(
        measurement_id="recursive_transition.anchor_coverage",
        family="recursive_transition_network",
        name="RTN Anchor Coverage",
        value=round(value, 4),
        unit="ratio",
        status=status,
        evidence=[
            {"kind": "anchor_count", "present": len(present), "total": total},
            {"kind": "present", "anchors": present},
        ],
        gap_codes=gap_codes,
        metadata={"missing": missing},
        computed_at=now or datetime.now(timezone.utc),
    )


def external_outcome_coverage(
    external_outcomes: Sequence[ExternalOutcomeRecord],
    *,
    now: datetime | None = None,
) -> InvariantMeasurement:
    """Measure whether the invariant plane has externally-grounded data."""

    counts = Counter(record.outcome_kind for record in external_outcomes)
    total = sum(counts.values())
    status = "healthy" if total >= 10 else "degraded" if total >= 2 else "insufficient_data"
    gap_codes = [] if total else ["external_outcomes_missing"]
    return InvariantMeasurement(
        measurement_id="external_outcomes.coverage",
        family="external_grounding",
        name="External Outcome Coverage",
        value=float(total),
        unit="records",
        status=status,
        evidence=[
            {"kind": "outcome_kind_counts", "counts": dict(counts)},
        ],
        gap_codes=gap_codes,
        metadata={"distinct_outcome_kinds": len(counts)},
        computed_at=now or datetime.now(timezone.utc),
    )


def _external_outcome_trends(
    external_outcomes: Sequence[ExternalOutcomeRecord],
    *,
    max_series: int,
    now: datetime,
) -> list[InvariantMeasurement]:
    grouped: dict[str, list[ExternalOutcomeRecord]] = defaultdict(list)
    for record in external_outcomes:
        grouped[record.outcome_kind].append(record)

    selected = _select_series(grouped.keys(), grouped, max_series=max_series)
    measurements: list[InvariantMeasurement] = []
    for outcome_kind in selected:
        records = sorted(grouped[outcome_kind], key=lambda item: item.created_at)
        samples = [(record.created_at, record.value) for record in records]
        slope = linear_slope_per_day(samples)
        if slope is None:
            continue
        measurements.append(
            InvariantMeasurement(
                measurement_id=f"external_outcome.{_slug(outcome_kind)}.slope",
                family="external_grounding",
                name=f"{outcome_kind} Trend",
                value=round(slope, 6),
                unit="value_per_day",
                status=_trend_status(outcome_kind, slope),
                window=_window_label(samples),
                evidence=[
                    {"kind": "sample_count", "value": len(samples)},
                    {"kind": "first_value", "value": samples[0][1]},
                    {"kind": "last_value", "value": samples[-1][1]},
                ],
                metadata={"outcome_kind": outcome_kind},
                computed_at=now,
            )
        )
    return measurements


def _workflow_score_trends(
    workflow_scores: Sequence[WorkflowScoreRecord],
    *,
    max_series: int,
    now: datetime,
) -> list[InvariantMeasurement]:
    grouped: dict[str, list[WorkflowScoreRecord]] = defaultdict(list)
    for record in workflow_scores:
        grouped[record.score_name].append(record)

    selected = _select_series(grouped.keys(), grouped, max_series=max_series)
    measurements: list[InvariantMeasurement] = []
    for score_name in selected:
        records = sorted(grouped[score_name], key=lambda item: item.recorded_at)
        samples = [(record.recorded_at, record.score_value) for record in records]
        slope = linear_slope_per_day(samples)
        if slope is None:
            continue
        measurements.append(
            InvariantMeasurement(
                measurement_id=f"workflow_score.{_slug(score_name)}.slope",
                family="workflow_score",
                name=f"{score_name} Trend",
                value=round(slope, 6),
                unit="score_per_day",
                status=_trend_status(score_name, slope),
                window=_window_label(samples),
                evidence=[
                    {"kind": "sample_count", "value": len(samples)},
                    {"kind": "first_value", "value": samples[0][1]},
                    {"kind": "last_value", "value": samples[-1][1]},
                ],
                metadata={"score_name": score_name},
                computed_at=now,
            )
        )
    return measurements


def linear_slope_per_day(samples: Sequence[tuple[datetime, float]]) -> float | None:
    """Return simple least-squares slope in value units per day."""

    if len(samples) < 2:
        return None
    ordered = sorted(samples, key=lambda item: item[0])
    base = ordered[0][0]
    xs = [(stamp - base).total_seconds() / SECONDS_PER_DAY for stamp, _ in ordered]
    ys = [float(value) for _, value in ordered]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom <= 0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom


def _select_series(
    names: Iterable[str],
    grouped: dict[str, Sequence[Any]],
    *,
    max_series: int,
) -> list[str]:
    priority = []
    regular = []
    for name in names:
        lowered = name.lower()
        item = (name, len(grouped[name]))
        if any(token in lowered for token in ("gauntlet", "tier1", "invariant", "provider")):
            priority.append(item)
        else:
            regular.append(item)
    ordered = sorted(priority, key=lambda item: (-item[1], item[0]))
    ordered.extend(sorted(regular, key=lambda item: (-item[1], item[0])))
    return [name for name, _ in ordered[:max_series]]


def _trend_status(name: str, slope: float) -> str:
    lowered = name.lower()
    if "gauntlet" in lowered and ("tier1" in lowered or "tier_1" in lowered):
        if slope >= 0.005:
            return "healthy"
        if slope <= -0.01:
            return "regression"
        return "degraded"
    if slope > 0:
        return "healthy"
    if slope < 0:
        return "degraded"
    return "unknown"


def _window_label(samples: Sequence[tuple[datetime, float]]) -> str:
    if len(samples) < 2:
        return ""
    first = samples[0][0].date().isoformat()
    last = samples[-1][0].date().isoformat()
    return f"{first}..{last}"


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "ACTIVE_SURFACE_MANIFEST.yaml").exists():
            return parent
    return Path.cwd()


def _slug(value: str) -> str:
    chars = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "_":
            chars.append("_")
    slug = "".join(chars).strip("_")
    return slug or "unknown"


__all__ = [
    "InvariantMeasurement",
    "build_invariant_measurements",
    "build_invariant_measurements_from_db",
    "external_outcome_coverage",
    "linear_slope_per_day",
    "record_measurements_as_workflow_scores",
    "recursive_transition_anchor_coverage",
]
