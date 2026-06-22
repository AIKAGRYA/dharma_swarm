"""Task curator — layer (B) of the two-layer arena (spec §3). STUB.

The curator is the EVOLVING, world-fed layer. It may expand the task universe
freely (eventually via the throat/Bronze ingestion) but it can NEVER mutate the
frozen scored slice mid-epoch — that hard boundary is the anti-corruption
invariant (§6.1: frozen scored slice per epoch).

This keystone ships only the stub + the boundary it must honor. The live ingestion
seam is out of scope (spec §10 step 5, the throat) and intentionally not built here.
"""

from __future__ import annotations

from dharma_swarm.coordination.arena.taskpack import ArenaTask, Taskpack


class TaskCurator:
    """Stub curator. Proposes candidate tasks WITHOUT touching the frozen slice."""

    def __init__(self, frozen: Taskpack) -> None:
        self._frozen_manifest_hash = frozen.task_manifest_hash()
        self.frozen = frozen
        self.candidate_pool: list[ArenaTask] = []

    def propose(self, task: ArenaTask) -> None:
        """Add a candidate task to the (mutable) curator pool only."""
        self.candidate_pool.append(task)

    def assert_frozen_slice_intact(self) -> None:
        """The frozen slice must be byte-stable across the epoch (spec §6.1)."""
        if self.frozen.task_manifest_hash() != self._frozen_manifest_hash:
            raise RuntimeError(
                "frozen scored slice mutated mid-epoch — anti-corruption invariant "
                "§6.1 violated. The curator may expand candidates but NEVER the "
                "frozen slice."
            )

    def promote_next_epoch(self) -> Taskpack:  # pragma: no cover - future seam
        """Build the NEXT epoch's frozen pack from curated candidates.

        Out of scope for the keystone (needs the throat/Bronze ingestion, spec
        §10 step 5). Documented seam only.
        """
        raise NotImplementedError(
            "Next-epoch promotion needs the world-fed throat seam (spec §10 step 5)."
        )


__all__ = ["TaskCurator"]
