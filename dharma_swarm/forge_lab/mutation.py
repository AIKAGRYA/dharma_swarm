"""Mutation operators — pluggable, wild-first, network-injectable.

``llm_propose_genome`` is the primary operator (Sakana-style: the frontier
model sees the parent, its failures, and archive context, and proposes an
ARBITRARY genome dict — including free-form ``extra_instruction`` text and
novel keys, which are preserved as compost). ``parametric_mutation`` is one
operator among several and the deterministic no-network operator for tests.

The LLM completion function is injected (``complete_fn(prompt) -> (text,
tokens)``) so this module never talks to the network itself; production wires
``providers.PoolCompletion(model_id).complete``.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

WINDOW_CHOICES = (6000, 11000, 24000)
PER_CALL_CHOICES = (3500, 6000, 16000)

INSTRUCTION_FRAGMENTS = (
    "Think step by step about which file the bug lives in before writing the diff.",
    "Write the minimal patch: change as few lines as possible.",
    "First restate the failing behavior in one sentence, then fix it.",
    "Consider edge cases around empty input and unicode before finalizing.",
    "Re-read the test expectations carefully; match exact expected strings.",
)


@dataclass(frozen=True)
class MutationResult:
    genome: dict[str, Any] | None
    operator: str
    notes: str = ""
    raw_output: str = ""
    tokens_used: int = 0
    parse_issues: tuple[str, ...] = field(default=())


def parametric_mutation(parent: dict[str, Any], *, rng: random.Random) -> MutationResult:
    """1-2 atomic gene edits from an enumerable registry (deterministic under seed)."""
    child = dict(parent)
    ops: list[tuple[str, Callable[[], None]]] = [
        ("set_window_chars", lambda: child.update(window_chars=rng.choice(WINDOW_CHOICES))),
        ("set_per_call_tokens", lambda: child.update(per_call_tokens=rng.choice(PER_CALL_CHOICES))),
        ("set_k", lambda: child.update(k=rng.randint(1, 5))),
        (
            "append_instruction",
            lambda: child.update(
                extra_instruction=(str(child.get("extra_instruction") or "") + " " + rng.choice(INSTRUCTION_FRAGMENTS)).strip()
            ),
        ),
        (
            "swap_arm_kind",
            lambda: child.update(
                arm_kind=rng.choice(["freeform_single", "self_moa", "verify_chain"])
            ),
        ),
    ]
    chosen = rng.sample(ops, k=rng.choice((1, 2)))
    for _, apply in chosen:
        apply()
    names = ",".join(name for name, _ in chosen)
    child["notes"] = f"parametric:{names}"
    return MutationResult(genome=child, operator="parametric", notes=names)


def _extract_json_object(text: str) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Tolerant extraction: first balanced top-level {...} that parses."""
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blob = text[start : i + 1]
                    try:
                        parsed = json.loads(blob)
                    except json.JSONDecodeError as exc:
                        return None, (f"json_decode_error:{exc.msg}",)
                    if isinstance(parsed, dict):
                        return parsed, ()
                    return None, ("top_level_not_an_object",)
        start = text.find("{", start + 1)
    return None, ("no_json_object_found",)


def _mutation_prompt(
    parent: dict[str, Any],
    failures: Sequence[dict[str, Any]],
    archive_context: Sequence[dict[str, Any]],
    second_parent: dict[str, Any] | None = None,
) -> str:
    role = (
        "You are the MUTATION OPERATOR of an evolutionary search over coding-agent "
        "scaffolds. You receive a parent genome, the tasks it FAILED, and context "
        "from the archive of prior candidates. Propose ONE child genome as a single "
        "JSON object — nothing else in your reply.\n\n"
        "Be genuinely creative: the 'extra_instruction' gene is FREE-FORM text "
        "injected into the coding agent's repair prompt — rewrite it boldly based "
        "on the failure evidence. You may also invent additional keys; unknown keys "
        "are preserved for future operators.\n\n"
        "Executable genes (children outside these still get archived, but cannot "
        "be graded today):\n"
        '  arm_kind: one of "freeform_single" | "self_moa" | "verify_chain" | "mixed_moa"\n'
        "  generator_model / verifier_model: keep the parent's values unless you have a reason\n"
        "  k: 1..8 (self_moa only) · per_call_tokens: 256..32768 · window_chars: 1000..200000\n"
        "  extra_instruction: any text (the wild gene)\n"
        '  notes: one line explaining WHY this mutation, given the failures\n'
    )
    parts = [role, "PARENT GENOME:\n" + json.dumps(parent, indent=2, default=str)]
    if second_parent is not None:
        parts.append(
            "SECOND PARENT (crossover — synthesize the strengths of both):\n"
            + json.dumps(second_parent, indent=2, default=str)
        )
    if failures:
        parts.append("PARENT'S FAILURES:\n" + json.dumps(list(failures)[:8], indent=2, default=str))
    if archive_context:
        parts.append(
            "ARCHIVE CONTEXT (other candidates, pass rates — decorrelate from what already failed):\n"
            + json.dumps(list(archive_context)[:6], indent=2, default=str)
        )
    parts.append("Reply with the child genome JSON object only.")
    return "\n\n".join(parts)


def llm_propose_genome(
    parent: dict[str, Any],
    *,
    complete_fn: Callable[[str], tuple[str, int]],
    failures: Sequence[dict[str, Any]] = (),
    archive_context: Sequence[dict[str, Any]] = (),
    second_parent: dict[str, Any] | None = None,
) -> MutationResult:
    operator = "llm_crossover" if second_parent is not None else "llm_propose"
    prompt = _mutation_prompt(parent, failures, archive_context, second_parent)
    try:
        text, tokens = complete_fn(prompt)
    except Exception as exc:  # provider errors are evidence, not crashes
        return MutationResult(None, operator, notes=f"provider_error:{exc}", parse_issues=("provider_error",))
    genome, issues = _extract_json_object(text or "")
    notes = ""
    if isinstance(genome, dict):
        notes = str(genome.get("notes") or "")
    return MutationResult(
        genome=genome,
        operator=operator,
        notes=notes,
        raw_output=(text or "")[:20000],
        tokens_used=tokens,
        parse_issues=issues,
    )


__all__ = [
    "MutationResult",
    "parametric_mutation",
    "llm_propose_genome",
    "WINDOW_CHOICES",
    "PER_CALL_CHOICES",
]
