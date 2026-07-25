"""Tier-C gate-compliant proposal helpers for evolution tests.

Why this module exists
----------------------
WS4 (``dharma_swarm/evolution.py`` ~L1543) makes a self-mod proposal a HARD
REJECT whenever the telos gatekeeper returns ``REVIEW`` — and a ``REVIEW`` is
produced whenever *any* Tier-C advisory gate flags. A proposal must therefore
clear the WHOLE Tier-C battery at once. Evolution tests written before WS4 used
terse descriptions and so are rejected for "low epistemological diversity" or
"no counterarguments", which has nothing to do with what they actually assert
(fitness / archival / selection mechanics).

Field map — which gate reads which field
----------------------------------------
Verified with ``scripts/diagnostics/proposal_gate_probe.py`` (run it to re-map
if the gates change):

==============  ===============  ==================================================
Gate            Reads            Needs
==============  ===============  ==================================================
ANEKANTA /      description       >=1 keyword from each of the three epistemological
SVABHAAVA       + diff            frames (mechanistic / phenomenological / systems)
STEELMAN        diff              a counterargument marker (however / risk: /
                                  alternatively ...) when the description carries a
                                  mutation word and the diff is non-empty
DOGMA_DRIFT     diff              evidence markers (tested / measured / verified /
                                  result:) if confidence markers are present
VYAVASTHIT      description       must NOT contain forcing words
REVERSIBILITY   description       irreversible words downgrade to WARN
==============  ===============  ==================================================

Use :func:`gate_compliant_description` for the proposal text and
:func:`tier_c_diff` for the diff. See
``docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md`` for the full contract.
This module is self-validated by ``tests/test_evolution_gate_helpers.py`` — if a
gate changes under it, that test fails loudly instead of silently rotting.
"""
from __future__ import annotations

# Spans the three anekanta frames (mechanistic: computation/layer/mechanism;
# phenomenological: observer/first-person/awareness; systems: feedback/
# adaptation/resilience/network). Carries no forcing or irreversible words.
_FRAMES_CLAUSE = (
    " — adjusts the computation-layer mechanism while keeping the observer's "
    "first-person awareness of the behaviour and preserving system-level "
    "feedback, adaptation, and resilience across the network"
)

# Counterargument (STEELMAN) + evidence (DOGMA_DRIFT) markers. Lives in the diff
# because those gates scan the diff (content), not the description.
_STEELMAN_EVIDENCE_NOTE = (
    "+# however, risk: a regression is possible; tested and measured, "
    "verified by the results above"
)


def gate_compliant_description(intent: str) -> str:
    """Extend *intent* so the proposal clears ANEKANTA/SVABHAAVA (three frames).

    The caller keeps a readable intent ("Add entropy normalization") and this
    appends a frame-complete clause. Sufficient on its own for proposals with an
    empty diff (STEELMAN is skipped when there is no diff content).
    """
    return f"{intent}{_FRAMES_CLAUSE}"


def tier_c_diff(body: str = "+change") -> str:
    """Return *body* with a steelman+evidence note appended.

    Needed whenever a proposal has a non-empty diff AND a mutation-word
    description, so STEELMAN and DOGMA_DRIFT pass. The note is a diff comment
    line, so it does not change the meaning of *body* for size/efficiency checks.
    """
    return f"{body}\n{_STEELMAN_EVIDENCE_NOTE}"


def gate_compliant_proposal_kwargs(
    *,
    component: str,
    intent: str,
    change_type: str = "mutation",
    diff_body: str = "+change",
) -> dict[str, str]:
    """Return kwargs for ``DarwinEngine.propose`` that clear the Tier-C battery."""
    return {
        "component": component,
        "change_type": change_type,
        "description": gate_compliant_description(intent),
        "diff": tier_c_diff(diff_body),
    }
