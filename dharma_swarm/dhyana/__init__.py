"""Dhyana — Meditative Reconciler (System 4 Observer).

Continuously re-evaluates whether the system's model of itself is still
accurate. Not a builder, not a fixer — an observer that sits above the
control surface and asks: "Is our declared intent still coherent with
where we're actually going?"

In Beer's VSM: System 4 — the "outside and future" function.
System 3 (guardian crew) monitors internal stability.
System 4 monitors whether the internal model matches external reality.

Key constraint: Dhyana OBSERVES and RECOMMENDS. It does not mutate.
Its output flows to the operator (via control surface) or to the agent
handoff prompt generator. This preserves the noticer/doer boundary.
"""

from dharma_swarm.dhyana.drift_triage import (
    DriftTriageEntry,
    triage_drifted_zones,
)

__all__ = [
    "DriftTriageEntry",
    "triage_drifted_zones",
]
