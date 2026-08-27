"""The Foundry inner loop — army -> tripwires -> ring 1 -> grid -> ring 2.

One generation: select mutators (army), have each propose a candidate against a
parent elite, run the ring-1 gate (static tripwires, then determinism + timing
on apparent wins), insert survivors into the MAP-Elites grid, and re-verify new
elite wins on held-out workloads (ring 2). The loop halts on the kill-switch and
respects the monthly budget (free lanes always allowed). It never selects on
money — fitness comes only from the evaluator.

The ``propose_fn`` seam is where the real army calls models (mixed-MoA over
``model_pool``/``evolution_roster``); tests inject a synthetic proposer so the
whole loop runs hermetically.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from dharma_swarm.foundry import killswitch
from dharma_swarm.foundry.army import (
    CONFIG_A_ROSTER,
    ArmyModel,
    MutationBudget,
    select_mutators,
)
from dharma_swarm.foundry.elite_grid import EliteGrid
from dharma_swarm.foundry.evaluator import Candidate, Evaluator, blind_evaluate
from dharma_swarm.foundry.heldout import HeldoutOutcome, run_heldout
from dharma_swarm.foundry.tripwires import (
    TripwireReport,
    check_determinism,
    check_timing,
    scan_tripwires,
)

ProposeFn = Callable[[ArmyModel, str | None, int], Candidate]
DescriptorFn = Callable[[Candidate], tuple]


def _default_descriptor(candidate: Candidate) -> tuple:
    """Behavior descriptor: (diff-size bucket, origin-model family)."""
    size_bucket = min(len(candidate.diff) // 200, 9)
    family = (candidate.origin_model.split("-")[0] or "unknown")[:16]
    return (size_bucket, family)


@dataclass
class GenerationReport:
    generation: int
    proposed: int = 0
    ring1_wins: int = 0
    tripwire_trips: int = 0
    grid_coverage: int = 0
    best_fitness: float = 0.0
    spend_usd: float = 0.0
    ring2_checked: int = 0
    ring2_survivors: int = 0
    ring2_promotion_blocked: int = 0
    provider_failures: int = 0
    survival_rates: list[float] = field(default_factory=list)
    trip_reasons: dict[str, int] = field(default_factory=dict)

    def mean_survival(self) -> float:
        return sum(self.survival_rates) / len(self.survival_rates) if self.survival_rates else 0.0


@dataclass
class FoundryLoop:
    """Composes the army, tripwires, evaluator, grid, and held-out ring."""

    evaluator: Evaluator
    propose_fn: ProposeFn
    heldout_evaluators: dict[str, Evaluator] = field(default_factory=dict)
    allowed_paths: list[str] | None = None
    strategy: str = "explore"
    per_generation: int = 6
    timing_floor_s: float = 0.0
    survival_threshold: float = 0.5
    # A candidate must beat the measured baseline, not merely score above zero.
    win_floor: float = 0.0
    budget: MutationBudget = field(default_factory=MutationBudget)
    descriptor_fn: DescriptorFn = _default_descriptor
    grid: EliteGrid = field(default_factory=EliteGrid)
    roster: tuple[ArmyModel, ...] = CONFIG_A_ROSTER
    agents_root: object | None = None
    state_root: object | None = None
    on_survivor: Callable[[Candidate, float, HeldoutOutcome], None] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.per_generation, int) or self.per_generation < 0:
            raise ValueError("per_generation must be a non-negative integer")
        if not math.isfinite(self.timing_floor_s) or self.timing_floor_s < 0:
            raise ValueError("timing_floor_s must be finite and non-negative")
        if (
            not math.isfinite(self.survival_threshold)
            or not 0.0 <= self.survival_threshold <= 1.0
        ):
            raise ValueError("survival_threshold must be finite and within [0, 1]")
        if not math.isfinite(self.win_floor):
            raise ValueError("win_floor must be finite")
        if (
            not math.isfinite(self.budget.cap_usd)
            or self.budget.cap_usd < 0
            or not math.isfinite(self.budget.spent_usd)
            or self.budget.spent_usd < 0
            or self.budget.spent_usd > self.budget.cap_usd
        ):
            raise ValueError("mutation budget must be finite, non-negative, and within cap")

        prepared: set[int] = set()
        self.evaluator.prepare()
        prepared.add(id(self.evaluator))
        for evaluator in self.heldout_evaluators.values():
            if id(evaluator) not in prepared:
                evaluator.prepare()
                prepared.add(id(evaluator))

    def _ring1(
        self, candidate: Candidate, seed: int
    ) -> tuple[float, TripwireReport, tuple[str, ...], bool, dict | None]:
        report = scan_tripwires(candidate, allowed_paths=self.allowed_paths)
        first = blind_evaluate(
            self.evaluator,
            candidate,
            seed=seed,
            tripwires_fired=report.fired,
        )
        receipt = first
        second = None
        fired = list(report.fired)
        # Only re-verify apparent wins with the expensive determinism/timing checks.
        if receipt.fitness > 0:
            second = blind_evaluate(self.evaluator, candidate, seed=seed)
            det = check_determinism(receipt, second)
            tim = check_timing(receipt, floor_s=self.timing_floor_s)
            for trip in (det, tim):
                if trip and trip not in fired:
                    fired.append(trip)
            if det or tim:
                receipt = blind_evaluate(self.evaluator, candidate, seed=seed,
                                         tripwires_fired=tuple(fired))
        promotion = receipt.promotion_allowed
        isolation_proof = receipt.isolation_proof
        if second is not None:
            promotion = bool(
                promotion
                and first.promotion_allowed
                and second.promotion_allowed
                and first.run_identity is not None
                and second.run_identity is not None
                and first.run_identity["run_id"] != second.run_identity["run_id"]
                and first.run_identity["command_digest"]
                == second.run_identity["command_digest"]
                and first.run_identity["output_digest"]
                == second.run_identity["output_digest"]
            )
            isolation_proof = (
                {
                    "schema_version": "foundry_ring1_isolation.v1",
                    "promotion_allowed": True,
                    "primary": first.isolation_proof,
                    "determinism_recheck": second.isolation_proof,
                }
                if promotion
                else None
            )
        return (
            receipt.fitness,
            report,
            tuple(fired),
            promotion,
            isolation_proof,
        )

    def run_generation(self, generation: int) -> GenerationReport:
        killswitch.check(agents_root=self.agents_root, state_root=self.state_root)
        report = GenerationReport(generation=generation)
        models = select_mutators(self.strategy, self.per_generation, roster=self.roster,
                                 seed=generation)
        parent = self.grid.best()
        parent_id = parent.candidate_id if parent else None
        new_wins: list[tuple[Candidate, float, bool, dict | None]] = []

        for i, model in enumerate(models):
            if not self.budget.can_afford(model):
                continue  # metered lane out of budget; free lanes still run
            candidate = self.propose_fn(model, parent_id, generation * 1000 + i)
            if candidate.metadata.get("proposal_status") == "provider_error":
                report.provider_failures += 1
                report.trip_reasons["provider_error"] = (
                    report.trip_reasons.get("provider_error", 0) + 1
                )
                continue
            report.spend_usd += self.budget.charge(model)
            report.proposed += 1
            fitness, _, fired, ring1_promotion, ring1_proof = self._ring1(
                candidate, seed=generation
            )
            if fired:
                report.tripwire_trips += 1
                for reason in fired:
                    report.trip_reasons[reason] = report.trip_reasons.get(reason, 0) + 1
            if fitness > 0.0 and fitness > self.win_floor:
                report.ring1_wins += 1
                if self.grid.add(self.descriptor_fn(candidate), candidate.candidate_id,
                                 fitness, {"origin_model": model.id}):
                    new_wins.append((candidate, fitness, ring1_promotion, ring1_proof))

        # Ring 2: re-verify newly promoted elites on held-out workloads.
        if self.heldout_evaluators:
            for candidate, fitness, ring1_promotion, ring1_proof in new_wins:
                outcome = run_heldout(
                    candidate, self.heldout_evaluators,
                    in_loop_fitness=fitness,
                    baseline_fitness=self.win_floor,
                    seed=generation,
                    survival_threshold=self.survival_threshold,
                    in_loop_promotion_allowed=ring1_promotion,
                    in_loop_isolation_proof=ring1_proof,
                )
                report.ring2_checked += 1
                report.survival_rates.append(outcome.survival_rate)
                if outcome.survived and outcome.promotion_allowed:
                    report.ring2_survivors += 1
                    if self.on_survivor is not None:
                        self.on_survivor(candidate, fitness, outcome)
                elif outcome.survived:
                    report.ring2_promotion_blocked += 1

        report.grid_coverage = self.grid.coverage()
        best = self.grid.best()
        report.best_fitness = best.fitness if best else 0.0
        return report

    def run(self, n_generations: int) -> list[GenerationReport]:
        reports: list[GenerationReport] = []
        for gen in range(n_generations):
            if self.budget.exhausted():
                break
            try:
                reports.append(self.run_generation(gen))
            except killswitch.FoundryStopped:
                break
        return reports
