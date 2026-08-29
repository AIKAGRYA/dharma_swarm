"""Append-only candidate store — a thin wrap over EvolutionArchive.

Reuse Ledger: wraps ``archive.EvolutionArchive`` + its MerkleLog; never a new
JSONL lineage store, never a new hash chain. ``enforce_one_wire=False`` is an
explicit, RECORDED choice (the lab is its own fitness authority in shadow;
the governed ~/.dharma/evolution/archive.jsonl is never touched).

Row semantics:
- entry.id = content-addressed candidate_id (ids.candidate_id) — dedup is an
  identity property, not a policy.
- state ∈ {graded, blocked, errored, duplicate} lives in
  test_results["forge_lab"]["state"]. Only graded rows carry fitness-bearing
  status ("shadow"), so selection naturally sees only graded candidates while
  blocked/errored children persist as evidence (mycelial compost).
- append_graded never trusts a caller-asserted aggregate: pass_rate is
  recomputed from per_task (mismatch raises), and a budget-invalid grade is
  re-routed to the errored lane — over cap makes the run INVALID, never a
  lower score.
- The archive is never pruned. Ever.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from dharma_swarm.archive import ArchiveEntry, EvolutionArchive, FitnessScore
from dharma_swarm.forge_lab.freeform_explore import FreeformExploreEnvelope

FORGE_LAB_ROW_SCHEMA = "forge_lab.candidate_row.v0"

GRADED = "graded"
BLOCKED = "blocked"
ERRORED = "errored"
DUPLICATE = "duplicate"


class CandidateStore:
    def __init__(self, archive_path: Path | str, *, experiment_id: str, category: str = "agent_evolution") -> None:
        self.archive_path = Path(archive_path)
        self.experiment_id = experiment_id
        self.category = category
        # Non-governed path + explicit opt-out => One Wire never consulted;
        # recorded by experiment.py in run_manifest.archive_fitness_authority.
        self.archive = EvolutionArchive(path=self.archive_path, enforce_one_wire=False)

    async def load(self) -> None:
        await self.archive.load()

    async def has(self, candidate_id: str) -> bool:
        return await self.archive.get_entry(candidate_id) is not None

    async def graded_entries(self) -> list[ArchiveEntry]:
        return [e for e in self.archive._entries.values() if self._row(e).get("state") == GRADED]

    def n_children_map(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.archive._entries.values():
            if entry.parent_id:
                counts[entry.parent_id] = counts.get(entry.parent_id, 0) + 1
        return counts

    @staticmethod
    def _row(entry: ArchiveEntry) -> dict[str, Any]:
        row = entry.test_results.get("forge_lab")
        return row if isinstance(row, dict) else {}

    async def append_graded(
        self,
        *,
        candidate_id: str,
        genome: dict[str, Any],
        parent_id: str | None,
        generation: int,
        loop_iteration: int,
        role: str,
        pass_rate: float,
        per_task: list[dict[str, Any]],
        budget: dict[str, Any],
        tier: str,
        executed_fields: tuple[str, ...],
        ignored_fields: tuple[str, ...],
        envelope: FreeformExploreEnvelope,
        mutation_notes: str = "",
        model: str = "",
        tokens_used: int = 0,
    ) -> ArchiveEntry:
        # Custody honesty (L009/L022-L024): only graded-AND-budget-valid rows
        # may bear fitness. Per the Budget contract an over-cap run is INVALID,
        # never a lower score — re-route to the errored lane, never graded.
        if budget.get("invalid"):
            return await self._append_non_graded(
                ERRORED,
                candidate_id=candidate_id, genome=genome, parent_id=parent_id,
                generation=generation, loop_iteration=loop_iteration,
                reasons=[f"budget_invalid:{budget.get('invalid_reason') or 'over_cap'}"],
            )
        # Never trust a caller-asserted aggregate: pass_rate is recomputed from
        # per_task and a mismatch is refused fail-closed.
        recomputed = (
            (sum(1 for r in per_task if r.get("resolved")) / len(per_task))
            if per_task else 0.0
        )
        if abs(float(pass_rate) - recomputed) > 1e-9:
            raise ValueError(f"pass_rate_mismatch: caller={pass_rate} recomputed={recomputed}")
        pass_rate = recomputed
        entry = ArchiveEntry(
            id=candidate_id,
            parent_id=parent_id,
            component=f"forge_lab::{genome.get('arm_kind', 'unknown')}",
            change_type="explore_seed" if role == "seed_baseline" else "explore_candidate",
            description=mutation_notes or genome.get("notes", ""),
            fitness=FitnessScore(correctness=max(0.0, min(1.0, pass_rate))),
            status="shadow",
            experiment_id=self.experiment_id,
            model=model,
            tokens_used=tokens_used,
            test_results={
                "forge_lab": {
                    "schema": FORGE_LAB_ROW_SCHEMA,
                    "state": GRADED,
                    "category": self.category,
                    "genome": genome,
                    "generation": generation,
                    "loop_iteration": loop_iteration,
                    "role": role,
                    "pass_rate": pass_rate,
                    "per_task": per_task,
                    "behavior": {
                        "solved_task_ids": sorted(
                            str(r.get("task_id")) for r in per_task if r.get("resolved")
                        )
                    },
                    "budget": budget,
                    "tier": tier,
                    "executed_genome_fields": list(executed_fields),
                    "ignored_genome_fields": list(ignored_fields),
                    "envelope": asdict(envelope),
                }
            },
        )
        await self.archive.add_entry(entry)
        return entry

    async def _append_non_graded(
        self,
        state: str,
        *,
        candidate_id: str,
        genome: Any,
        parent_id: str | None,
        generation: int,
        loop_iteration: int,
        reasons: list[str],
        raw_output: str = "",
    ) -> ArchiveEntry:
        entry = ArchiveEntry(
            id=candidate_id,
            parent_id=parent_id,
            component="forge_lab::non_graded",
            change_type=f"explore_{state}",
            description="; ".join(reasons)[:500],
            status="proposed",  # never fitness-bearing => invisible to selection
            experiment_id=self.experiment_id,
            test_results={
                "forge_lab": {
                    "schema": FORGE_LAB_ROW_SCHEMA,
                    "state": state,
                    "category": self.category,
                    "genome": genome,
                    "generation": generation,
                    "loop_iteration": loop_iteration,
                    "reasons": reasons,
                    "raw_output": raw_output[:20000],
                }
            },
        )
        await self.archive.add_entry(entry)
        return entry

    async def append_blocked(self, **kw: Any) -> ArchiveEntry:
        return await self._append_non_graded(BLOCKED, **kw)

    async def append_errored(self, **kw: Any) -> ArchiveEntry:
        return await self._append_non_graded(ERRORED, **kw)

    async def append_duplicate(self, **kw: Any) -> ArchiveEntry:
        return await self._append_non_graded(DUPLICATE, **kw)


__all__ = ["CandidateStore", "GRADED", "BLOCKED", "ERRORED", "DUPLICATE", "FORGE_LAB_ROW_SCHEMA"]
