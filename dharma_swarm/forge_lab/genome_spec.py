"""Scaffold genome v0 — the searchable space, governed at the membrane only.

EXPLORE accepts any dict that clears the membrane (freeform_explore law):
unknown keys are preserved as compost for future operators, never rejected.
Executability is a separate, honest question: ``executable_arm`` says whether
the grading adapter can run this genome today, and ``executed_genome_fields``
records exactly which genes the executor actually honored — a hermetic win on
ignored genes must never masquerade as evolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ARM_KINDS = ("freeform_single", "self_moa", "verify_chain", "mixed_moa")

# The genes the v0 executor actually honors, per arm kind.
EXECUTED_FIELDS: dict[str, tuple[str, ...]] = {
    "freeform_single": ("arm_kind", "generator_model", "per_call_tokens", "window_chars", "extra_instruction"),
    "self_moa": ("arm_kind", "generator_model", "k", "per_call_tokens", "window_chars"),
    "verify_chain": ("arm_kind", "generator_model", "verifier_model", "per_call_tokens", "window_chars"),
    "mixed_moa": ("arm_kind", "generator_model", "verifier_model", "per_call_tokens", "window_chars"),
}

DEFAULT_GENOME: dict[str, Any] = {
    "arm_kind": "freeform_single",
    "generator_model": "",  # filled from the live roster at experiment start
    "verifier_model": None,
    "k": 3,
    "per_call_tokens": 6000,
    "window_chars": 11000,
    "extra_instruction": "",
    "notes": "seed",
}


@dataclass(frozen=True)
class GenomeCheck:
    executable: bool
    reasons: tuple[str, ...] = ()
    executed_fields: tuple[str, ...] = ()
    ignored_fields: tuple[str, ...] = ()


def check_genome(genome: Any) -> GenomeCheck:
    """Membrane-side executability check — NOT a schema gate.

    A genome that fails here is archived as ``blocked`` (evidence), never an
    error: in explore, malformed children are data about the mutation
    operator, not exceptions.
    """
    if not isinstance(genome, dict):
        return GenomeCheck(False, ("genome_not_a_dict",))
    reasons: list[str] = []
    arm_kind = genome.get("arm_kind")
    if arm_kind not in ARM_KINDS:
        reasons.append(f"unknown_arm_kind:{arm_kind}")
    generator = genome.get("generator_model")
    if not isinstance(generator, str) or not generator.strip():
        reasons.append("missing_generator_model")
    if arm_kind in ("verify_chain", "mixed_moa"):
        verifier = genome.get("verifier_model")
        if not isinstance(verifier, str) or not verifier.strip():
            reasons.append("missing_verifier_model")
    if arm_kind == "self_moa":
        k = genome.get("k")
        if not isinstance(k, int) or not 1 <= k <= 8:
            reasons.append(f"k_out_of_range:{k!r}")
    for gene, lo, hi in (("per_call_tokens", 256, 32768), ("window_chars", 1000, 200000)):
        value = genome.get(gene, DEFAULT_GENOME[gene])
        if not isinstance(value, int) or not lo <= value <= hi:
            reasons.append(f"{gene}_out_of_range:{value!r}")
    if reasons:
        return GenomeCheck(False, tuple(reasons))
    executed = EXECUTED_FIELDS[arm_kind]
    ignored = tuple(sorted(set(genome) - set(executed) - {"notes"}))
    return GenomeCheck(True, (), executed, ignored)


def merged_with_defaults(genome: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_GENOME)
    merged.update(genome)
    return merged


__all__ = ["ARM_KINDS", "DEFAULT_GENOME", "EXECUTED_FIELDS", "GenomeCheck", "check_genome", "merged_with_defaults"]
