"""Gauntlet → ExternalOutcome → Supervisor wiring.

This module is the missing wire identified by the 2026-05-12 SOTA audit:

    Existing pieces (already SOTA, no rewrite needed):
        - benchmarks/gauntlet.py runs externally-grounded Tier-1 tasks
          (Karpathy autoresearch-style: fixed-budget evaluation, ground-truth
          comparison, no LLM-as-judge).
        - telemetry_plane.ExternalOutcomeRecord is the canonical persistence
          for ground-truth signals.
        - loop_supervisor.LoopSupervisor watches loop health and can
          trigger PAUSE_LOOP / ALERT_DHYANA.
        - dgm_loop._sample_parent_qd implements Sakana DGM quality-diversity
          sampling with novelty_pressure=0.7 (matches Sakana default).

    Missing wire (this module):
        Gauntlet results were written to ~/.dharma/gauntlet/history.jsonl but
        never reached the ExternalOutcome substrate, so DGM fitness, loop
        supervisor trend detection, and the catalytic graph never saw them.

This wire turns the existing components into a closed Karpathy/DGM-style
evolutionary loop without writing a new evolutionary system. The principle
matches Karpathy autoresearch (github.com/karpathy/autoresearch, Mar 2026):
direct metric comparison, fixed wall-clock budget, no statistical tests.

Public API:
    - record_gauntlet_outcome(report)  — write tier scores as ExternalOutcomes
    - load_recent_outcomes(kind, days) — read window for trend analysis
    - compute_trend_slope(scores)      — least-squares slope, simple and robust
    - check_gauntlet_trend(...)        — supervisor-style alert if regressing
"""

from __future__ import annotations

import asyncio
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from dharma_swarm.telemetry_plane import (
    ExternalOutcomeRecord,
    TelemetryPlaneStore,
)

if TYPE_CHECKING:
    from benchmarks.gauntlet import GauntletReport  # pragma: no cover

logger = logging.getLogger(__name__)


# Outcome kinds — match the existing ExternalOutcomeRecord schema convention
# (snake_case, namespaced by source). Tier-1 is the only externally-grounded
# tier today, but we expose all tiers so trend dashboards can decompose.
OUTCOME_KIND_GAUNTLET_COMPOSITE = "gauntlet.composite"
OUTCOME_KIND_GAUNTLET_TIER1 = "gauntlet.tier1.correctness"
OUTCOME_KIND_GAUNTLET_TIER2 = "gauntlet.tier2.research"
OUTCOME_KIND_GAUNTLET_TIER3 = "gauntlet.tier3.self_modification"
OUTCOME_KIND_GAUNTLET_TIER4 = "gauntlet.tier4.telos_adversarial"
OUTCOME_KIND_GAUNTLET_TIER5 = "gauntlet.tier5.emergent"

_TIER_KIND = {
    1: OUTCOME_KIND_GAUNTLET_TIER1,
    2: OUTCOME_KIND_GAUNTLET_TIER2,
    3: OUTCOME_KIND_GAUNTLET_TIER3,
    4: OUTCOME_KIND_GAUNTLET_TIER4,
    5: OUTCOME_KIND_GAUNTLET_TIER5,
}


@dataclass(frozen=True, slots=True)
class TrendResult:
    """Outcome of a trend check over a recent window.

    Attributes:
        kind: ExternalOutcome kind queried.
        n_samples: Number of outcomes in the window.
        mean: Mean value over the window.
        slope_per_day: Least-squares slope in units/day.
        latest_value: Most recent observation.
        is_regressing: True if slope is significantly negative.
        is_improving: True if slope is significantly positive.
        message: Human-readable summary.
    """

    kind: str
    n_samples: int
    mean: float
    slope_per_day: float
    latest_value: float
    is_regressing: bool
    is_improving: bool
    message: str


# ---------------------------------------------------------------------------
# Writing — gauntlet report → ExternalOutcome records
# ---------------------------------------------------------------------------

