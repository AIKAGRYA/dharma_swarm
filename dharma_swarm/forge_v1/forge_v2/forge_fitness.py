"""Forge-backed DGM fitness adapter.

This is THE JOIN: scaffold genomes are scored by the real Forge v2 runner,
which grades final patches with the Forge/SWE-bench Docker path.  The genome is
an arm/scaffold spec, not a Python source diff.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal

from dharma_swarm.model_hierarchy import default_model
from dharma_swarm.models import ProviderType

from . import runner

SplitName = Literal["explore", "confirm"]


def _default_generator() -> str:
    return default_model(ProviderType.ZHIPU)


def _default_verifier() -> str:
    return default_model(ProviderType.OPENROUTER)


@dataclass(frozen=True)
class ArmSpec:
    """A mutation genome for Forge scaffold evolution."""

    arm: str
    generator: str = field(default_factory=_default_generator)
    verifier: str = field(default_factory=_default_verifier)
    mix_models: list[str] = field(default_factory=list)
    label: str = "forge_fitness"
    scaffold_ref: str = "forge_v2.arm_spec.v1"


@dataclass(frozen=True)
class ForgeGenomeFitness:
    """Fitness trace returned to DGM/archive layers."""

    genome: dict[str, Any]
    split: SplitName
    fitness: float
    ci: dict[str, Any]
    closeout: str
    real_grade: bool
    promote_eligible: bool
    runner_receipt: dict[str, Any]
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _coerce_arm_spec(genome: ArmSpec | dict[str, Any]) -> ArmSpec:
    if isinstance(genome, ArmSpec):
        return genome
    if not isinstance(genome, dict):
        raise TypeError("genome must be ArmSpec or dict")
    return ArmSpec(
        arm=str(genome.get("arm", "verify_chain")),
        generator=str(genome.get("generator") or _default_generator()),
        verifier=str(genome.get("verifier") or _default_verifier()),
        mix_models=list(genome.get("mix_models", []) or []),
        label=str(genome.get("label", "forge_fitness")),
        scaffold_ref=str(genome.get("scaffold_ref", "forge_v2.arm_spec.v1")),
    )


def _split_n_explore(instance_ids: list[str], split: SplitName) -> int:
    if split == "explore":
        return len(instance_ids)
    if split == "confirm":
        return 0
    raise ValueError(f"unsupported split: {split!r}")


def _fitness_from_receipt(receipt: dict[str, Any], split: SplitName) -> tuple[float, dict[str, Any]]:
    split_contrasts = dict(receipt.get("split_contrasts", {}) or {})
    ci = dict(split_contrasts.get(split, {}) or {})
    if not ci:
        ci = dict(receipt.get("contrast_vs_class_null", {}) or {})
    return float(ci.get("mean", 0.0)), ci


def grade_genome(
    genome: ArmSpec | dict[str, Any],
    instance_ids: list[str],
    *,
    split: SplitName,
    budget_cap: int = 60_000,
    budget_usd: float = 0.25,
    per_call_tokens: int = 3_500,
    k_self_moa: int = 1,
    grade_timeout: int = 1_200,
    timeout_s: int = 240,
    strategy: str = "explore",
    roster_n: int = 14,
    replicates: int = 1,
    runner_fn: Callable[..., dict[str, Any]] = runner.run,
) -> ForgeGenomeFitness:
    """Grade a scaffold genome through the real Forge v2 runner.

    ``split=explore`` is for learning signal only; ``split=confirm`` is the only
    promotion-capable path.  Callers may inject ``runner_fn`` in tests, but the
    default is the production runner, which performs the Docker grade.
    """
    if not instance_ids:
        raise ValueError("instance_ids must be non-empty")

    spec = _coerce_arm_spec(genome)
    receipt = runner_fn(
        list(instance_ids),
        n_explore=_split_n_explore(list(instance_ids), split),
        replicates=replicates,
        budget_cap=budget_cap,
        budget_usd=budget_usd,
        per_call_tokens=per_call_tokens,
        k_self_moa=k_self_moa,
        grade_timeout=grade_timeout,
        timeout_s=timeout_s,
        strategy=strategy,
        roster_n=roster_n,
        gen_id=spec.generator,
        ver_id=spec.verifier,
        label=spec.label,
        arm=spec.arm,
        mix_ids=list(spec.mix_models),
    )
    fitness, ci = _fitness_from_receipt(receipt, split)
    closeout = str(receipt.get("closeout", ""))
    any_invalid = bool((receipt.get("budget_matched_proof", {}) or {}).get("any_invalid", False))
    ci_lower = float(ci.get("lower", 0.0))
    blockers: list[str] = []
    if split != "confirm":
        blockers.append("promotion_requires_confirm_split")
    if closeout != "positive_lift_candidate":
        blockers.append(f"closeout_{closeout or 'missing'}")
    if ci_lower <= 0.0:
        blockers.append("confirm_ci_lower<=0")
    if any_invalid:
        blockers.append("invalid_budget")

    return ForgeGenomeFitness(
        genome=asdict(spec),
        split=split,
        fitness=fitness,
        ci=ci,
        closeout=closeout,
        real_grade=True,
        promote_eligible=not blockers,
        runner_receipt=receipt,
        blockers=blockers,
    )


__all__ = ["ArmSpec", "ForgeGenomeFitness", "grade_genome"]
