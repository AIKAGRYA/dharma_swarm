"""Ring 2 — held-out re-verification of in-loop winners.

An in-loop win is a hypothesis, not a result. Ring 2 re-scores a survivor on
rotated workloads that were NEVER shown to the search, on a fresh evaluation, and
reports the survival rate: how much of the claimed improvement holds up. This is
the number the kill-metrics watch — if survival collapses across cohorts, the
loop is optimizing its evaluator, not the code (the OpenEvolve MLX / Sakana CUDA
failure mode).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dharma_swarm.foundry.evaluator import Candidate, Evaluator, blind_evaluate


@dataclass(frozen=True)
class HeldoutOutcome:
    candidate_id: str
    in_loop_fitness: float
    heldout_fitness: float
    survival_rate: float
    survived: bool
    workloads: tuple[str, ...] = ()
    per_workload: dict[str, float] = field(default_factory=dict)
    promotion_allowed: bool = False
    isolation_proofs: dict[str, dict] = field(default_factory=dict)


def run_heldout(
    candidate: Candidate,
    heldout_evaluators: dict[str, Evaluator],
    *,
    in_loop_fitness: float,
    seed: int = 0,
    survival_threshold: float = 0.5,
    in_loop_promotion_allowed: bool = False,
    in_loop_isolation_proof: dict | None = None,
) -> HeldoutOutcome:
    """Re-verify a candidate on never-in-loop workloads and score its survival.

    ``survival_rate`` is mean held-out fitness divided by the in-loop fitness,
    clamped to [0, 1]. ``survived`` is True when that rate meets
    ``survival_threshold`` (default: at least half the claimed gain holds).
    """
    per_workload: dict[str, float] = {}
    proofs: dict[str, dict] = {}
    if in_loop_isolation_proof is not None:
        proofs["ring1"] = in_loop_isolation_proof
    workload_promotion: list[bool] = []
    for name, evaluator in heldout_evaluators.items():
        receipt = blind_evaluate(evaluator, candidate, seed=seed)
        per_workload[name] = receipt.fitness
        workload_promotion.append(receipt.promotion_allowed)
        if receipt.isolation_proof is not None:
            proofs[name] = receipt.isolation_proof

    mean_heldout = (
        sum(per_workload.values()) / len(per_workload) if per_workload else 0.0
    )
    if in_loop_fitness <= 0:
        survival_rate = 0.0
    else:
        survival_rate = max(0.0, min(1.0, mean_heldout / in_loop_fitness))

    return HeldoutOutcome(
        candidate_id=candidate.candidate_id,
        in_loop_fitness=in_loop_fitness,
        heldout_fitness=mean_heldout,
        survival_rate=survival_rate,
        survived=survival_rate >= survival_threshold,
        workloads=tuple(sorted(per_workload)),
        per_workload=per_workload,
        promotion_allowed=(
            in_loop_promotion_allowed
            and bool(workload_promotion)
            and all(workload_promotion)
        ),
        isolation_proofs=proofs,
    )