def _new_outcome_id() -> str:
    return f"oc_{uuid.uuid4().hex[:16]}"


def build_outcome_records(report: "GauntletReport") -> list[ExternalOutcomeRecord]:
    """Translate a GauntletReport into ExternalOutcomeRecord rows.

    One composite record per run, plus one record per tier with at least one
    scored task. We use ``confidence=1.0`` for Tier 1 (verifiable ground
    truth) and lower for higher tiers (graded by LLM-assisted quality).

    Args:
        report: GauntletReport from ``benchmarks.gauntlet.run_gauntlet``.

    Returns:
        List of records ready for ``TelemetryPlaneStore.record_external_outcome``.
    """
    created_at = _parse_timestamp(report.timestamp)
    records: list[ExternalOutcomeRecord] = []

    # Composite — always recorded
    records.append(
        ExternalOutcomeRecord(
            outcome_id=_new_outcome_id(),
            outcome_kind=OUTCOME_KIND_GAUNTLET_COMPOSITE,
            value=float(report.gauntlet_score),
            unit="score_0_1",
            confidence=0.9,
            status="observed",
            subject_id="dharma_swarm.system",
            summary=(
                f"Gauntlet composite={report.gauntlet_score:.3f} "
                f"(Δ{report.delta:+.3f}) over tiers {report.tiers_run}"
            ),
            run_id=report.run_id,
            metadata={
                "previous_score": report.previous_score,
                "delta": report.delta,
                "tiers_run": list(report.tiers_run),
                "top_failure_modes": list(report.top_failure_modes),
                "dgm_targets": list(report.dgm_targets),
                "duration_seconds": report.duration_seconds,
            },
            created_at=created_at,
        )
    )

    # Per-tier — group by tier, average composite-per-task within tier
    by_tier: dict[int, list[dict[str, Any]]] = {}
    for task in report.task_scores:
        tier = int(task.get("tier", 0))
        if tier in _TIER_KIND:
            by_tier.setdefault(tier, []).append(task)

    for tier, tasks in by_tier.items():
        if not tasks:
            continue
        # Per-tier value is the mean of composite scores (matches the
        # gauntlet's own aggregation).
        tier_value = sum(
            _task_composite(t) for t in tasks
        ) / len(tasks)
        pass_count = sum(1 for t in tasks if t.get("passed"))
        records.append(
            ExternalOutcomeRecord(
                outcome_id=_new_outcome_id(),
                outcome_kind=_TIER_KIND[tier],
                value=float(tier_value),
                unit="score_0_1",
                # Tier 1 = verifiable ground truth → confidence 1.0
                # Higher tiers = LLM-assisted grading → lower confidence
                confidence=1.0 if tier == 1 else 0.7,
                status="observed",
                subject_id="dharma_swarm.system",
                summary=(
                    f"Tier {tier}: {pass_count}/{len(tasks)} passed, "
                    f"mean={tier_value:.3f}"
                ),
                run_id=report.run_id,
                metadata={
                    "tier": tier,
                    "n_tasks": len(tasks),
                    "pass_count": pass_count,
                    "task_ids": [t.get("task_id", "") for t in tasks],
                },
                created_at=created_at,
            )
        )

    return records


async def record_gauntlet_outcome(
    report: "GauntletReport",
    *,
    store: TelemetryPlaneStore | None = None,
) -> list[ExternalOutcomeRecord]:
    """Persist a gauntlet report as ExternalOutcomeRecords.

    Idempotent at the run_id level only if your store enforces uniqueness;
    the gauntlet generates a fresh ``run_id`` per run so re-runs are distinct.

    Args:
        report: GauntletReport object.
        store: Optional TelemetryPlaneStore. Default opens the shared store.

    Returns:
        The records that were persisted.
    """
    store = store or TelemetryPlaneStore()
    records = build_outcome_records(report)
    persisted: list[ExternalOutcomeRecord] = []
    for rec in records:
        try:
            saved = await store.record_external_outcome(rec)
            persisted.append(saved)
        except Exception:  # pragma: no cover — keep gauntlet runs from failing
            logger.exception(
                "Failed to persist ExternalOutcomeRecord kind=%s value=%.3f",
                rec.outcome_kind, rec.value,
            )
    logger.info(
        "Recorded %d gauntlet outcomes (composite=%.3f, run_id=%s)",
        len(persisted), report.gauntlet_score, report.run_id,
    )
    return persisted


