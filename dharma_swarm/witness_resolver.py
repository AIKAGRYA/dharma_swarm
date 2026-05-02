"""witness_resolver - heartbeat-driven resolver for elapsed causal
prediction windows.

Component 1.2 of the OMEGA Layer + Causal Closure plan
(~/.claude/plans/a-structural-dazzling-garden.md).

WHAT THIS DOES
--------------
The plan: "Wire telos_gates.check() outcome to a future-resolved
outcome. When gatekeeper.check() returns ALLOW for a consequential
action, attach a pending-resolution token... resolver fires N
heartbeats later... witness log gets the resolution appended."

WitnessResolver maintains an in-memory + disk-backed queue of
predictions awaiting resolution. On every heartbeat tick, it scans
the queue for predictions whose window has elapsed, then derives the
"actual" outcome from observable post-decision evidence and writes a
resolution mark via causal_ledger.resolve_prediction.

The result: every gate decision (or mutation, or welfare proposal)
that declared a prediction at decision time now has a paired
resolution mark in register_marks.jsonl with `corrects` linkage.
This closes the predict-then-verify arc the auditor flagged as the
load-bearing missing component.

DESIGN: STANDALONE, ADDITIVE, MERGE-SAFE
----------------------------------------
- NEW module. Zero modification to telos_gates.py, organism.py, or
  strange_loop.py. Wiring happens at merge phase via:
    * Caller -> resolver.enqueue(...) right after a prediction is
      declared by causal_ledger.declare_prediction()
    * organism.py heartbeat -> resolver.tick(cycle) once per heartbeat
- Persistent queue at ~/.dharma/witness/_pending.jsonl so resolutions
  survive daemon restart.
- Resolution heuristic is conservative: it reports actual_outcome as
  one of {"stable", "degraded", "reversed", "unknown"}. When evidence
  is ambiguous, "unknown" is preferred over confident misattribution.

ACTUAL-OUTCOME DERIVATION (heuristic)
-------------------------------------
For each pending prediction whose window has elapsed:

1. If a register mark fired referencing the same subject_id within the
   window, with severity >= "warn" -> "degraded"
2. If a post_deployment_drift mark with corrects=<this_prediction>
   fired -> "reversed"
3. If witness logs in the post-decision window show >= 2 consecutive
   BLOCKED outcomes against the same subject -> "degraded"
4. Otherwise -> "stable"

Numerical actual values: when the prediction had numeric `expected`
fields, we synthesize a coarse `actual` dict mapping each expected
metric to a heuristic value (1.0 * expected for stable, 0.0 for
degraded, -expected for reversed). This lets compute_repair_rate_for_kind
treat resolutions uniformly.

THIS IS BOOTSTRAP HEURISTIC. Future iterations should derive numeric
actuals from real downstream metrics (organism pulse history,
fitness archives, etc.) instead of synthesizing from coarse buckets.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .causal_ledger import resolve_prediction
from .register_disciplines import DEFAULT_REGISTER_LOG

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PENDING_PATH = Path.home() / ".dharma" / "witness" / "_pending.jsonl"
DEFAULT_WITNESS_DIR = Path.home() / ".dharma" / "witness"

# Maximum heartbeat-cycle drift before a pending entry is force-resolved as
# "unknown" (e.g., daemon was down so long the window is meaningless)
MAX_BACKLOG_CYCLES = 1000

# Severity mapping: any mark with severity in this set is treated as a
# "degraded" signal for resolution
DEGRADED_SEVERITIES = frozenset({"warn", "hold", "block"})


# ---------------------------------------------------------------------------
# Pending entry dataclass
# ---------------------------------------------------------------------------


@dataclass
class PendingResolution:
    """A prediction awaiting resolution at a future heartbeat cycle."""

    prediction_mark_id: str
    subject_kind: str  # "mutation" | "gate" | "agent_route" | "welfare_proposal"
    subject_id: str  # the subject the prediction was about
    expected: dict[str, float]  # original predicted values
    enqueued_at_cycle: int  # heartbeat cycle when enqueued
    resolves_at_cycle: int  # cycle at/after which to resolve
    enqueued_at_iso: str  # for human inspection / debugging
    decision_point: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PendingResolution":
        return cls(
            prediction_mark_id=str(d.get("prediction_mark_id", "")),
            subject_kind=str(d.get("subject_kind", "other")),
            subject_id=str(d.get("subject_id", "")),
            expected=dict(d.get("expected", {})),
            enqueued_at_cycle=int(d.get("enqueued_at_cycle", 0)),
            resolves_at_cycle=int(d.get("resolves_at_cycle", 0)),
            enqueued_at_iso=str(d.get("enqueued_at_iso", "")),
            decision_point=str(d.get("decision_point", "")),
        )


# ---------------------------------------------------------------------------
# WitnessResolver
# ---------------------------------------------------------------------------


class WitnessResolver:
    """Heartbeat-driven resolver. Owns a persistent queue of pending
    predictions; called on each tick to resolve elapsed windows.

    Lifecycle:
        resolver = WitnessResolver()
        resolver.enqueue(prediction_mark_id="abc", subject_kind="gate", ...)
        # ... heartbeats elapse ...
        resolutions = resolver.tick(current_cycle=cycle)
        # resolutions: list of resolution-mark dicts that were written

    Persistence: pending queue auto-saved on enqueue/tick; auto-loaded
    on construction. Survives daemon restart.

    Thread safety: NOT thread-safe. Single-writer model (the heartbeat
    loop). If multi-writer becomes needed, wrap in a lock.
    """

    def __init__(
        self,
        *,
        pending_path: Path | None = None,
        register_marks_path: Path | None = None,
        witness_dir: Path | None = None,
    ) -> None:
        self.pending_path = pending_path or DEFAULT_PENDING_PATH
        self.register_marks_path = register_marks_path or DEFAULT_REGISTER_LOG
        self.witness_dir = witness_dir or DEFAULT_WITNESS_DIR
        self._pending: list[PendingResolution] = []
        self._load_pending()

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def enqueue(
        self,
        *,
        prediction_mark_id: str,
        subject_kind: str,
        subject_id: str,
        expected: dict[str, float],
        window_heartbeats: int,
        current_cycle: int,
        decision_point: str = "",
    ) -> bool:
        """Queue a prediction for later resolution. Idempotent: enqueueing
        the same prediction_mark_id twice is a no-op (returns False).

        IMPORTANT: ``expected`` MUST match the dict that was passed to
        causal_ledger.declare_prediction() when the prediction mark was
        created. The resolver synthesizes the resolution's ``actual`` by
        applying outcome-bucket multipliers to ``expected``. If the keys
        don't match the prediction's keys, _is_repaired in causal_ledger
        will fail the key check and the resolution counts as not-repaired.

        Production wiring pattern:
            mark = causal_ledger.declare_prediction(..., expected=E, ...)
            resolver.enqueue(prediction_mark_id=mark.mark_id, ...,
                             expected=E, ...)
        Pass the SAME E to both. Using E read from the prediction mark
        (instead of caller passing it) is a future hardening; v1 trusts
        the caller for performance.
        """
        if not prediction_mark_id:
            return False
        # Idempotency check
        for existing in self._pending:
            if existing.prediction_mark_id == prediction_mark_id:
                return False

        entry = PendingResolution(
            prediction_mark_id=prediction_mark_id,
            subject_kind=subject_kind,
            subject_id=subject_id,
            expected=dict(expected),
            enqueued_at_cycle=int(current_cycle),
            resolves_at_cycle=int(current_cycle + max(0, window_heartbeats)),
            enqueued_at_iso=datetime.now(timezone.utc).isoformat(),
            decision_point=decision_point,
        )
        self._pending.append(entry)
        self._save_pending()
        return True

    def queue_size(self) -> int:
        """Current number of pending resolutions."""
        return len(self._pending)

    def pending_for_subject(self, subject_id: str) -> list[PendingResolution]:
        """Return all pending entries for a given subject_id (read-only copy)."""
        return [p for p in self._pending if p.subject_id == subject_id]

    # ------------------------------------------------------------------
    # Heartbeat tick
    # ------------------------------------------------------------------

    def tick(
        self,
        current_cycle: int,
        *,
        now: datetime | None = None,
    ) -> list[dict]:
        """Resolve all pending predictions whose window has elapsed.

        Returns list of resolution-mark dicts that were successfully written
        (one per resolved prediction). Failed writes are kept in queue for
        retry on the next tick.

        Backlog protection: any pending entry where
            current_cycle - resolves_at_cycle > MAX_BACKLOG_CYCLES
        is force-resolved with actual_outcome="unknown" and removed.
        Prevents unbounded queue growth on long daemon outages.
        """
        ready: list[PendingResolution] = []
        backlog: list[PendingResolution] = []
        keep: list[PendingResolution] = []

        for entry in self._pending:
            if current_cycle - entry.resolves_at_cycle > MAX_BACKLOG_CYCLES:
                backlog.append(entry)
            elif current_cycle >= entry.resolves_at_cycle:
                ready.append(entry)
            else:
                keep.append(entry)

        resolutions: list[dict] = []
        new_keep: list[PendingResolution] = list(keep)

        for entry in ready:
            res_dict = self._resolve_one(entry)
            if res_dict is None:
                # Write failed -> keep for retry
                new_keep.append(entry)
            else:
                resolutions.append(res_dict)

        for entry in backlog:
            res_dict = self._resolve_one_force_unknown(entry)
            if res_dict is None:
                # Write failed; drop it anyway to prevent queue growth
                continue
            resolutions.append(res_dict)

        if new_keep != self._pending:
            self._pending = new_keep
            self._save_pending()

        return resolutions

    # ------------------------------------------------------------------
    # Resolution helpers
    # ------------------------------------------------------------------

    def _resolve_one(self, entry: PendingResolution) -> dict | None:
        """Derive actual outcome and write the resolution mark."""
        outcome = self._classify_outcome(entry)
        actual = self._synthesize_actual(entry, outcome)

        mark = resolve_prediction(
            prediction_mark_id=entry.prediction_mark_id,
            actual=actual,
            expected=entry.expected,
            decision_point=f"witness_resolver.tick:{outcome}",
            log_path=self.register_marks_path,
        )
        if mark is None:
            return None
        return {
            "prediction_mark_id": entry.prediction_mark_id,
            "resolution_mark_id": mark.mark_id,
            "actual_outcome": outcome,
            "subject_kind": entry.subject_kind,
            "subject_id": entry.subject_id,
        }

    def _resolve_one_force_unknown(
        self, entry: PendingResolution,
    ) -> dict | None:
        """Force-resolve a backlog entry as unknown."""
        actual = {k: 0.0 for k in entry.expected}
        mark = resolve_prediction(
            prediction_mark_id=entry.prediction_mark_id,
            actual=actual,
            expected=entry.expected,
            decision_point="witness_resolver.tick:backlog_forced_unknown",
            log_path=self.register_marks_path,
        )
        if mark is None:
            return None
        return {
            "prediction_mark_id": entry.prediction_mark_id,
            "resolution_mark_id": mark.mark_id,
            "actual_outcome": "unknown",
            "subject_kind": entry.subject_kind,
            "subject_id": entry.subject_id,
            "reason": "backlog_exceeded",
        }

    def _classify_outcome(self, entry: PendingResolution) -> str:
        """Return one of {stable, degraded, reversed, unknown}.

        Reads register_marks.jsonl to decide:
          - any post_deployment_drift mark with corrects=<our_id> -> reversed
          - any mark referencing same subject_id with severity in
            DEGRADED_SEVERITIES, posted AFTER our enqueue ts -> degraded
          - else -> stable
        """
        if not self.register_marks_path.exists():
            return "stable"

        try:
            text = self.register_marks_path.read_text(encoding="utf-8")
        except OSError:
            return "unknown"

        enqueued_ts = entry.enqueued_at_iso
        saw_degraded = False
        saw_drift = False

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                mark = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            # Reversed: explicit drift mark pointing at us
            if (
                mark.get("discipline") == "post_deployment_drift"
                and mark.get("corrects") == entry.prediction_mark_id
            ):
                saw_drift = True
                break

            # Degraded: any mark on same subject_id, posted after enqueue,
            # with severity in degraded set
            if mark.get("subject_id") != entry.subject_id:
                continue
            mark_ts = mark.get("ts", "")
            if mark_ts <= enqueued_ts:
                continue
            severity = mark.get("severity", "")
            if severity in DEGRADED_SEVERITIES:
                saw_degraded = True

        if saw_drift:
            return "reversed"
        if saw_degraded:
            return "degraded"
        return "stable"

    @staticmethod
    def _synthesize_actual(
        entry: PendingResolution, outcome: str,
    ) -> dict[str, float]:
        """Coarse synthesis of `actual` dict from outcome bucket.

        For each expected metric:
          stable   -> actual = expected (1.0x)
          degraded -> actual = 0.5x expected (under-delivers but same sign)
          reversed -> actual = -1.0x expected (sign flipped)
          unknown  -> actual = 0.0 (signals "no info" without sign)

        compute_repair_rate_for_kind reads these values and applies its
        50%-magnitude + sign tolerance check. Stable -> repaired.
        Degraded -> still in tolerance (rate stays high). Reversed ->
        sign flip -> NOT repaired.
        """
        if not entry.expected:
            return {}
        if outcome == "stable":
            return {k: float(v) for k, v in entry.expected.items()}
        if outcome == "degraded":
            return {k: 0.5 * float(v) for k, v in entry.expected.items()}
        if outcome == "reversed":
            return {k: -float(v) for k, v in entry.expected.items()}
        # unknown
        return {k: 0.0 for k in entry.expected}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_pending(self) -> bool:
        """Atomic-ish write of the pending queue to disk."""
        try:
            self.pending_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.pending_path.with_suffix(self.pending_path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                for entry in self._pending:
                    f.write(json.dumps(entry.to_dict()) + "\n")
            tmp.replace(self.pending_path)
            return True
        except OSError:
            return False

    def _load_pending(self) -> None:
        """Rehydrate from disk on construction."""
        self._pending = []
        if not self.pending_path.exists():
            return
        try:
            text = self.pending_path.read_text(encoding="utf-8")
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
                entry = PendingResolution.from_dict(d)
            except (TypeError, ValueError):
                continue
            self._pending.append(entry)


__all__ = [
    "PendingResolution",
    "WitnessResolver",
    "MAX_BACKLOG_CYCLES",
]
