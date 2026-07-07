"""E4 — the causal daily delta chain: the chamber's heartbeat.

Elevation spec E4 + chamber doctrine discipline 12: one receipt per day
proving the system behaves measurably differently today BECAUSE OF
yesterday's ingest and gym outcomes. Causal, not correlational: every
behavior-change entry names its ``caused_by`` digest chain (world event ->
bronze receipt hash -> promotion -> change -> gym delta). An entry without a
resolvable cause is not evidence and is refused at write time.

Chain mechanics live in chamber.chain (checker expect_chain compatible).
Also carries the metabolic-efficiency metric: measured improvement per unit
of ingest — hoarding gets a denominator.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dharma_swarm.chamber.chain import BrokenChainError, append_chained, read_chain

DAILY_DELTA_SCHEMA = "chamber_daily_delta.v1"
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

__all__ = [
    "BrokenChainError",
    "CausalityError",
    "DAILY_DELTA_SCHEMA",
    "append_daily_delta",
    "read_chain",
]


class CausalityError(ValueError):
    """A behavior-change entry lacks a resolvable caused_by digest chain."""


def _validate_changes(changes: list[dict[str, Any]]) -> None:
    for i, change in enumerate(changes):
        for key in ("surface", "before", "after"):
            if key not in change:
                raise CausalityError(f"behavior_change {i}: missing {key!r}")
        caused_by = change.get("caused_by")
        if not isinstance(caused_by, list) or not caused_by:
            raise CausalityError(
                f"behavior_change {i} ({change['surface']}): empty caused_by — "
                "a correlational delta is not evidence (E4 mandate)")
        for d in caused_by:
            if not _DIGEST_RE.match(str(d)):
                raise CausalityError(
                    f"behavior_change {i}: caused_by entry {d!r} is not a "
                    "sha256 digest")


def append_daily_delta(path: Path, *, date: str, yesterday: dict[str, Any],
                       behavior_changes: list[dict[str, Any]],
                       ingest_units: int, improvement_units: float,
                       attributes: dict[str, Any] | None = None) -> dict[str, Any]:
    """Append one day's causal delta; returns the stamped row.

    ``yesterday`` records what was consumed (bronze landed/consumed, gym runs
    with taskpack shas + scores); ``behavior_changes`` each carry caused_by
    digests. A delta-empty day is written honestly (empty list) — the
    flatline must be visible, never skipped."""
    _validate_changes(behavior_changes)
    ratio = round(improvement_units / ingest_units, 6) if ingest_units else None
    return append_chained(path, {
        "schema": DAILY_DELTA_SCHEMA,
        "date": date,
        "produced_at": date,
        "yesterday": yesterday,
        "behavior_changes": behavior_changes,
        "metabolic_efficiency": {
            "ingest_units": ingest_units,
            "improvement_units": improvement_units,
            "ratio": ratio,
        },
        "attributes": attributes or {},
    })
