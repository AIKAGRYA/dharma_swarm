"""Cold-start trace corpus — arena WINNERS become labeled orchestration traces.

Track ``orchestration-arena-v1-2026-06`` next-item 3: "Connect arena winners to
a cold-start trace corpus (no training yet; corpus only)."

Zero-weight doctrine (spec §5, §6.9): this module produces LABELS ONLY — rows a
future learned coordinator could cold-start from AFTER training is earned. It
never trains, never touches archive fitness, and never feeds anything back into
routing. Only genomes whose arena closeout is ``positive_lift_candidate`` (beat
best-single at budget parity, with significance, Council-corroborated) enter
the corpus; measured-negative / inconclusive / contaminated runs never do.

Every row is deterministic and replayable: the same winner genome against the
same frozen taskpack always yields the same rows, so the corpus is verifiable
evidence, not accumulated state.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Iterable

from dharma_swarm.coordination.arena.runner import ArenaRunner
from dharma_swarm.coordination.arena.scorer import scorer_hash

if TYPE_CHECKING:  # avoid a runtime cross-import; entries are duck-typed
    from dharma_swarm.coordination.orchestrator_v1 import ArchiveEntry

COLD_START_TRACE_SCHEMA = "orchestration_arena_v1_cold_start_trace.v1"
_WINNER_STATE = "positive_lift_candidate"


def build_cold_start_corpus(
    runner: ArenaRunner, entries: Iterable["ArchiveEntry"]
) -> list[dict[str, Any]]:
    """Replay each WINNER genome hermetically and emit one labeled row per task.

    ``entries`` are archive entries (duck-typed: ``.genome`` +
    ``.closeout_state``); non-winners are skipped, never partially included.
    Correctness labels come from the deterministic scorer's scorecard — the sole
    correctness authority — not from any judge or vote.
    """
    rows: list[dict[str, Any]] = []
    manifest_hash = runner.taskpack.task_manifest_hash()
    oracle = scorer_hash()
    winners = [e for e in entries if e.closeout_state == _WINNER_STATE]
    for entry in sorted(winners, key=lambda e: e.genome.genome_id):
        genome = entry.genome
        arm = runner.run_arm("cold_start_corpus_replay", genome)
        per_task = arm.scorecard["per_task"]
        traces = {t["task_id"]: t for t in arm.trace_receipts}
        for task_id in runner.taskpack.task_ids():
            trace = traces.get(task_id, {})
            rows.append(
                {
                    "schema": COLD_START_TRACE_SCHEMA,
                    "genome_id": genome.genome_id,
                    "behavioral_cell": list(genome.behavioral_descriptors.bin_key()),
                    "adjudication_rule": genome.adjudication_rule,
                    "roster": [m.member_id for m in genome.roster],
                    "closeout_state": entry.closeout_state,
                    "task_id": task_id,
                    "family": runner.taskpack.family_of(task_id),
                    "prompt": runner.taskpack.prompt_of(task_id),
                    "answers": trace.get("answers", {}),
                    "aggregated_answer": trace.get("aggregated_answer", ""),
                    "correct": bool(per_task.get(task_id, False)),
                    "task_manifest_hash": manifest_hash,
                    "scorer_hash": oracle,
                }
            )
    return rows


def corpus_sha256(rows: list[dict[str, Any]]) -> str:
    """Content hash over the serialized corpus (pins it in the report receipt)."""
    return hashlib.sha256(render_corpus_jsonl(rows).encode("utf-8")).hexdigest()


def render_corpus_jsonl(rows: list[dict[str, Any]]) -> str:
    """Deterministic JSONL serialization (same rows -> same bytes -> same hash)."""
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)


__all__ = [
    "COLD_START_TRACE_SCHEMA",
    "build_cold_start_corpus",
    "corpus_sha256",
    "render_corpus_jsonl",
]
