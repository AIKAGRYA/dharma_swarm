"""Frontier genome proposer for Forge Lab's WILD EXPLORE path.

This is the organ the conservative first chassis left dormant: it makes the
``llm_propose_genome`` operator actually *reachable* by the generational loop.

It does NOT invent a parallel provider/policy table. It reuses the canonical
model-grain seam:

* ``forge_v1.canonical.pool_slots`` — the hierarchy-true roster selector.
* ``forge_v1.canonical._provider_for_slot`` — build a live provider from a slot.
* ``forge_v1.canonical._call`` — one call with hard timeout + 429 backoff.
* ``key_oracle.dispatchable_now`` — the honest "what can I dispatch to RIGHT
  NOW" set; if a frontier slot is not dispatchable, we do NOT fake a call.
* ``forge_v2.budget.Budget`` — one shared token/$ cap for the whole experiment.

Sakana-style: the frontier model receives the parent genome, per-task FAILURE
TRANSCRIPTS, and ARCHIVE CONTEXT (mycelial soil), and proposes an ARBITRARY new
genome dict. EXPLORE accepts anything clearing the membrane; malformed output is
returned to the caller as evidence, never silently dropped.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from dharma_swarm.forge_v1.forge_v2.budget import Budget

LLMProposer = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

_GENOME_SYSTEM = (
    "You are evolving a CODING-AGENT SCAFFOLD GENOME for an automated software-"
    "repair lab. A genome is a JSON object describing how the agent attempts a "
    "fix: strategy, prompt_template_id, k_candidates, verify_gate, window_chars, "
    "per_call_tokens, and any extra fields you judge useful. You are NOT writing "
    "a code patch. Propose ONE mutated genome that is meaningfully different from "
    "the parent and likely to solve more tasks. Return ONLY a single JSON object."
)


class ProposerBudgetExhausted(RuntimeError):
    """Raised inside the proposer when the shared budget cap is reached."""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort parse of a single JSON object from model output.

    Tries a raw ``json.loads`` first, then a fenced json block, then the first
    balanced ``{...}`` span. Returns ``None`` when nothing parses.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        try:
            parsed = json.loads(fence.group(1))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass
    depth = 0
    start = -1
    for idx, char in enumerate(raw):
        if char == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    parsed = json.loads(raw[start : idx + 1])
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    start = -1
    return None


def _build_genome_prompt(
    parent: dict[str, Any],
    context: dict[str, Any],
    *,
    max_transcripts: int = 3,
    max_exemplars: int = 3,
) -> str:
    transcripts = list(context.get("failure_transcripts") or [])[:max_transcripts]
    exemplars = list(context.get("archive_context") or [])[:max_exemplars]
    parts = [
        _GENOME_SYSTEM,
        "\nPARENT GENOME:\n" + json.dumps(parent, indent=2, sort_keys=True)[:4000],
    ]
    if transcripts:
        parts.append(
            "\nRECENT FAILURE TRANSCRIPTS (task_id, error/tail — learn from these):\n"
            + json.dumps(transcripts, indent=2, sort_keys=True)[:4000]
        )
    if exemplars:
        parts.append(
            "\nARCHIVE EXEMPLARS (prior genomes as compost/soil — reuse freely):\n"
            + json.dumps(exemplars, indent=2, sort_keys=True)[:4000]
        )
    parts.append("\nReturn ONLY the new genome as one JSON object. No prose.")
    return "\n".join(parts)


def _dispatchable_slots(strategy: str, n: int):
    """Return pool slots whose provider is dispatchable RIGHT NOW.

    Never fakes a route: if the honest dispatchable set does not cover a slot's
    provider, that slot is dropped. Returns ``[]`` when nothing is reachable.
    """
    from dharma_swarm.forge_v1.canonical import pool_slots
    from dharma_swarm.key_oracle import dispatchable_now

    live = dispatchable_now()
    slots = []
    seen: set[str] = set()
    for slot in pool_slots(n=n, strategy=strategy):
        if slot.model_id in seen:
            continue
        seen.add(slot.model_id)
        if slot.provider.value in live:
            slots.append(slot)
    return slots


class FrontierGenomeProposer:
    """Callable proposer that turns parent+context into a new genome dict.

    Constructed only when at least one frontier slot is dispatchable. Shares a
    single :class:`Budget` across the whole experiment; raises
    :class:`ProposerBudgetExhausted` once the cap is crossed so the mutation
    layer can record ``budget_exhausted`` as honest evidence.
    """

    def __init__(
        self,
        *,
        slots,
        budget: Budget,
        per_call_tokens: int,
        timeout_s: int,
    ) -> None:
        self._slots = list(slots)
        self.budget = budget
        self.per_call_tokens = int(per_call_tokens)
        self.timeout_s = int(timeout_s)
        self._cursor = 0
        self.calls = 0

    @property
    def slot_ids(self) -> list[str]:
        return [s.model_id for s in self._slots]

    def __call__(self, parent: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        from dharma_swarm.forge_v1.canonical import _call, _provider_for_slot

        if self.budget.invalid or self.budget.remaining() <= 0:
            raise ProposerBudgetExhausted(self.budget.invalid_reason or "token budget exhausted")

        slot = self._slots[self._cursor % len(self._slots)]
        self._cursor += 1
        self.calls += 1
        prompt = _build_genome_prompt(parent, context)
        provider, wire = _provider_for_slot(slot, timeout_s=self.timeout_s)
        text, tokens, _stop = _call(
            provider,
            wire,
            prompt,
            max_tokens=self.per_call_tokens,
            temperature=1.0,
            timeout_s=self.timeout_s,
        )
        # Free/subscription routes accrue shadow $ so "free" is not infinite.
        self.budget.charge("generation", int(tokens), is_free_route=True)
        proposed = _extract_json_object(text)
        if proposed is None:
            # Surfaced to the mutation layer as a malformed (blocked) child.
            raise ValueError(f"proposer returned unparseable genome from {slot.model_id}")
        proposed.setdefault("notes", [])
        if isinstance(proposed["notes"], list):
            proposed["notes"].append(f"llm_propose_genome:{slot.model_id}")
        proposed["_operator_model"] = slot.model_id
        proposed["_operator_provider"] = slot.provider.value
        return proposed


def build_frontier_proposer(
    *,
    allow_model_calls: bool,
    strategy: str = "explore",
    roster_n: int = 8,
    per_call_tokens: int = 3500,
    timeout_s: int = 60,
    token_budget: int = 120_000,
    max_usd: float = 0.0,
) -> tuple[LLMProposer | None, dict[str, Any]]:
    """Build the wild proposer, or return ``(None, why)`` honestly.

    Returns ``(None, report)`` when model calls are disabled or no frontier slot
    is dispatchable right now — so the loop falls back to non-LLM operators
    without ever faking a frontier call. The report is recorded in the manifest.
    """
    report: dict[str, Any] = {
        "allow_model_calls": bool(allow_model_calls),
        "strategy": strategy,
        "roster_n": roster_n,
        "token_budget": token_budget,
        "max_usd": max_usd,
    }
    if not allow_model_calls:
        report["proposer"] = "disabled"
        report["reason"] = "allow_model_calls=False (offline/deterministic run)"
        return None, report
    try:
        slots = _dispatchable_slots(strategy, roster_n)
    except Exception as exc:  # noqa: BLE001 - report, never crash the run.
        report["proposer"] = "unavailable"
        report["reason"] = f"roster_error:{type(exc).__name__}:{exc}"
        return None, report
    if not slots:
        report["proposer"] = "unavailable"
        report["reason"] = "no_dispatchable_frontier_slot"
        return None, report
    budget = Budget(cap_tokens=int(token_budget), cap_usd=(max_usd or None))
    proposer = FrontierGenomeProposer(
        slots=slots,
        budget=budget,
        per_call_tokens=per_call_tokens,
        timeout_s=timeout_s,
    )
    report["proposer"] = "active"
    report["dispatchable_slots"] = proposer.slot_ids
    return proposer, report
