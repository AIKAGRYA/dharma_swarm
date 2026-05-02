"""drift_monitor - post-deployment drift surveillance for kept mutations.

Component 1.4 of the OMEGA Layer + Causal Closure plan
(~/.claude/plans/a-structural-dazzling-garden.md).

WHAT THIS DOES
--------------
The plan: "Mutations that were 'kept' stay under observation at T+25
and T+100; decay below threshold emits a walk-back register mark."

When strange_loop's _measure_decide keeps a mutation at T+5 (the
existing measurement window), the organism commits to it permanently.
But mutations can decay over longer windows: a routing change that
helped at T+5 may produce drift at T+25 as new patterns emerge, or
silently regress at T+100 as workload distribution shifts.

DriftMonitor maintains a watch list of kept mutations + their target
re-measurement cycles. On each heartbeat, it compares CURRENT pulse
metrics against the mutation's post_metrics_t5 (the metrics that
justified keeping it). If decay exceeds DRIFT_TOLERANCE at a target
cycle, it writes a register mark with:
  - discipline = "post_deployment_drift"
  - corrects = <original mutation's register mark id>
  - recommended_action = "revert_for_review"
  - severity per how bad the drift is

NEVER AUTO-REVERTS
This is a SIGNAL, not a verdict. Drift could be exogenous (workload
changed, new agents added) rather than caused by the mutation. The
mark goes through the human-in-loop path. strange_loop and the
DarwinEngine see the mark in the register-digest; the user decides
whether to actually revert.

DESIGN: ZERO MODIFICATION TO STRANGE_LOOP.PY
Per the plan's "minimize merge-conflict surface" discipline, this is
shipped as a STANDALONE module. Wiring at the merge phase:
  - When strange_loop's _measure_decide keeps a mutation, ALSO call:
        drift_monitor.add_watch(mutation_id, parameter,
                                pre_metrics, post_metrics_t5,
                                kept_at_cycle, original_mark_id)
  - organism.py heartbeat ALSO calls:
        drift_monitor.tick(current_cycle, current_metrics)

WATCH-LIST CADENCE
The plan specifies T+25 and T+100. We schedule both per watch entry.
Each entry has a list of (target_cycle, snapshot_kind) pairs. After
all targets fire, the watch is removed. Watches that haven't fired
their last target in MAX_WATCH_AGE cycles are evicted to prevent
unbounded growth.

DRIFT DETECTION HEURISTIC
A metric has decayed when it has lost more than DRIFT_TOLERANCE
(default 0.5, i.e. 50%) of its T+5 gain over T-1 (pre_metrics).

    gain_at_t5 = post_metrics_t5 - pre_metrics    # the improvement
    current_gain = current_metrics - pre_metrics  # current vs baseline
    decay_ratio = (gain_at_t5 - current_gain) / abs(gain_at_t5)
    drift_detected = decay_ratio > DRIFT_TOLERANCE

The decay must hold across MAJORITY of measured metrics (>50%) to
fire — single-metric noise doesn't trigger.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .register_disciplines import (
    DEFAULT_REGISTER_LOG,
    DisciplineResult,
    make_register_mark,
    write_register_mark,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_WATCH_PATH = (
    Path.home() / ".dharma" / "organism_memory" / "drift_watch.jsonl"
)

# Default re-measurement cycles relative to kept_at_cycle.
DEFAULT_TARGET_CYCLES: tuple[int, ...] = (25, 100)

# Decay fraction that triggers drift. 0.5 = lost half of T+5 gain.
DRIFT_TOLERANCE: float = 0.5

# Fraction of measured metrics that must show decay for drift to fire.
DECAY_QUORUM: float = 0.5

# Max age (in cycles) a watch can sit before eviction.
MAX_WATCH_AGE: int = 1000

# Floor for "the gain was material" — if abs(post_t5 - pre) is below this,
# we don't fire drift (the original improvement was noise; subsequent
# decay is also noise).
MATERIAL_GAIN_FLOOR: float = 0.01


# ---------------------------------------------------------------------------
# Watch entry
# ---------------------------------------------------------------------------


@dataclass
class DriftWatch:
    """A kept mutation under post-deployment surveillance."""

    mutation_id: str
    parameter: str
    pre_metrics: dict[str, float]  # baseline before the mutation
    post_metrics_t5: dict[str, float]  # snapshot at T+5 (the keep decision)
    kept_at_cycle: int
    original_mark_id: str  # the register mark for the kept decision (corrects target)
    targets_remaining: list[int] = field(default_factory=list)
    targets_fired: list[int] = field(default_factory=list)

    def next_target(self) -> int | None:
        """Soonest pending target cycle (relative to kept_at_cycle)."""
        if not self.targets_remaining:
            return None
        return min(self.targets_remaining)

    def absolute_target(self) -> int | None:
        """Absolute (heartbeat) cycle when next target fires."""
        nt = self.next_target()
        if nt is None:
            return None
        return self.kept_at_cycle + nt

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DriftWatch":
        return cls(
            mutation_id=str(d.get("mutation_id", "")),
            parameter=str(d.get("parameter", "")),
            pre_metrics=dict(d.get("pre_metrics", {})),
            post_metrics_t5=dict(d.get("post_metrics_t5", {})),
            kept_at_cycle=int(d.get("kept_at_cycle", 0)),
            original_mark_id=str(d.get("original_mark_id", "")),
            targets_remaining=list(d.get("targets_remaining", [])),
            targets_fired=list(d.get("targets_fired", [])),
        )


# ---------------------------------------------------------------------------
# DriftMonitor
# ---------------------------------------------------------------------------


class DriftMonitor:
    """Owns the persistent watch list and fires drift marks on decay.

    Lifecycle:
        monitor = DriftMonitor()
        # When strange_loop keeps a mutation:
        monitor.add_watch(mutation_id="abc", parameter="routing_bias",
                          pre_metrics={"health": 0.6},
                          post_metrics_t5={"health": 0.85},
                          kept_at_cycle=100,
                          original_mark_id="mark-xyz")
        # On each heartbeat:
        marks = monitor.tick(current_cycle=125,
                             current_metrics={"health": 0.65})
        # marks: list of drift-mark dicts written

    NOT thread-safe. Single-writer (heartbeat loop).
    """

    def __init__(
        self,
        *,
        watch_path: Path | None = None,
        register_marks_path: Path | None = None,
        target_cycles: tuple[int, ...] = DEFAULT_TARGET_CYCLES,
        drift_tolerance: float = DRIFT_TOLERANCE,
    ) -> None:
        self.watch_path = watch_path or DEFAULT_WATCH_PATH
        self.register_marks_path = register_marks_path or DEFAULT_REGISTER_LOG
        self.target_cycles = tuple(sorted(target_cycles))
        self.drift_tolerance = float(drift_tolerance)
        self._watches: list[DriftWatch] = []
        self._load_watches()

    # ------------------------------------------------------------------
    # Watch management
    # ------------------------------------------------------------------

    def add_watch(
        self,
        *,
        mutation_id: str,
        parameter: str,
        pre_metrics: dict[str, float],
        post_metrics_t5: dict[str, float],
        kept_at_cycle: int,
        original_mark_id: str,
        target_cycles: tuple[int, ...] | None = None,
    ) -> bool:
        """Register a kept mutation for post-deployment surveillance.

        Idempotent: re-adding the same mutation_id is a no-op (returns False).
        """
        if not mutation_id:
            return False
        for existing in self._watches:
            if existing.mutation_id == mutation_id:
                return False

        targets = list(target_cycles or self.target_cycles)
        watch = DriftWatch(
            mutation_id=mutation_id,
            parameter=parameter,
            pre_metrics=dict(pre_metrics),
            post_metrics_t5=dict(post_metrics_t5),
            kept_at_cycle=int(kept_at_cycle),
            original_mark_id=original_mark_id,
            targets_remaining=targets,
            targets_fired=[],
        )
        self._watches.append(watch)
        self._save_watches()
        return True

    def watch_count(self) -> int:
        return len(self._watches)

    def remove_watch(self, mutation_id: str) -> bool:
        """Manually remove a watch (e.g., after operator review)."""
        before = len(self._watches)
        self._watches = [w for w in self._watches if w.mutation_id != mutation_id]
        if len(self._watches) != before:
            self._save_watches()
            return True
        return False

    # ------------------------------------------------------------------
    # Heartbeat tick
    # ------------------------------------------------------------------

    def tick(
        self,
        current_cycle: int,
        current_metrics: dict[str, float],
    ) -> list[dict]:
        """Check all watches whose next target has elapsed; fire drift marks.

        Returns list of mark-summary dicts produced this tick.
        Watches whose targets are all fired (or are too old) are evicted.
        """
        produced: list[dict] = []
        survivors: list[DriftWatch] = []
        changed = False

        for watch in self._watches:
            # Eviction by age
            if current_cycle - watch.kept_at_cycle > MAX_WATCH_AGE:
                changed = True
                continue

            absolute_target = watch.absolute_target()
            if absolute_target is None:
                # All targets fired; evict
                changed = True
                continue

            if current_cycle < absolute_target:
                # Window not yet elapsed
                survivors.append(watch)
                continue

            # Target elapsed: check drift
            target_relative = watch.next_target()
            assert target_relative is not None  # next_target was non-None

            drift = _detect_drift(
                pre=watch.pre_metrics,
                post_t5=watch.post_metrics_t5,
                current=current_metrics,
                tolerance=self.drift_tolerance,
                quorum=DECAY_QUORUM,
            )

            if drift["fired"]:
                mark = self._write_drift_mark(
                    watch=watch,
                    target_relative=target_relative,
                    drift=drift,
                    current_metrics=current_metrics,
                )
                if mark is not None:
                    produced.append({
                        "mutation_id": watch.mutation_id,
                        "original_mark_id": watch.original_mark_id,
                        "drift_mark_id": mark.get("mark_id"),
                        "target_cycle": target_relative,
                        "decay_ratio": drift["decay_ratio"],
                    })

            # Advance watch state regardless of fire (target consumed)
            watch.targets_fired.append(target_relative)
            watch.targets_remaining = [
                t for t in watch.targets_remaining if t != target_relative
            ]
            changed = True

            if watch.targets_remaining:
                survivors.append(watch)
            # else: all targets fired -> evicted

        if changed:
            self._watches = survivors
            self._save_watches()

        return produced

    # ------------------------------------------------------------------
    # Mark writing
    # ------------------------------------------------------------------

    def _write_drift_mark(
        self,
        *,
        watch: DriftWatch,
        target_relative: int,
        drift: dict,
        current_metrics: dict[str, float],
    ) -> dict | None:
        """Write a drift-detected register mark with corrects linkage."""
        decay_ratio = float(drift.get("decay_ratio", 0.0))

        # Severity bucket from decay magnitude
        if decay_ratio >= 1.5:
            severity = "block"
        elif decay_ratio >= 1.0:
            severity = "hold"
        else:
            severity = "warn"

        explanation = (
            f"post-deployment drift on mutation {watch.mutation_id} "
            f"(parameter={watch.parameter}) at T+{target_relative}: "
            f"decay_ratio={decay_ratio:.2f} across {drift['n_metrics_decayed']}/"
            f"{drift['n_metrics_compared']} metrics. "
            f"Recommend revert_for_review."
        )

        result = DisciplineResult(
            flagged=True,
            confidence=min(1.0, decay_ratio),
            explanation=explanation,
            markers=[f"target=T+{target_relative}", f"decay={decay_ratio:.2f}"],
            discipline="post_deployment_drift",
        )

        links = {
            "mutation_id": watch.mutation_id,
            "parameter": watch.parameter,
            "target_relative_cycle": target_relative,
            "pre_metrics": watch.pre_metrics,
            "post_metrics_t5": watch.post_metrics_t5,
            "current_metrics": dict(current_metrics),
            "decay_ratio": round(decay_ratio, 4),
            "n_metrics_decayed": drift["n_metrics_decayed"],
            "n_metrics_compared": drift["n_metrics_compared"],
            "decayed_keys": drift.get("decayed_keys", []),
        }

        mark = make_register_mark(
            result,
            plane="evolution",  # drift is an evolution-plane signal
            subject_type="mutation",
            subject_id=watch.mutation_id,
            decision_point=f"drift_monitor.tick:T+{target_relative}",
            actual_action="flag_drift",
            corrects=watch.original_mark_id,  # walk-back chain
            severity=severity,
            recommended_action="hold",  # operator reviews
            links=links,
        )

        ok = write_register_mark(mark, self.register_marks_path)
        if not ok:
            return None
        return mark.to_dict()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_watches(self) -> bool:
        try:
            self.watch_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.watch_path.with_suffix(self.watch_path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                for w in self._watches:
                    f.write(json.dumps(w.to_dict()) + "\n")
            tmp.replace(self.watch_path)
            return True
        except OSError:
            return False

    def _load_watches(self) -> None:
        self._watches = []
        if not self.watch_path.exists():
            return
        try:
            text = self.watch_path.read_text(encoding="utf-8")
        except OSError:
            return
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            try:
                w = DriftWatch.from_dict(d)
            except (TypeError, ValueError):
                continue
            self._watches.append(w)


# ---------------------------------------------------------------------------
# Drift detection (pure function, public for testability)
# ---------------------------------------------------------------------------


def _detect_drift(
    *,
    pre: dict[str, float],
    post_t5: dict[str, float],
    current: dict[str, float],
    tolerance: float,
    quorum: float,
) -> dict[str, Any]:
    """Decide whether current_metrics show decay vs post_metrics_t5
    relative to pre_metrics baseline.

    Returns:
        {
          fired: bool,
          decay_ratio: float (max across metrics; for severity),
          n_metrics_compared: int,
          n_metrics_decayed: int,
          decayed_keys: list[str],
        }
    """
    common = set(pre.keys()) & set(post_t5.keys()) & set(current.keys())
    if not common:
        return {
            "fired": False,
            "decay_ratio": 0.0,
            "n_metrics_compared": 0,
            "n_metrics_decayed": 0,
            "decayed_keys": [],
        }

    n_decayed = 0
    decayed_keys: list[str] = []
    max_decay = 0.0

    for k in common:
        try:
            p = float(pre[k])
            t5 = float(post_t5[k])
            c = float(current[k])
        except (TypeError, ValueError):
            continue

        gain_t5 = t5 - p
        if abs(gain_t5) < MATERIAL_GAIN_FLOOR:
            # No material gain to lose; skip (was noise, decay is noise too)
            continue

        current_gain = c - p
        # decay_ratio: 0 if current_gain == gain_t5; 1 if current_gain == 0;
        # >1 if current is worse than pre baseline.
        decay = (gain_t5 - current_gain) / abs(gain_t5)

        if decay > tolerance:
            n_decayed += 1
            decayed_keys.append(k)
            if decay > max_decay:
                max_decay = decay

    n_compared = len(common)
    fired = (
        n_compared > 0
        and n_decayed > 0
        and (n_decayed / n_compared) >= quorum
    )

    return {
        "fired": fired,
        "decay_ratio": max_decay,
        "n_metrics_compared": n_compared,
        "n_metrics_decayed": n_decayed,
        "decayed_keys": decayed_keys,
    }


__all__ = [
    "DriftWatch",
    "DriftMonitor",
    "DEFAULT_TARGET_CYCLES",
    "DRIFT_TOLERANCE",
    "MATERIAL_GAIN_FLOOR",
]
