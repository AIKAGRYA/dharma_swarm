"""Pluggable free-form mutation operators for Forge Lab."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class MutationResult:
    genome: dict[str, Any]
    operator: str
    blocked: bool = False
    blocker: str = ""
    raw_output: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)


LLMProposer = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def seed_genome() -> dict[str, Any]:
    return {
        "schema": "forge_lab.scaffold_genome.freeform.v0",
        "strategy": "baseline_empty_patch",
        "k_candidates": 1,
        "verify_gate": True,
        "window_chars": 6000,
        "per_call_tokens": 3500,
        "prompt_template_id": "baseline_v0",
        "patches": {},
        "notes": ["seed baseline; no positive claim"],
    }


def parametric_mutation(parent: dict[str, Any], *, rng: random.Random) -> MutationResult:
    child = copy.deepcopy(parent)
    child.setdefault("notes", [])
    ops = [
        "set_k_candidates",
        "toggle_verify_gate",
        "set_window_chars",
        "set_per_call_tokens",
        "swap_prompt_template",
        "append_strategy_note",
    ]
    chosen = rng.sample(ops, k=rng.randint(1, min(3, len(ops))))
    for op in chosen:
        if op == "set_k_candidates":
            child["k_candidates"] = rng.randint(1, 5)
        elif op == "toggle_verify_gate":
            child["verify_gate"] = not bool(child.get("verify_gate", True))
        elif op == "set_window_chars":
            child["window_chars"] = rng.choice([6000, 11000, 24000])
        elif op == "set_per_call_tokens":
            child["per_call_tokens"] = rng.choice([3500, 6000, 16000])
        elif op == "swap_prompt_template":
            child["prompt_template_id"] = rng.choice(
                ["baseline_v0", "repair_first_v1", "failure_transcript_v1", "minimal_diff_v1"]
            )
        elif op == "append_strategy_note":
            child["notes"] = [*list(child.get("notes") or []), f"mutation_note_{rng.randint(1, 999)}"]
    child["mutation_ops"] = chosen
    return MutationResult(genome=child, operator="parametric", artifacts={"ops": chosen})


def llm_propose_genome(
    parent: dict[str, Any],
    *,
    proposer: LLMProposer | None,
    failure_transcripts: list[dict[str, Any]] | None = None,
    archive_context: list[dict[str, Any]] | None = None,
) -> MutationResult:
    """Frontier-model seam.

    No provider call is made here unless the caller supplies a proposer.  This
    keeps EXPLORE wild without silently spending money or pretending a mock LLM
    is a frontier model.
    """

    if proposer is None:
        return MutationResult(
            genome=dict(parent),
            operator="llm_propose_genome",
            blocked=True,
            blocker="llm_proposer_unavailable",
        )
    context = {
        "failure_transcripts": failure_transcripts or [],
        "archive_context": archive_context or [],
    }
    try:
        proposed = proposer(copy.deepcopy(parent), context)
    except Exception as exc:  # noqa: BLE001 - malformed/exhausted is EVIDENCE, not a crash.
        blocker = f"{type(exc).__name__}:{str(exc)[:200]}"
        return MutationResult(
            genome=dict(parent),
            operator="llm_propose_genome",
            blocked=True,
            blocker=blocker,
            raw_output=str(exc)[:4000],
        )
    if not isinstance(proposed, dict):
        return MutationResult(
            genome={"raw_proposal": repr(proposed)},
            operator="llm_propose_genome",
            blocked=True,
            blocker="llm_proposer_returned_non_dict",
            raw_output=repr(proposed),
        )
    return MutationResult(genome=proposed, operator="llm_propose_genome", raw_output=repr(proposed)[:4000])


def llm_crossover(
    parent: dict[str, Any],
    *,
    second_parent: dict[str, Any] | None,
) -> MutationResult:
    if second_parent is None:
        return MutationResult(
            genome=dict(parent),
            operator="llm_crossover",
            blocked=True,
            blocker="second_parent_unavailable",
        )
    child = copy.deepcopy(parent)
    for key, value in second_parent.items():
        if key not in child or key in {"prompt_template_id", "notes", "patches"}:
            child[key] = copy.deepcopy(value)
    child.setdefault("notes", [])
    child["notes"] = [*list(child["notes"]), "crossover_without_provider"]
    return MutationResult(genome=child, operator="llm_crossover")


def mutate_genome(
    parent: dict[str, Any],
    *,
    rng: random.Random,
    operators: list[str] | None = None,
    proposer: LLMProposer | None = None,
    second_parent: dict[str, Any] | None = None,
    failure_transcripts: list[dict[str, Any]] | None = None,
    archive_context: list[dict[str, Any]] | None = None,
) -> MutationResult:
    registry = {
        "parametric": lambda: parametric_mutation(parent, rng=rng),
        "llm_propose_genome": lambda: llm_propose_genome(
            parent,
            proposer=proposer,
            failure_transcripts=failure_transcripts,
            archive_context=archive_context,
        ),
        "llm_crossover": lambda: llm_crossover(parent, second_parent=second_parent),
    }
    names = operators or ["parametric"]
    unknown = [name for name in names if name not in registry]
    if unknown:
        return MutationResult(
            genome=dict(parent),
            operator="unknown",
            blocked=True,
            blocker=f"unknown_operators:{','.join(sorted(unknown))}",
        )
    return registry[rng.choice(names)]()


# WILD-first default operator ladder. The handoff mandate is explicit: the LLM
# proposer is the primary EXPLORE operator, with parametric demoted to one
# operator among several. ``default_operators`` therefore leads with
# ``llm_propose_genome`` whenever a proposer is available, and only falls back to
# the non-LLM operators when no frontier slot is dispatchable.
WILD_OPERATORS: tuple[str, ...] = ("llm_propose_genome", "llm_crossover", "parametric")
FALLBACK_OPERATORS: tuple[str, ...] = ("parametric",)


def default_operators(
    *,
    proposer: LLMProposer | None,
    second_parent: dict[str, Any] | None = None,
) -> list[str]:
    """Return the operator ladder for a child slot.

    Wild-first when a live proposer exists; otherwise the honest non-LLM
    fallback so an offline/CI run never fakes a frontier call.
    """
    if proposer is None:
        return list(FALLBACK_OPERATORS)
    ops = ["llm_propose_genome"]
    if second_parent is not None:
        ops.append("llm_crossover")
    ops.append("parametric")
    return ops
