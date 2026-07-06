"""Mycelial context builders for the WILD EXPLORE loop.

Dead children are compost; the archive is soil. These helpers turn prior
candidate records into the two context streams the frontier proposer consumes:
failure transcripts (learn from what failed) and archive exemplars (reuse any
prior genome as mutation soil). Kept in a tiny module so experiment.py stays
lean and the module-size ratchet stays green.
"""

from __future__ import annotations

import random
from typing import Any


def recent_failure_transcripts(records: list[Any], *, limit: int = 3) -> list[dict[str, Any]]:
    """Pull the most recent unsolved-task signals from graded/blocked records."""
    out: list[dict[str, Any]] = []
    for record in reversed(records):
        receipt = getattr(record, "benchmark_receipt", None) or {}
        for item in list(receipt.get("grade_receipts") or []):
            if item.get("resolved") is True:
                continue
            out.append(
                {
                    "task_id": item.get("task_id", ""),
                    "error": item.get("error", ""),
                    "from_candidate": record.candidate_id,
                }
            )
            if len(out) >= limit:
                return out
        if record.state == "blocked" and record.notes:
            out.append({"blocked_candidate": record.candidate_id, "blocker": record.notes})
            if len(out) >= limit:
                return out
    return out


def archive_context(records: list[Any], *, limit: int = 3) -> list[dict[str, Any]]:
    """Top graded genomes as mutation soil (mycelial reuse)."""
    graded = [r for r in records if r.state == "graded"]
    graded.sort(key=lambda r: r.weighted_fitness, reverse=True)
    return [
        {
            "candidate_id": r.candidate_id,
            "fitness": r.weighted_fitness,
            "genome": r.genome,
        }
        for r in graded[:limit]
    ]


def pick_second_parent(records: list[Any], exclude_id: str, rng: random.Random) -> Any | None:
    """Choose a distinct graded record to enable crossover, or None."""
    pool = [r for r in records if r.state == "graded" and r.candidate_id != exclude_id]
    if not pool:
        return None
    return rng.choice(pool)
