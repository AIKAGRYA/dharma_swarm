"""causal_ledger - predict-then-verify for consequential actions.

Component 1.1 of the OMEGA Layer + Causal Closure plan
(~/.claude/plans/a-structural-dazzling-garden.md).

The contract: every consequential action declares an expected outcome at
decision time. After a window (heartbeats), an actual outcome is recorded
and the delta is computed. Both events are RegisterMarks on the "causal"
plane. The resolution mark sets ``corrects = <prediction_mark_id>`` so
the walk-back chain is queryable from the existing register-digest pipeline.

This module is deliberately the *external auditor* of internal measurements
(e.g. strange_loop's pre/post metrics, telos_gates' witness logs). It does
not REPLACE that measurement. It records what the proposer *expected* and
what *happened*, so R_M (Component 1.7, repair rate) can compute whether
predictions match reality across gate / mutation / welfare surfaces.

Friston's free-energy framing is the load-bearing constraint:

    prior (predicted observation)
        -> action
            -> observed delta
                -> belief / policy update

This ledger makes that loop auditable without inventing a new file format.
Reuses ``RegisterMark`` v3 schema; adds ``plane="causal"`` and uses
``links`` for the prediction/actual/delta payload.

Subjects (CAUSAL_SUBJECT_KINDS):
    mutation         - strange_loop parameter mutation outcome
    gate             - telos_gates ALLOW / BLOCK decision outcome
    agent_route      - orchestrator routing decision outcome
    welfare_proposal - action claiming external welfare impact
    other            - generic catch-all

Composition with strange_loop (Component 1.4 wiring example):
    on _observe_diagnose_propose:
        prediction_mark = causal_ledger.declare_prediction(
            subject_kind="mutation",
            subject_id=mutation.id,
            expected={"avg_failure": diagnosed_target_value, ...},
            window_heartbeats=self._measurement_window,
            decision_point="strange_loop._observe_diagnose_propose",
            rationale=mutation.reason,
        )
        # store prediction_mark.mark_id on the Mutation for later resolution

    on _measure_decide:
        causal_ledger.resolve_prediction(
            prediction_mark_id=mutation.causal_prediction_id,
            actual={"avg_failure": measured, ...},
            expected={"avg_failure": diagnosed_target_value, ...},
            decision_point="strange_loop._measure_decide",
        )

The ledger never raises in normal use (best-effort logging); callers must
treat None returns as logging-failure (e.g., disk full) and continue.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .register_disciplines import (
    DEFAULT_REGISTER_LOG,
    DisciplineResult,
    RegisterMark,
    make_register_mark,
    write_register_mark,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CAUSAL_SUBJECT_KINDS: tuple[str, ...] = (
    "mutation",
    "gate",
    "agent_route",
    "welfare_proposal",
    "other",
)

DISCIPLINE_PREDICT = "causal_prediction"
DISCIPLINE_RESOLVE = "causal_resolution"

# Tolerance for the coarse repair check used by compute_repair_rate_for_kind.
# A prediction is "repaired" when the actual outcome stays within this
# fraction of the predicted magnitude AND the sign agrees with the
# prediction (when nonzero). r_m_metric.py may refine; this is the v1
# default so the meter has SOMETHING to compute.
_REPAIR_MAGNITUDE_TOLERANCE = 0.5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def declare_prediction(
    *,
    subject_kind: str,
    subject_id: str,
    expected: dict[str, float],
    window_heartbeats: int,
    decision_point: str = "",
    rationale: str = "",
    log_path: Path | None = None,
) -> RegisterMark | None:
    """Declare a predict-then-verify expectation at decision time.

    Parameters
    ----------
    subject_kind:
        One of CAUSAL_SUBJECT_KINDS. Unknown values are coerced to "other"
        rather than raising (best-effort discipline).
    subject_id:
        Stable identifier for the subject being predicted. Examples:
        ``mutation.id`` for a strange_loop mutation,
        ``f"gate:{action_id}"`` for a telos_gate decision.
    expected:
        ``{metric_name: float}`` of the predicted downstream effects.
        Use the SAME metric names the resolver will use; mismatched names
        cause silent zero-delta in resolve.
    window_heartbeats:
        How many heartbeats until the resolver should fire. Persisted in
        ``links.window_heartbeats`` for offline scans
        (find_unresolved_predictions).
    decision_point:
        Dotted call-site path for traceability (e.g.
        "strange_loop._observe_diagnose_propose").
    rationale:
        Short text explaining why this prediction. Goes to ``explanation``.
    log_path:
        Override for tests. Default: ``~/.dharma/stigmergy/register_marks.jsonl``.

    Returns
    -------
    RegisterMark | None
        The mark that was written, or None if the write failed. Caller
        should usually capture ``mark.mark_id`` to thread through to a
        later resolve_prediction call. Never raises.
    """
    if subject_kind not in CAUSAL_SUBJECT_KINDS:
        subject_kind = "other"

    # The DisciplineResult is a thin shim so we can flow through the
    # existing make_register_mark() helper without divergent code paths.
    # Predictions are NOT flags - flagged=False, severity="note".
    result = DisciplineResult(
        flagged=False,
        confidence=1.0,
        explanation=rationale or f"causal prediction for {subject_kind}:{subject_id}",
        markers=[],
        discipline=DISCIPLINE_PREDICT,
    )

    links: dict[str, Any] = {
        "kind": "causal_prediction",
        "expected": _coerce_float_dict(expected),
        "window_heartbeats": int(max(0, window_heartbeats)),
        "subject_kind": subject_kind,
        # resolves_at_hint: an iso timestamp so manual scans are readable;
        # actual resolution time is set by resolve_prediction's mark.ts.
        "resolves_at_hint": datetime.now(timezone.utc).isoformat(),
    }

    mark = make_register_mark(
        result,
        plane="causal",
        subject_type="decision",
        subject_id=subject_id or "anon",
        decision_point=decision_point,
        actual_action=f"declare_prediction({subject_kind})",
        links=links,
        severity="note",
        recommended_action="continue",
    )

    ok = write_register_mark(mark, log_path)
    return mark if ok else None


def resolve_prediction(
    *,
    prediction_mark_id: str,
    actual: dict[str, float],
    expected: dict[str, float] | None = None,
    decision_point: str = "",
    log_path: Path | None = None,
) -> RegisterMark | None:
    """Resolve a previously-declared prediction with observed values.

    Parameters
    ----------
    prediction_mark_id:
        The ``mark_id`` from the original declare_prediction return value.
        Becomes the resolution mark's ``corrects`` field, threading the
        walk-back chain.
    actual:
        ``{metric_name: float}`` of observed values. Same key set as the
        prediction's ``expected``.
    expected:
        Optional - duplicating the prediction's expected so delta can be
        computed inline. If omitted, downstream analysis must look up the
        prediction mark to compute delta. Including it makes the
        register-digest digest pipeline simpler.
    decision_point:
        Dotted call-site path of the resolver.
    log_path:
        Override for tests.

    Returns
    -------
    RegisterMark | None
        The resolution mark on success, None on write failure.

    Notes
    -----
    Idempotency is **not** enforced at this layer. The underlying JSONL
    is append-only and the cost of a duplicate write is one disk-line.
    Callers should track whether they've already resolved (e.g., by
    storing the resolution mark_id on their domain object). Multiple
    resolutions of the same prediction are visible as multiple marks
    sharing the same ``corrects`` field, which is intentional - re-
    measurement is a real signal, not a bug.
    """
    actual_clean = _coerce_float_dict(actual)
    expected_clean = _coerce_float_dict(expected) if expected else {}

    delta: dict[str, float] = {}
    if expected_clean:
        for k, exp_v in expected_clean.items():
            if k in actual_clean:
                try:
                    delta[k] = float(actual_clean[k]) - float(exp_v)
                except (TypeError, ValueError):
                    continue

    result = DisciplineResult(
        flagged=False,
        confidence=1.0,
        explanation=f"causal resolution for prediction {prediction_mark_id}",
        markers=[],
        discipline=DISCIPLINE_RESOLVE,
    )

    links: dict[str, Any] = {
        "kind": "causal_resolution",
        "actual": actual_clean,
    }
    if expected_clean:
        links["expected"] = expected_clean
    if delta:
        links["delta"] = delta

    mark = make_register_mark(
        result,
        plane="causal",
        subject_type="decision",
        # The resolution's subject_id is the prediction's mark_id, so a
        # cheap subject_id-grouped query surfaces (prediction, resolution)
        # pairs without needing the corrects index.
        subject_id=prediction_mark_id,
        decision_point=decision_point,
        actual_action="resolve_prediction",
        corrects=prediction_mark_id,  # the walk-back link
        links=links,
        severity="note",
        recommended_action="continue",
    )

    ok = write_register_mark(mark, log_path)
    return mark if ok else None


def find_unresolved_predictions(
    *,
    log_path: Path | None = None,
    subject_kind: str | None = None,
    max_lines: int = 50_000,
) -> list[dict]:
    """Scan register_marks.jsonl for causal predictions without resolution.

    Useful for the daily sweep: many unresolved predictions = open loop =
    R_M pulled toward zero.

    Parameters
    ----------
    log_path:
        Default ~/.dharma/stigmergy/register_marks.jsonl.
    subject_kind:
        If set, restrict to predictions of that kind.
    max_lines:
        Cap on file lines read (tail) for performance. The default 50k
        is generous; current production rate is ~80 marks/2 weeks.

    Returns
    -------
    list[dict]
        One dict per unresolved prediction with key fields:
        ``mark_id``, ``ts``, ``subject_kind``, ``subject_id``,
        ``expected``, ``window_heartbeats``. Empty list on file-missing
        or parse error (never raises).
    """
    log_path = log_path or DEFAULT_REGISTER_LOG
    if not log_path.exists():
        return []

    predictions: dict[str, dict] = {}
    resolved: set[str] = set()

    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return []

    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            mark = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if mark.get("plane") != "causal":
            continue

        links = mark.get("links") or {}
        kind = links.get("kind")

        if kind == "causal_prediction":
            if subject_kind and links.get("subject_kind") != subject_kind:
                continue
            mark_id = mark.get("mark_id")
            if mark_id:
                predictions[mark_id] = {
                    "mark_id": mark_id,
                    "ts": mark.get("ts"),
                    "subject_kind": links.get("subject_kind"),
                    "subject_id": mark.get("subject_id"),
                    "expected": links.get("expected") or {},
                    "window_heartbeats": links.get("window_heartbeats"),
                }
        elif kind == "causal_resolution":
            corrects = mark.get("corrects")
            if corrects:
                resolved.add(corrects)

    return [p for mid, p in predictions.items() if mid not in resolved]


def compute_repair_rate_for_kind(
    subject_kind: str,
    *,
    log_path: Path | None = None,
    max_lines: int = 50_000,
) -> tuple[float, int, int]:
    """Compute per-kind repair rate from causal-plane marks.

    Used by Component 1.7 (R_M REPAIR) as one of three subscores:
    r_m_gate, r_m_mutation, r_m_welfare. The aggregate R_M is geometric
    mean across these so any zero pulls the whole thing down.

    A prediction is "repaired" when:
    - it has a paired resolution mark (corrects link found), AND
    - for every metric in expected: actual is within
      _REPAIR_MAGNITUDE_TOLERANCE (50%) of expected magnitude AND
      sign agrees (when expected is nonzero).

    Parameters
    ----------
    subject_kind:
        One of CAUSAL_SUBJECT_KINDS, e.g. "mutation".
    log_path:
        Default register_marks.jsonl.
    max_lines:
        Tail cap on file read.

    Returns
    -------
    tuple[float, int, int]
        ``(repair_rate, n_predictions, n_resolved)`` where:

        - ``repair_rate`` is in [0, 1]; ``0.0`` when n_predictions == 0
          (and confidence-weighted downstream).
        - ``n_predictions`` counts declared predictions (denominator).
        - ``n_resolved`` counts predictions that have any resolution mark.

    Never raises.
    """
    log_path = log_path or DEFAULT_REGISTER_LOG
    if not log_path.exists():
        return (0.0, 0, 0)

    predictions: dict[str, dict] = {}
    resolutions: dict[str, dict] = {}

    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return (0.0, 0, 0)

    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            mark = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if mark.get("plane") != "causal":
            continue

        links = mark.get("links") or {}
        kind = links.get("kind")

        if kind == "causal_prediction":
            if links.get("subject_kind") != subject_kind:
                continue
            mark_id = mark.get("mark_id")
            if mark_id:
                predictions[mark_id] = mark
        elif kind == "causal_resolution":
            corrects = mark.get("corrects")
            if corrects:
                # Last-write-wins on multiple resolutions for same prediction.
                resolutions[corrects] = mark

    n_predictions = len(predictions)
    if n_predictions == 0:
        return (0.0, 0, 0)

    n_resolved = sum(1 for mid in predictions if mid in resolutions)
    n_repaired = sum(
        1
        for mid, pred in predictions.items()
        if _is_repaired(pred, resolutions.get(mid))
    )

    return (n_repaired / n_predictions, n_predictions, n_resolved)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _coerce_float_dict(d: dict[str, Any] | None) -> dict[str, float]:
    """Best-effort coercion of value-like-strings to floats."""
    out: dict[str, float] = {}
    if not d:
        return out
    for k, v in d.items():
        if v is None:
            continue
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            # Skip non-numeric values; they don't belong in expected/actual
            continue
    return out


def _is_repaired(pred: dict, res: dict | None) -> bool:
    """Heuristic: did the resolution land within tolerance of the prediction?"""
    if res is None:
        return False
    pred_links = pred.get("links") or {}
    res_links = res.get("links") or {}
    expected = pred_links.get("expected") or {}
    actual = res_links.get("actual") or {}
    if not expected or not actual:
        return False

    for k, exp_v in expected.items():
        if k not in actual:
            return False
        try:
            exp_f = float(exp_v)
            act_f = float(actual[k])
        except (TypeError, ValueError):
            return False

        denom = max(abs(exp_f), 1.0)
        in_magnitude = abs(act_f - exp_f) / denom <= _REPAIR_MAGNITUDE_TOLERANCE
        # Sign agreement: only enforce when expected is materially nonzero
        sign_ok = abs(exp_f) < 1e-9 or (exp_f * act_f >= 0)
        if not (in_magnitude and sign_ok):
            return False

    return True


__all__ = [
    "CAUSAL_SUBJECT_KINDS",
    "DISCIPLINE_PREDICT",
    "DISCIPLINE_RESOLVE",
    "declare_prediction",
    "resolve_prediction",
    "find_unresolved_predictions",
    "compute_repair_rate_for_kind",
]
