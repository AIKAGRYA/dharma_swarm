"""Ring 2 — held-out re-verification of in-loop winners.

An in-loop win is a hypothesis, not a result. Ring 2 re-scores a survivor on
rotated workloads that were NEVER shown to the search, on a fresh evaluation, and
reports the survival rate: how much of the claimed improvement holds up. This is
the number the kill-metrics watch — if survival collapses across cohorts, the
loop is optimizing its evaluator, not the code (the OpenEvolve MLX / Sakana CUDA
failure mode).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from dharma_swarm.foundry.evaluator import (
    Candidate,
    Evaluator,
    blind_evaluate,
    candidate_digest,
    validate_isolation_proof_payload,
)
from dharma_swarm.foundry.tripwires import check_determinism


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


def _valid_ring1_proof(proof: dict | None, candidate: Candidate) -> bool:
    expected = {
        "schema_version",
        "promotion_allowed",
        "primary",
        "determinism_recheck",
    }
    if type(proof) is not dict or set(proof) != expected:
        return False
    if (
        proof.get("schema_version") != "foundry_ring1_isolation.v1"
        or proof.get("promotion_allowed") is not True
    ):
        return False
    bindings = []
    for key in ("primary", "determinism_recheck"):
        validated, allows = validate_isolation_proof_payload(proof.get(key))
        if not allows or validated is None:
            return False
        binding = validated["evaluation_binding"]
        if (
            binding["candidate_id"] != candidate.candidate_id
            or binding["target_id"] != candidate.target_id
            or binding["candidate_digest"] != candidate_digest(candidate)
        ):
            return False
        bindings.append(binding)
    return (
        bindings[0]["evaluator_id"] == bindings[1]["evaluator_id"]
        and bindings[0]["seed"] == bindings[1]["seed"]
        and bindings[0]["run_id"] != bindings[1]["run_id"]
    )


def run_heldout(
    candidate: Candidate,
    heldout_evaluators: dict[str, Evaluator],
    *,
    in_loop_fitness: float,
    baseline_fitness: float = 0.0,
    seed: int = 0,
    survival_threshold: float = 0.5,
    in_loop_promotion_allowed: bool = False,
    in_loop_isolation_proof: dict | None = None,
) -> HeldoutOutcome:
    """Re-verify a candidate on never-in-loop workloads and score its survival.

    ``survival_rate`` is the held-out gain above ``baseline_fitness`` divided
    by the in-loop gain above that same baseline, clamped to [0, 1].
    ``survived`` is True when that rate meets
    ``survival_threshold`` (default: at least half the claimed gain holds).
    """
    if any(type(name) is not str or not name or name == "ring1"
           for name in heldout_evaluators):
        raise ValueError("held-out workload names cannot use reserved key 'ring1'")
    if not math.isfinite(survival_threshold) or not 0.0 <= survival_threshold <= 1.0:
        raise ValueError("survival_threshold must be finite and within [0, 1]")
    if not math.isfinite(baseline_fitness):
        raise ValueError("baseline_fitness must be finite")
    if not math.isfinite(in_loop_fitness):
        in_loop_fitness = 0.0

    per_workload: dict[str, float] = {}
    proofs: dict[str, dict] = {}
    if in_loop_isolation_proof is not None:
        proofs["ring1"] = in_loop_isolation_proof
    workload_promotion: list[bool] = []
    for name, evaluator in heldout_evaluators.items():
        primary = blind_evaluate(evaluator, candidate, seed=seed)
        recheck = blind_evaluate(evaluator, candidate, seed=seed)
        deterministic = check_determinism(primary, recheck) is None
        per_workload[name] = primary.fitness if deterministic else 0.0
        proof_bundle = {
            "schema_version": "foundry_heldout_isolation.v1",
            "promotion_allowed": bool(
                deterministic
                and primary.promotion_allowed
                and recheck.promotion_allowed
                and primary.run_identity is not None
                and recheck.run_identity is not None
                and primary.run_identity["run_id"] != recheck.run_identity["run_id"]
            ),
            "primary": primary.isolation_proof,
            "determinism_recheck": recheck.isolation_proof,
        }
        workload_promotion.append(
            proof_bundle["promotion_allowed"] is True
            and isinstance(primary.isolation_proof, dict)
            and isinstance(recheck.isolation_proof, dict)
            and primary.isolation_proof.get("promotion_allowed") is True
            and recheck.isolation_proof.get("promotion_allowed") is True
        )
        if primary.isolation_proof is not None or recheck.isolation_proof is not None:
            proofs[name] = proof_bundle

    try:
        mean_heldout = (
            math.fsum(per_workload.values()) / len(per_workload)
            if per_workload
            else 0.0
        )
    except (OverflowError, ValueError):
        mean_heldout = 0.0
    if not math.isfinite(mean_heldout):
        mean_heldout = 0.0
    in_loop_gain = in_loop_fitness - baseline_fitness
    heldout_gain = mean_heldout - baseline_fitness
    if (
        not math.isfinite(in_loop_gain)
        or not math.isfinite(heldout_gain)
        or in_loop_gain <= 0
        or heldout_gain <= 0
    ):
        survival_rate = 0.0
    else:
        ratio = heldout_gain / in_loop_gain
        survival_rate = max(0.0, min(1.0, ratio)) if math.isfinite(ratio) else 0.0
    # Threshold zero may be useful for exploration reports, but a candidate
    # that preserves none of its measured gain is never a promotion survivor.
    survived = (
        bool(per_workload)
        and survival_rate > 0.0
        and survival_rate >= survival_threshold
    )

    return HeldoutOutcome(
        candidate_id=candidate.candidate_id,
        in_loop_fitness=in_loop_fitness,
        heldout_fitness=mean_heldout,
        survival_rate=survival_rate,
        survived=survived,
        workloads=tuple(sorted(per_workload)),
        per_workload=per_workload,
        promotion_allowed=(
            survived
            and in_loop_promotion_allowed is True
            and _valid_ring1_proof(in_loop_isolation_proof, candidate)
            and bool(workload_promotion)
            and all(workload_promotion)
        ),
        isolation_proofs=proofs,
    )
