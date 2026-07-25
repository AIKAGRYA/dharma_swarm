"""Bounded reflective reroute state node for Telos witness recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from dharma_swarm.models import GateCheckResult, GateDecision, GateResult


class _Gatekeeper(Protocol):
    def check(
        self,
        action: str,
        content: str = "",
        tool_name: str = "",
        trust_mode: str | None = None,
        think_phase: str | None = None,
        reflection: str = "",
    ) -> GateCheckResult: ...


@dataclass
class ReflectiveGateOutcome:
    """Result bundle for reflective reroute gate checks."""

    result: GateCheckResult
    attempts: int = 0
    reflection: str = ""
    suggestions: list[str] = field(default_factory=list)


@dataclass
class ReflectiveRerouteNodeState:
    """Explicit bounded state node for reflective gate rerouting."""

    action: str
    content: str = ""
    tool_name: str = ""
    trust_mode: str | None = None
    think_phase: str | None = None
    reflection: str = ""
    max_attempts: int = 2
    spec_ref: str | None = None
    requirement_refs: list[str] = field(default_factory=list)
    attempts: int = 0
    suggestions: list[str] = field(default_factory=list)
    result: GateCheckResult | None = None
    done: bool = False

    @property
    def phase_key(self) -> str:
        return (self.think_phase or "").strip().lower()


def run_reflective_reroute(
    gatekeeper: _Gatekeeper,
    mandatory_phases: set[str],
    *,
    action: str,
    content: str = "",
    tool_name: str = "",
    trust_mode: str | None = None,
    think_phase: str | None = None,
    reflection: str = "",
    max_reroutes: int = 2,
    spec_ref: str | None = None,
    requirement_refs: list[str] | None = None,
) -> ReflectiveGateOutcome:
    """Run gate checks with explicit bounded witness recovery state."""

    state = ReflectiveRerouteNodeState(
        action=action,
        content=content,
        tool_name=tool_name,
        trust_mode=trust_mode,
        think_phase=think_phase,
        reflection=(reflection or "").strip(),
        max_attempts=max(0, int(max_reroutes)),
        spec_ref=spec_ref,
        requirement_refs=list(requirement_refs or []),
    )

    for _ in range(state.max_attempts + 1):
        state = advance_reflective_reroute_node(
            state,
            gatekeeper=gatekeeper,
            mandatory_phases=mandatory_phases,
        )
        if state.done:
            break

    if state.result is None:
        state = advance_reflective_reroute_node(
            state,
            gatekeeper=gatekeeper,
            mandatory_phases=mandatory_phases,
        )

    return ReflectiveGateOutcome(
        result=state.result,
        attempts=state.attempts,
        reflection=state.reflection,
        suggestions=state.suggestions,
    )


def advance_reflective_reroute_node(
    state: ReflectiveRerouteNodeState,
    *,
    gatekeeper: _Gatekeeper,
    mandatory_phases: set[str],
) -> ReflectiveRerouteNodeState:
    """Run one bounded reflective reroute transition."""

    result = gatekeeper.check(
        action=state.action,
        content=state.content,
        tool_name=state.tool_name,
        trust_mode=state.trust_mode,
        think_phase=state.think_phase,
        reflection=state.reflection,
    )
    state.result = result

    witness_result = result.gate_results.get("WITNESS")
    mandatory_witness_block = (
        result.decision == GateDecision.BLOCK
        and witness_result is not None
        and witness_result[0] == GateResult.FAIL
        and state.phase_key in mandatory_phases
    )
    if not mandatory_witness_block or state.attempts >= state.max_attempts:
        state.done = True
        return state

    state.attempts += 1
    state.suggestions = reflective_lenses(
        spec_ref=state.spec_ref,
        requirement_refs=state.requirement_refs,
    )
    scaffold = build_reflection_scaffold(
        attempt=state.attempts,
        max_attempts=state.max_attempts,
        reason=result.reason,
        phase=state.phase_key or "unknown",
        action=state.action,
        spec_ref=state.spec_ref,
        requirement_refs=state.requirement_refs,
    )
    state.reflection = (
        f"{state.reflection}\n\n{scaffold}".strip()
        if state.reflection
        else scaffold
    )
    return state


def reflective_lenses(
    *,
    spec_ref: str | None = None,
    requirement_refs: list[str] | None = None,
) -> list[str]:
    requirements = ", ".join(requirement_refs or []) or "none"
    trace = spec_ref or "unlinked"
    return [
        (
            "Risk lens: What could break, who/what could be harmed, and what "
            "smallest reversible step reduces blast radius?"
        ),
        (
            "Counterfactual lens: If this fails, what early signal will detect "
            "it and what rollback is immediate?"
        ),
        (
            "Plurality lens: What are two alternative strategies and why is this "
            "one preferred now?"
        ),
        (
            "Evidence lens: Which concrete spec/requirement does this satisfy "
            f"(spec={trace}, reqs={requirements})?"
        ),
        (
            "Integrity lens: Which assumption is uncertain and how will it be "
            "validated before completion?"
        ),
    ]


def build_reflection_scaffold(
    *,
    attempt: int,
    max_attempts: int,
    reason: str,
    phase: str,
    action: str,
    spec_ref: str | None = None,
    requirement_refs: list[str] | None = None,
) -> str:
    requirements = ", ".join(requirement_refs or []) or "none"
    trace = spec_ref or "unlinked"
    return (
        f"Reflective reroute attempt {attempt}/{max_attempts}. "
        f"Phase: {phase}. Trigger: {reason}\n"
        f"Action intent: {action}\n"
        f"Spec trace: {trace}\n"
        f"Requirement refs: {requirements}\n"
        "RISK: Bound to smallest reversible step.\n"
        "ROLLBACK: State exact undo path before continuing.\n"
        "ALTERNATIVES: Name two alternatives and why deferred.\n"
        "EVIDENCE: Define pass/fail signal for this step.\n"
        "UNCERTAINTY: Name one unknown + check."
    )
