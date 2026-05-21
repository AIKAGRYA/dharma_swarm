"""Sakshi — Witness Auditor (Provenance Chain Guardian).

Maintains the complete provenance chain for every state transition.
Not "what changed" (git does that) but "why did it change, who decided,
with what evidence, and was the decision consistent with the governance
constraints active at the time?"

Sakshi (साक्षी) is the witness-consciousness — the observer that doesn't
participate in action but provides the ground of awareness against which
action is evaluated.

Key constraint: Append-only and tamper-evident. Never deletes. Never
modifies past records. The substrate's institutional memory.
"""

from dharma_swarm.sakshi.provenance_log import (
    ProvenanceEntry,
    ProvenanceLog,
)

__all__ = [
    "ProvenanceEntry",
    "ProvenanceLog",
]
