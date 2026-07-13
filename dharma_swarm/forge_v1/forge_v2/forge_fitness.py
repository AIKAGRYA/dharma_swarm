"""Forge-backed DGM fitness adapter.

This is THE JOIN: scaffold genomes are scored by the real Forge v2 runner,
which grades final patches with the Forge/SWE-bench Docker path.  The genome is
an arm/scaffold spec, not a Python source diff.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Literal

from . import runner
from .promote import DEFAULT_PREREGISTERED_MDE, MIN_CONFIRM_N_FOR_PROMOTION, MIN_PROMOTION_EFFECT

SplitName = Literal["explore", "confirm"]
SUBPROCESS_RESULT_PREFIX = "FORGE_GENOME_FITNESS_JSON "


def _default_generator() -> str:
    return runner.DEFAULT_FORGE_GENERATOR_MODEL


def _default_verifier() -> str:
    return runner.DEFAULT_FORGE_VERIFIER_MODEL


@dataclass(frozen=True)
class ArmSpec:
    """A mutation genome for Forge scaffold evolution."""

    arm: str
    generator: str = field(default_factory=_default_generator)
    verifier: str = field(default_factory=_default_verifier)
    mix_models: list[str] = field(default_factory=list)
    window_chars: int = runner.DEFAULT_WINDOW_CHARS
    selection_strategy: str = "verify_chain"
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
    raw_window = genome.get("window_chars", runner.DEFAULT_WINDOW_CHARS)
    try:
        window_chars = int(raw_window)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"window_chars must be an integer, got {raw_window!r}") from exc
    if window_chars <= 0:
        raise ValueError("window_chars must be positive")
    return ArmSpec(
        arm=str(genome.get("arm", "verify_chain")),
        generator=str(genome.get("generator") or _default_generator()),
        verifier=str(genome.get("verifier") or _default_verifier()),
        mix_models=list(genome.get("mix_models", []) or []),
        window_chars=window_chars,
        selection_strategy=str(genome.get("selection_strategy") or "verify_chain"),
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


def _ci_half_width(ci: dict[str, Any]) -> float:
    return max(0.0, (float(ci.get("upper", 0.0)) - float(ci.get("lower", 0.0))) / 2.0)


def _contamination_state(receipt: dict[str, Any]) -> str:
    value = receipt.get("contamination_state")
    if isinstance(value, dict):
        return str(value.get("state", "unknown"))
    return str(value or "unknown")


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
        window_chars=spec.window_chars,
    )
    fitness, ci = _fitness_from_receipt(receipt, split)
    closeout = str(receipt.get("closeout", ""))
    any_invalid = bool((receipt.get("budget_matched_proof", {}) or {}).get("any_invalid", False))
    ci_lower = float(ci.get("lower", 0.0))
    confirm_ci = dict((receipt.get("split_contrasts", {}) or {}).get("confirm", {}) or {})
    explore_ci = dict((receipt.get("split_contrasts", {}) or {}).get("explore", {}) or {})
    contamination_state = _contamination_state(receipt)
    confirm_n = int(confirm_ci.get("n", 0) or 0)
    explore_n = int(explore_ci.get("n", 0) or 0)
    blockers: list[str] = []
    if split != "confirm":
        blockers.append("promotion_requires_confirm_split")
    if closeout != "positive_lift_candidate":
        blockers.append(f"closeout_{closeout or 'missing'}")
    if ci_lower <= 0.0:
        blockers.append("confirm_ci_lower<=0")
    if split == "confirm" and confirm_n < MIN_CONFIRM_N_FOR_PROMOTION:
        blockers.append("confirm_n<500")
    if split == "confirm" and explore_n:
        blockers.append("split_confirm_not_allowed_for_promotion")
    if split == "confirm" and fitness < MIN_PROMOTION_EFFECT:
        blockers.append("confirm_mean<0.05")
    if split == "confirm" and _ci_half_width(confirm_ci or ci) > DEFAULT_PREREGISTERED_MDE:
        blockers.append("confirm_power_insufficient")
    if split == "confirm" and contamination_state not in {"fresh_heldout", "self_mod_clean", "clean"}:
        blockers.append(f"contamination_{contamination_state}")
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


def grade_genome_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Grade a JSON payload in a fresh process for async DGM callers."""
    kwargs: dict[str, Any] = {}
    for key in (
        "budget_cap",
        "budget_usd",
        "per_call_tokens",
        "k_self_moa",
        "grade_timeout",
        "timeout_s",
        "strategy",
        "roster_n",
        "replicates",
    ):
        if key in payload:
            kwargs[key] = payload[key]
    fitness = grade_genome(
        payload["genome"],
        list(payload["instance_ids"]),
        split=payload["split"],
        **kwargs,
    )
    return fitness.to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forge genome fitness subprocess worker")
    parser.add_argument("--json-stdin", action="store_true", help="Read grading payload JSON from stdin")
    args = parser.parse_args(argv)
    if not args.json_stdin:
        parser.error("--json-stdin is required")
    payload = json.loads(sys.stdin.read())
    result = grade_genome_from_payload(payload)
    print(SUBPROCESS_RESULT_PREFIX + json.dumps(result, sort_keys=True, default=str), flush=True)
    return 0


__all__ = [
    "ArmSpec",
    "ForgeGenomeFitness",
    "SUBPROCESS_RESULT_PREFIX",
    "grade_genome",
    "grade_genome_from_payload",
]


if __name__ == "__main__":
    raise SystemExit(main())