# ---------------------------------------------------------------------------
# Reading — recent outcomes window for trend analysis
# ---------------------------------------------------------------------------

async def load_recent_outcomes(
    kind: str,
    *,
    days: int = 7,
    store: TelemetryPlaneStore | None = None,
    limit: int = 500,
) -> list[ExternalOutcomeRecord]:
    """Load gauntlet outcomes from the last ``days`` days.

    Filters in Python (the store's API is kind/session/limit only). Cheap
    because gauntlet runs are sparse (nightly, not per-second).
    """
    store = store or TelemetryPlaneStore()
    all_recent = await store.list_external_outcomes(
        outcome_kind=kind, limit=limit,
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [r for r in all_recent if r.created_at >= cutoff]


# ---------------------------------------------------------------------------
# Trend analysis — Karpathy-style direct comparison, no p-values
# ---------------------------------------------------------------------------

def compute_trend_slope(
    samples: list[tuple[datetime, float]],
) -> float:
    """Least-squares slope of (datetime, value) samples, units per day.

    Returns 0.0 if fewer than 2 distinct timestamps. Pure stdlib — no
    scipy dependency. This matches the Karpathy autoresearch principle of
    direct metric comparison without statistical tests; the slope itself
    is the signal, and the supervisor's threshold (e.g. -0.01/day) is the
    decision criterion.
    """
    if len(samples) < 2:
        return 0.0
    # Anchor on the earliest timestamp; convert to days as x-axis.
    sorted_samples = sorted(samples, key=lambda s: s[0])
    t0 = sorted_samples[0][0]
    xs = [(s[0] - t0).total_seconds() / 86400.0 for s in sorted_samples]
    ys = [s[1] for s in sorted_samples]
    if max(xs) - min(xs) < 1e-9:
        return 0.0  # all samples at same moment

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if den < 1e-12:
        return 0.0
    return num / den


async def check_gauntlet_trend(
    *,
    kind: str = OUTCOME_KIND_GAUNTLET_TIER1,
    days: int = 7,
    regression_slope_threshold: float = -0.01,
    improvement_slope_threshold: float = 0.005,
    min_samples: int = 3,
    store: TelemetryPlaneStore | None = None,
) -> TrendResult:
    """Compute trend for an outcome kind over the last ``days`` days.

    Defaults are calibrated for tier-1 correctness scores in [0,1]:
        - regression_slope_threshold = -0.01/day means losing 1 percentage
          point of correctness per day, which is meaningful regression.
        - improvement_slope_threshold = +0.005/day means gaining 0.5 pp/day,
          which over a 30-day window is +15pp — the Karpathy DGM scale.
        - min_samples=3 means at least 3 nightly runs before triggering;
          this is the smallest window where a slope is interpretable.

    These thresholds are intentionally simple — Karpathy autoresearch uses
    raw metric comparison and so do we. Tune as data accumulates.
    """
    outcomes = await load_recent_outcomes(kind, days=days, store=store)
    if not outcomes:
        return TrendResult(
            kind=kind, n_samples=0, mean=0.0, slope_per_day=0.0,
            latest_value=0.0, is_regressing=False, is_improving=False,
            message=f"No {kind} outcomes in last {days} days",
        )

    samples = [(o.created_at, o.value) for o in outcomes]
    slope = compute_trend_slope(samples)
    mean = sum(o.value for o in outcomes) / len(outcomes)
    latest = max(outcomes, key=lambda o: o.created_at).value

    has_enough = len(outcomes) >= min_samples
    is_regressing = has_enough and slope <= regression_slope_threshold
    is_improving = has_enough and slope >= improvement_slope_threshold

    if is_regressing:
        msg = (
            f"REGRESSING {kind}: slope={slope:+.4f}/day over {len(outcomes)} "
            f"runs (≤ threshold {regression_slope_threshold})"
        )
    elif is_improving:
        msg = (
            f"IMPROVING {kind}: slope={slope:+.4f}/day over {len(outcomes)} "
            f"runs (≥ threshold {improvement_slope_threshold})"
        )
    elif not has_enough:
        msg = f"INSUFFICIENT {kind}: only {len(outcomes)}/{min_samples} runs"
    else:
        msg = (
            f"FLAT {kind}: slope={slope:+.4f}/day over {len(outcomes)} runs "
            f"(within [{regression_slope_threshold}, "
            f"{improvement_slope_threshold}])"
        )

    return TrendResult(
        kind=kind,
        n_samples=len(outcomes),
        mean=mean,
        slope_per_day=slope,
        latest_value=latest,
        is_regressing=is_regressing,
        is_improving=is_improving,
        message=msg,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_composite(task: dict[str, Any]) -> float:
    """Mirror of TaskScore.composite. Kept inline to avoid a circular import
    with benchmarks/gauntlet.py at module load time."""
    correctness = float(task.get("correctness", 0.0))
    quality = float(task.get("quality", 0.0))
    telos = float(task.get("telos_alignment", 0.0))
    speed = float(task.get("speed_score", 0.0))
    return correctness * 0.35 + quality * 0.30 + telos * 0.25 + speed * 0.10


def _parse_timestamp(ts: str) -> datetime:
    try:
        # Gauntlet writes isoformat with timezone; accept both.
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return datetime.now(timezone.utc)


def check_gauntlet_trend_sync(
    *,
    kind: str = OUTCOME_KIND_GAUNTLET_TIER1,
    days: int = 7,
    regression_slope_threshold: float = -0.01,
    improvement_slope_threshold: float = 0.005,
    min_samples: int = 3,
) -> TrendResult:
    """Synchronous wrapper around ``check_gauntlet_trend``.

    Used by ``loop_supervisor.LoopSupervisor.tick()``, which is fully sync.
    Safe when no event loop is running. If called from inside an existing
    loop, returns a no-op TrendResult (the supervisor will retry next tick).
    """
    try:
        # Detect already-running loop (e.g. supervisor invoked from async).
        asyncio.get_running_loop()
        return TrendResult(
            kind=kind, n_samples=0, mean=0.0, slope_per_day=0.0,
            latest_value=0.0, is_regressing=False, is_improving=False,
            message=(
                "check_gauntlet_trend_sync skipped: already inside event loop; "
                "call check_gauntlet_trend directly with await."
            ),
        )
    except RuntimeError:
        pass  # no running loop — safe to use asyncio.run

    return asyncio.run(
        check_gauntlet_trend(
            kind=kind,
            days=days,
            regression_slope_threshold=regression_slope_threshold,
            improvement_slope_threshold=improvement_slope_threshold,
            min_samples=min_samples,
        )
    )


__all__ = [
    "OUTCOME_KIND_GAUNTLET_COMPOSITE",
    "OUTCOME_KIND_GAUNTLET_TIER1",
    "OUTCOME_KIND_GAUNTLET_TIER2",
    "OUTCOME_KIND_GAUNTLET_TIER3",
    "OUTCOME_KIND_GAUNTLET_TIER4",
    "OUTCOME_KIND_GAUNTLET_TIER5",
    "TrendResult",
    "build_outcome_records",
    "record_gauntlet_outcome",
    "load_recent_outcomes",
    "compute_trend_slope",
    "check_gauntlet_trend",
    "check_gauntlet_trend_sync",
]
