"""Zero-weight orchestrator v1 (spec §10 step 4).

Emits ``OrchestrationGenome``s with a HEURISTIC generator + simple mutation
operators + bandit/Darwin selection over a MAP-Elites archive, scores them
through the hermetic Arena v1, and promotes winners to the archive.

NON-NEGOTIABLE: this is ZERO-weight (no LLM call generates genomes), ZERO-GPU,
ZERO-training. Genome generation is heuristics + mutation only. It NEVER mutates
production routing — it consults the arena's roster registry (capability
metadata) and writes only to its own archive + route receipts. It does NOT
import or touch ``provider_policy`` / ``orchestrator.py`` / ``model_hierarchy``.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dharma_swarm.coordination.arena.fixtures import ALL_MODEL_IDS
from dharma_swarm.coordination.arena.runner import ArenaRunner, render_decision_packet
from dharma_swarm.coordination.genome import (
    Lineage,
    OrchestrationGenome,
    RosterMember,
)

_ADJUDICATION_CHOICES = ("single", "synthesize", "vote")
_MAX_ROSTER = len(ALL_MODEL_IDS)


@dataclass
class ArchiveEntry:
    """One MAP-Elites cell occupant (quality-diversity, not a top-k leaderboard)."""

    genome: OrchestrationGenome
    fitness: float
    closeout_state: str
    score: float
    dpi: float
    council_verdict: str
    lineage: dict[str, Any]


class MapElitesArchive:
    """Behavioral-descriptor-binned archive. Keeps the best occupant per cell."""

    def __init__(self) -> None:
        self.cells: dict[tuple, ArchiveEntry] = {}

    def consider(self, entry: ArchiveEntry) -> bool:
        """Insert if the cell is empty or the entry beats the incumbent. Returns
        True iff it was archived (illuminated a new cell or improved one).

        Contaminated/quarantined genomes are NEVER archived — not even into an
        empty cell — so a quarantined run can never become an elite or a mutation
        parent (the 'contaminated genomes are never promotable' invariant)."""
        if entry.closeout_state == "contaminated_quarantine" or entry.fitness < 0:
            return False
        key = entry.genome.behavioral_descriptors.bin_key()
        incumbent = self.cells.get(key)
        if incumbent is None or entry.fitness > incumbent.fitness:
            self.cells[key] = entry
            return True
        return False

    def elites(self) -> list[ArchiveEntry]:
        return list(self.cells.values())

    def best(self) -> Optional[ArchiveEntry]:
        if not self.cells:
            return None
        return max(self.cells.values(), key=lambda e: e.fitness)

    def winners(self) -> list[ArchiveEntry]:
        return [e for e in self.cells.values() if e.closeout_state == "positive_lift_candidate"]


@dataclass
class EvolutionResult:
    best: Optional[ArchiveEntry]
    archive: MapElitesArchive
    route_receipts: list[dict[str, Any]] = field(default_factory=list)
    generations: int = 0
    evaluated: int = 0


class ZeroWeightOrchestratorV1:
    """Heuristic genome emitter + Darwin/MAP-Elites search over the arena."""

    def __init__(self, runner: Optional[ArenaRunner] = None, seed: int = 0) -> None:
        self.runner = runner or ArenaRunner()
        self.rng = random.Random(seed)

    # ----------------------------------------------------------- heuristic seeds
    def seed_population(self) -> list[OrchestrationGenome]:
        """Heuristic generator — NO LLM. Single-model arms, the full router, and a
        vote ensemble; mutation explores the rest of the space."""
        seeds: list[OrchestrationGenome] = []
        for model_id in ALL_MODEL_IDS:
            seeds.append(self._make_genome([model_id], "single", op="seed_single"))
        # the full specialist roster under each adjudication rule
        full = list(ALL_MODEL_IDS)
        seeds.append(self._make_genome(full, "synthesize", op="seed_router"))
        seeds.append(self._make_genome(full, "vote", op="seed_vote"))
        return seeds

    def _make_genome(
        self,
        member_ids: list[str],
        adjudication: str,
        *,
        op: str,
        parent_id: Optional[str] = None,
        generation: int = 0,
    ) -> OrchestrationGenome:
        roster = [
            RosterMember(role_id=f"r{i}", member_id=m, kind="model")
            for i, m in enumerate(member_ids)
        ]
        genome = OrchestrationGenome(
            roster=roster,
            adjudication_rule=adjudication,  # type: ignore[arg-type]
            lineage=Lineage(parent_genome_id=parent_id, mutation_op=op, generation=generation),
        )
        return genome.with_descriptors()

    # ---------------------------------------------------------------- mutation ops
    def mutate(self, parent: OrchestrationGenome, generation: int) -> OrchestrationGenome:
        members = [m.member_id for m in parent.roster]
        op = self.rng.choice(
            ["add_specialist", "drop_role", "swap_model", "change_adjudication"]
        )
        if op == "add_specialist":
            missing = [m for m in ALL_MODEL_IDS if m not in members]
            if missing and len(members) < _MAX_ROSTER:
                members = members + [self.rng.choice(missing)]
        elif op == "drop_role" and len(members) > 1:
            members = members[:-1]
        elif op == "swap_model" and members:
            i = self.rng.randrange(len(members))
            members = list(members)
            members[i] = self.rng.choice(ALL_MODEL_IDS)
        adjudication = parent.adjudication_rule
        if op == "change_adjudication":
            adjudication = self.rng.choice(_ADJUDICATION_CHOICES)
        # de-dup roster members while preserving order
        seen: set[str] = set()
        deduped = [m for m in members if not (m in seen or seen.add(m))]
        return self._make_genome(
            deduped or [self.rng.choice(ALL_MODEL_IDS)],
            adjudication,
            op=op,
            parent_id=parent.genome_id,
            generation=generation,
        )

    # ---------------------------------------------------------------- evaluation
    def evaluate(self, genome: OrchestrationGenome) -> ArchiveEntry:
        """Score one genome through the hermetic arena and build an archive entry."""
        run = self.runner.run(genome)
        contaminated = run["contaminated"]
        score = run["arm_scores"]["candidate"]
        dpi = run["_power_index"]["dpi"]
        # Fitness: capability (score) is the headline; DPI breaks ties. Contaminated
        # genomes are never promotable — fitness floored so they cannot win a cell.
        fitness = -1.0 if contaminated else score + 1e-6 * dpi
        return ArchiveEntry(
            genome=genome,
            fitness=fitness,
            closeout_state=run["closeout_state"],
            score=score,
            dpi=dpi,
            council_verdict=run["council_verdict"],
            lineage=genome.lineage.model_dump(),
        )

    # -------------------------------------------------------------- bandit select
    def _select_parent(self, archive: MapElitesArchive) -> OrchestrationGenome:
        """Darwin/bandit parent selection: epsilon-greedy over archive elites,
        biased toward higher fitness (exploitation) with exploration."""
        elites = archive.elites()
        if not elites:
            return self._make_genome([self.rng.choice(ALL_MODEL_IDS)], "single", op="cold_start")
        if self.rng.random() < 0.3:  # explore: uniform elite
            return self.rng.choice(elites).genome
        # exploit: pick among the top-fitness elites
        top = sorted(elites, key=lambda e: e.fitness, reverse=True)[: max(1, len(elites) // 2)]
        return self.rng.choice(top).genome

    # --------------------------------------------------------------------- evolve
    def evolve(
        self, generations: int = 12, output_dir: Optional[Path] = None
    ) -> EvolutionResult:
        archive = MapElitesArchive()
        route_receipts: list[dict[str, Any]] = []
        evaluated = 0

        def record(entry: ArchiveEntry, gen: int, archived: bool) -> None:
            nonlocal evaluated
            evaluated += 1
            route_receipts.append(
                {
                    "generation": gen,
                    "genome_id": entry.genome.genome_id,
                    "parent_genome_id": entry.lineage.get("parent_genome_id"),
                    "mutation_op": entry.lineage.get("mutation_op"),
                    "adjudication_rule": entry.genome.adjudication_rule,
                    "roster": [m.member_id for m in entry.genome.roster],
                    "closeout_state": entry.closeout_state,
                    "score": entry.score,
                    "archived": archived,
                    "behavioral_cell": list(entry.genome.behavioral_descriptors.bin_key()),
                }
            )

        for genome in self.seed_population():
            entry = self.evaluate(genome)
            record(entry, 0, archive.consider(entry))

        for gen in range(1, generations + 1):
            parent = self._select_parent(archive)
            child = self.mutate(parent, gen)
            entry = self.evaluate(child)
            record(entry, gen, archive.consider(entry))

        result = EvolutionResult(
            best=archive.best(),
            archive=archive,
            route_receipts=route_receipts,
            generations=generations,
            evaluated=evaluated,
        )
        if output_dir is not None:
            self._write_outputs(output_dir, result)
        return result

    def _write_outputs(self, output_dir: Path, result: EvolutionResult) -> None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "route_receipts.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in result.route_receipts),
            encoding="utf-8",
        )
        archive_rows = [
            {
                "behavioral_cell": list(key),
                "genome_id": e.genome.genome_id,
                "fitness": e.fitness,
                "score": e.score,
                "closeout_state": e.closeout_state,
                "council_verdict": e.council_verdict,
                "lineage": e.lineage,
            }
            for key, e in result.archive.cells.items()
        ]
        (out / "map_elites_archive.json").write_text(
            json.dumps({"cells": archive_rows, "winners": len(result.archive.winners())},
                       indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if result.best is not None:
            # Re-run the best genome (no output_dir, to avoid clobbering the
            # orchestrator-level route_receipts.jsonl) and emit its decision packet
            # plus the full arena artifact set under best_run/.
            run = self.runner.run(result.best.genome, output_dir=out / "best_run")
            (out / "decision_packet.md").write_text(
                render_decision_packet(run, run["_power_index"]), encoding="utf-8"
            )


__all__ = [
    "ArchiveEntry",
    "EvolutionResult",
    "MapElitesArchive",
    "ZeroWeightOrchestratorV1",
]
