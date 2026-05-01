"""r_repair_metric - the repair-rate measurement (Component 1.7 of the
OMEGA Layer + Causal Closure plan).

Plan reference: ~/.claude/plans/a-structural-dazzling-garden.md

NAMING NOTE
-----------
The plan calls this metric "R_M as REPAIR." The existing identity.py
already uses "RM" for "Research Momentum" (archive entries, stigmergy
density, task completion). To avoid silent semantic collision with a
load-bearing existing metric, this module names the metric
``RepairScore`` / ``r_aggregate`` etc. The wiring decision - replace
identity.py's RM with this, add as a 4th TCS component, or keep both
as separate dashboard signals - is deferred to the post-merge wiring
session where the user is awake to decide.

The conceptual claim still holds: this is the auditor's "R_M as REPAIR"
- the rate at which prediction errors are successfully corrected.

WHY REPAIR
----------
R_V (the published metric) is a static-state geometric measurement of
representational contraction. If R_M were ALSO static-state (e.g.,
internal coherence), the system would have two snapshot scores and
zero recovery-dynamics scores. Deacon's teleodynamic principle is
explicit: a self-repairing system is not one whose parts agree at
one moment - it is one that *closes the gap* between prediction and
observation through internal action. Friston's free-energy
minimization is exactly this dynamic.

The vector across subject kinds prevents Goodhart on any single kind:

    r_aggregate = geometric_mean(r_gate, r_mutation, r_welfare)

geometric (not arithmetic) so any single zero pulls the whole thing
down. A system that perfectly repairs gate predictions but never
acts on welfare evidence reads as 0, not 2/3.

EIGENFORM-ASYMPTOTE ALARM
-------------------------
If r_aggregate > 0.95 sustained for 30+ days, fire ``near_eigenform``.
Per Hofstadter's eigenform doctrine: "a system that fully reaches
S(x) = x has equilibrated - it is at thermodynamic death. The
PURPOSE of the system is constituted by the gap between current
state and eigenform." A repair rate too perfect means the system
isn't being challenged hard enough; the gap that constitutes
purpose is closing.

PROVISIONAL FLAG
----------------
Per the Mahakali calibration window doctrine ("rare-but-real
refusal"), repair scores are reported with ``provisional=True`` for
the first 90 days after launched_at. The metric should not influence
human-facing decisions during the calibration window.

USAGE
-----
    score = compute_repair_score(window_days=30)
    # score.r_aggregate ∈ [0, 1] (or NaN when one kind has no data)
    # score.provisional True for first 90 days
    # score.near_eigenform True when too-perfect

    # Persist for meso-loop to read:
    persist_repair_score(score)
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .causal_ledger import (
    CAUSAL_SUBJECT_KINDS,
    compute_repair_rate_for_kind,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Geometric mean is computed across these kinds. "agent_route" and "other"
# are intentionally excluded from the aggregate - they're low-signal at
# the v1 instrumentation; including them would dilute the signal.
AGGREGATE_KINDS: tuple[str, ...] = ("gate", "mutation", "welfare_proposal")

# Eigenform alarm threshold and sustained-window length.
NEAR_EIGENFORM_THRESHOLD: float = 0.95
NEAR_EIGENFORM_SUSTAINED_DAYS: int = 30

# Mahakali calibration window for the provisional flag.
PROVISIONAL_WINDOW_DAYS: int = 90

# Confidence weighting: linear ramp from 0 at 0 predictions to 1 at this many.
# Below 30 total predictions, confidence is < 1.0 and the score should be
# read with caution.
CONFIDENCE_FULL_AT_N: int = 30

# Default persistence locations.
DEFAULT_SCORE_PATH = Path.home() / ".dharma" / "meta" / "r_repair_score.json"
DEFAULT_HISTORY_PATH = Path.home() / ".dharma" / "meta" / "r_repair_history.jsonl"

# Sentinel for "kind had zero predictions": NaN. Aggregation treats NaN as
# missing (excluded from geometric mean rather than zeroing the product).
_NAN = float("nan")


# ---------------------------------------------------------------------------
# Score dataclass
# ---------------------------------------------------------------------------


@dataclass
class RepairScore:
    """Output of compute_repair_score.

    All r_* fields are in [0, 1] OR NaN (when that kind had no predictions
    in the window). r_aggregate is the geometric mean over kinds that
    have at least one prediction; if NO kind has predictions, r_aggregate
    is NaN and confidence is 0.
    """

    computed_at: str
    window_days: int

    r_gate: float
    r_mutation: float
    r_welfare: float
    r_aggregate: float

    n_predictions_total: int
    n_resolved_total: int
    n_repaired_total: int
    per_kind_counts: dict[str, dict[str, int]] = field(default_factory=dict)

    confidence: float = 0.0
    provisional: bool = True
    near_eigenform: bool = False

    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        # JSON doesn't allow NaN in strict mode; we replace with None on
        # write so the file is parseable by stdlib json.loads.
        for k in ("r_gate", "r_mutation", "r_welfare", "r_aggregate"):
            v = d.get(k)
            if isinstance(v, float) and math.isnan(v):
                d[k] = None
        return d


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_repair_score(
    *,
    window_days: int = 30,
    log_path: Path | None = None,
    history_path: Path | None = None,
    launched_at: datetime | None = None,
    now: datetime | None = None,
) -> RepairScore:
    """Compute the current repair score from causal_ledger marks.

    Parameters
    ----------
    window_days:
        How many days back to consider for the rate computation. The
        underlying ``compute_repair_rate_for_kind`` reads from the tail
        of register_marks.jsonl so this is approximate (mark-count
        bound, not strict day bound) at the v1 implementation.
    log_path:
        Override register_marks.jsonl location.
    history_path:
        Override the historical scores jsonl. Used to evaluate
        ``near_eigenform`` (sustained-high check).
    launched_at:
        Optional UTC datetime when the metric system "launched". Used
        for the 90-day Mahakali provisional window. Defaults to None
        which leaves provisional=True (safer default).
    now:
        Override "now" for testing. Defaults to UTC now.

    Returns
    -------
    RepairScore
        Never raises in normal use. Field defaults preserve the dataclass
        contract on partial-data paths.
    """
    now = now or datetime.now(timezone.utc)

    # 1. Per-kind rates
    rates: dict[str, float] = {}
    counts: dict[str, dict[str, int]] = {}
    n_pred_total = 0
    n_res_total = 0
    n_rep_total = 0

    for kind in AGGREGATE_KINDS:
        rate, n_pred, n_res = compute_repair_rate_for_kind(kind, log_path=log_path)

        # n_repaired isn't directly returned; recompute from rate + n_pred
        # Use round() because integer derivation: rate = n_repaired / n_pred.
        n_repaired = int(round(rate * n_pred)) if n_pred > 0 else 0

        # Use NaN sentinel when zero predictions to distinguish "no data"
        # from "zero repair rate."
        rates[kind] = rate if n_pred > 0 else _NAN
        counts[kind] = {
            "n_predictions": n_pred,
            "n_resolved": n_res,
            "n_repaired": n_repaired,
        }
        n_pred_total += n_pred
        n_res_total += n_res
        n_rep_total += n_repaired

    # 2. Aggregate via geometric mean over kinds that have data
    valid_rates = [v for v in rates.values() if not math.isnan(v)]
    if not valid_rates:
        r_aggregate = _NAN
    elif any(v == 0.0 for v in valid_rates):
        # Geometric mean of zero is zero. Honor that semantically:
        # any kind at zero pulls the aggregate to zero.
        r_aggregate = 0.0
    else:
        r_aggregate = math.exp(sum(math.log(v) for v in valid_rates) / len(valid_rates))

    # 3. Confidence: linear ramp on total predictions, capped at 1.0
    confidence = min(1.0, n_pred_total / max(1, CONFIDENCE_FULL_AT_N))

    # 4. Provisional flag: True for first 90 days post-launch
    if launched_at is None:
        provisional = True
    else:
        cutoff = launched_at + timedelta(days=PROVISIONAL_WINDOW_DAYS)
        provisional = now < cutoff

    # 5. Eigenform-asymptote alarm: 30-day sustained > threshold
    near_eigenform = _check_near_eigenform(
        history_path=history_path or DEFAULT_HISTORY_PATH,
        current_aggregate=r_aggregate,
        now=now,
    )

    notes: list[str] = []
    if confidence < 0.3:
        notes.append(
            f"low confidence: only {n_pred_total} total predictions "
            f"(want >= {CONFIDENCE_FULL_AT_N})"
        )
    if math.isnan(r_aggregate):
        notes.append("no causal predictions found in any subject kind")
    if near_eigenform:
        notes.append(
            "near_eigenform: aggregate sustained > "
            f"{NEAR_EIGENFORM_THRESHOLD} for {NEAR_EIGENFORM_SUSTAINED_DAYS}+ days. "
            "System may not be challenged hard enough; the gap that "
            "constitutes purpose is closing (Hofstadter doctrine)."
        )
    if provisional:
        notes.append(
            f"provisional: within {PROVISIONAL_WINDOW_DAYS}-day Mahakali "
            "calibration window; do not influence human decisions yet"
        )

    return RepairScore(
        computed_at=now.isoformat(),
        window_days=window_days,
        r_gate=rates.get("gate", _NAN),
        r_mutation=rates.get("mutation", _NAN),
        r_welfare=rates.get("welfare_proposal", _NAN),
        r_aggregate=r_aggregate,
        n_predictions_total=n_pred_total,
        n_resolved_total=n_res_total,
        n_repaired_total=n_rep_total,
        per_kind_counts=counts,
        confidence=round(confidence, 3),
        provisional=provisional,
        near_eigenform=near_eigenform,
        notes=notes,
    )


def persist_repair_score(
    score: RepairScore,
    *,
    score_path: Path | None = None,
    history_path: Path | None = None,
) -> bool:
    """Persist the score to disk for meso-loop / dashboard consumption.

    Writes:
      - <score_path>: latest score (overwritten)
      - <history_path>: append-only history jsonl (one line per call)

    Returns True on full success, False if any write failed.
    Never raises.
    """
    score_path = score_path or DEFAULT_SCORE_PATH
    history_path = history_path or DEFAULT_HISTORY_PATH
    payload = score.to_dict()

    ok = True
    try:
        score_path.parent.mkdir(parents=True, exist_ok=True)
        score_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError:
        ok = False

    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except OSError:
        ok = False

    return ok


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_near_eigenform(
    *,
    history_path: Path,
    current_aggregate: float,
    now: datetime,
) -> bool:
    """True when r_aggregate has been > NEAR_EIGENFORM_THRESHOLD for the
    last NEAR_EIGENFORM_SUSTAINED_DAYS days continuously.

    Reads history_path (jsonl) and looks at the last N days of records.
    If history is shorter than the sustained window, returns False
    (insufficient data).
    """
    if math.isnan(current_aggregate) or current_aggregate <= NEAR_EIGENFORM_THRESHOLD:
        return False
    if not history_path.exists():
        return False

    cutoff = now - timedelta(days=NEAR_EIGENFORM_SUSTAINED_DAYS)
    try:
        text = history_path.read_text(encoding="utf-8")
    except OSError:
        return False

    # Walk records, keep those whose computed_at >= cutoff.
    in_window: list[float] = []
    earliest_ts: datetime | None = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        ts_str = rec.get("computed_at")
        agg = rec.get("r_aggregate")
        if not ts_str or agg is None:
            continue
        try:
            # Robust to with/without timezone; normalize to UTC.
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if ts >= cutoff:
            try:
                in_window.append(float(agg))
            except (TypeError, ValueError):
                continue
        if earliest_ts is None or ts < earliest_ts:
            earliest_ts = ts

    # Need history that goes back at least to the cutoff to be confident
    # the score has been HIGH for the full sustained window. Otherwise
    # we just don't have enough data yet.
    if earliest_ts is None or earliest_ts > cutoff:
        return False
    if not in_window:
        return False

    # All in-window records (including current implicitly via persist
    # before compute calls _check) must be > threshold for sustained.
    return all(v > NEAR_EIGENFORM_THRESHOLD for v in in_window)


__all__ = [
    "AGGREGATE_KINDS",
    "NEAR_EIGENFORM_THRESHOLD",
    "NEAR_EIGENFORM_SUSTAINED_DAYS",
    "PROVISIONAL_WINDOW_DAYS",
    "RepairScore",
    "compute_repair_score",
    "persist_repair_score",
]
