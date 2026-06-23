"""Auditable evolutionary orchestration substrate.

The keystone of the Dharma Swarm orchestration substrate (spec
``docs/architecture/LEARNED_AUDITABLE_ORCHESTRATOR_SPEC.md``). Zero-GPU,
zero-training: a heuristic orchestrator emits ``OrchestrationGenome``s, a frozen
hermetic arena scores them against a best-single gate at budget parity, and a
MAP-Elites archive promotes winners — all from a recorded fixture pool with a
deterministic scorer as the sole correctness authority.
"""

from dharma_swarm.coordination.genome import OrchestrationGenome

__all__ = ["OrchestrationGenome"]
