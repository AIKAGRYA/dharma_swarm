"""E6 — the velocity substrate: Frontier Ledger render history + d(delta)/dt.

Elevation spec E6: the decisive number is not position (our number vs the
field's) but velocity — is each delta closing or eroding, and how does our
loop latency compare to the field's publication cadence (doctrine §2.3: you
beat months in cycle time). Each ledger render appends one chained history
row; velocity values from fewer than 2 numeric points render UNVALUED with
their ``requires`` stated (the chamber-drift honesty pattern) — never
extrapolated from nothing.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm.chamber.chain import append_chained, read_chain

LEDGER_HISTORY_SCHEMA = "chamber_ledger_history.v1"

__all__ = [
    "LEDGER_HISTORY_SCHEMA",
    "append_history",
    "compute_velocity",
    "history_values",
    "read_chain",
]


def _series_value(vals: dict[str, Any]) -> float | None:
    """The trackable number for a capability: its delta-to-field when
    commensurable, else our own measured value. Without the ``ours`` fallback
    velocity is dead by construction — only one row is ever commensurable and
    its value is None, so no capability would ever accumulate two points
    (review R1-3)."""
    for key in ("delta", "ours"):
        v = vals.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def history_values(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract per-capability numeric series (time-sorted) from history rows."""
    series: dict[str, list[tuple[str, float]]] = {}
    for row in rows:
        at = str(row.get("generated_at", ""))
        for cap, vals in row.get("capabilities", {}).items():
            v = _series_value(vals)
            if v is not None:
                series.setdefault(cap, []).append((at, v))
    for points in series.values():  # by time, not insertion order (R1-5)
        points.sort(key=lambda p: p[0])
    return series


def _days_between(a: str, b: str) -> float | None:
    try:
        ta = datetime.fromisoformat(a.replace("Z", "+00:00"))
        tb = datetime.fromisoformat(b.replace("Z", "+00:00"))
    except ValueError:
        return None
    days = (tb - ta).total_seconds() / 86400.0
    return days if days > 0 else None


def compute_velocity(prior_rows: list[dict[str, Any]],
                     current_capabilities: dict[str, dict[str, Any]],
                     current_generated_at: str) -> dict[str, Any]:
    """Velocity block from prior history + the render being produced.

    Pure function of its inputs — the ledger's --check replays it from the
    committed history file and receipt."""
    rows = prior_rows + [{
        "generated_at": current_generated_at,
        "capabilities": current_capabilities,
    }]
    series = history_values(rows)
    per_cap: dict[str, Any] = {}
    valued = 0
    for cap in sorted(current_capabilities):
        points = series.get(cap, [])
        if len(points) < 2:
            per_cap[cap] = {
                "status": "UNVALUED",
                "requires": ">=2 renders with a numeric value for this "
                            "capability",
                "points": len(points),
            }
            continue
        (t0, d0), (t1, d1) = points[-2], points[-1]
        days = _days_between(t0, t1)
        rate = round((d1 - d0) / days, 6) if days else None
        per_cap[cap] = {
            "status": "VALUED" if rate is not None else "UNVALUED",
            "d_delta_dt_per_day": rate,
            "window": [t0, t1],
            "closing": (rate < 0 if rate is not None else None),
            "points": len(points),
        }
        if rate is None:  # equal or non-increasing timestamps between renders
            per_cap[cap]["requires"] = ("two renders at least one clock-second "
                                        "apart (identical timestamps cannot "
                                        "define a rate)")
        valued += rate is not None
    return {
        "renders_in_history": len(rows),
        "capabilities": per_cap,
        "valued": valued,
        "loop_latency": {
            "status": "UNVALUED",
            "requires": "gym iteration receipts with timestamps AND field "
                        "publication cadence from ingest (code-world lane)",
        },
    }


def append_history(path: Path, *, generated_at: str, receipt_digest: str,
                   capabilities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Append one render's summary to the chained history; returns the row."""
    return append_chained(path, {
        "schema": LEDGER_HISTORY_SCHEMA,
        "generated_at": generated_at,
        "receipt_digest": receipt_digest,
        "capabilities": capabilities,
    })
