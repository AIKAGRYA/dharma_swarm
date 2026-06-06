"""Automatic run-level LEARN executor (the 'Living' metabolism step).

Complement to the agent-invoked ``memory_write`` tool. Where ``memory_write`` is
an explicit tool call inside a wake, ``commit_learning`` is the automatic
adapter the kernel runs at the END of every governed run: given a
completed/review run whose ``MemoryPlan.proposed_learning_delta`` is non-empty
and whose target namespaces are declared in ``write_namespaces``, it appends a
bounded learning record THROUGH the existing ``KernelLessonStore.append_lesson``
hash-chained ledger. It does NOT create a second ledger primitive, mutate the
kernel run-state, or import a provider runtime. It is a pure adapter over the
frozen lesson-store API so an agent accumulates lessons across wakes — it LEARNS.

Bounded by construction: the delta is truncated to ``LEARNING_DELTA_CAP`` chars,
an identical (run_id, namespace, truncated-delta) is deduped to a single row,
and a route to a namespace that is not in ``write_namespaces`` is refused with no
row appended (and the caller is told to audit the refusal).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.operator_core.governed_work_admission import GovernedWorkAdmission
from dharma_swarm.operator_core.living_agent_kernel import (
    AgentRunEnvelope,
    KernelRunStatus,
)
from dharma_swarm.operator_core.living_agent_kernel_lessons import (
    EmptyLessonDeltaError,
    KernelLessonReceipt,
    KernelLessonStore,
)
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash

LEARNING_DELTA_CAP = 4000
LEARNABLE_STATUSES: frozenset[KernelRunStatus] = frozenset({"completed", "review"})


class LearningRefusal(BaseModel):
    """A refused auto-learn attempt: an audit fact, never a silent drop."""

    namespace: str
    reason: str
    delta_hash: str = ""
    detail: str = ""


class LearningOutcome(BaseModel):
    """Result of an automatic LEARN pass over one run.

    ``receipt`` is set when a real durable record was appended; ``refusals``
    records every routed namespace that was refused so the kernel can emit an
    audit event recording the refusal (no learning on un-admitted or
    out-of-scope work).
    """

    receipt: KernelLessonReceipt | None = None
    refusals: list[LearningRefusal] = Field(default_factory=list)
    skipped_reason: str = ""

    @property
    def wrote(self) -> bool:
        return self.receipt is not None

    def event_ref(self) -> dict[str, Any] | None:
        if self.receipt is None:
            return None
        return {
            "kind": "kernel_learning",
            "namespace": self.receipt.namespace,
            "record_hash": self.receipt.entry_hash,
            "delta_hash": self.receipt.delta_hash,
            "ledger_sequence": self.receipt.ledger_sequence,
            "run_id": self.receipt.run_id,
        }


def _target_namespaces(envelope: AgentRunEnvelope) -> list[tuple[str, bool]]:
    declared = [str(ns).strip() for ns in envelope.memory.write_namespaces if str(ns).strip()]
    metadata = envelope.memory.metadata or {}
    routed = metadata.get("learning_namespaces")
    if isinstance(routed, (list, tuple)):
        candidates = [str(ns).strip() for ns in routed if str(ns).strip()]
    elif isinstance(routed, str) and routed.strip():
        candidates = [routed.strip()]
    else:
        # Default route: the agent's own declared lessons namespace(s).
        candidates = list(declared)
    declared_set = set(declared)
    return [(ns, ns in declared_set) for ns in candidates]


def _bounded_delta(raw: str) -> str:
    text = str(raw or "")
    if len(text) > LEARNING_DELTA_CAP:
        return text[:LEARNING_DELTA_CAP]
    return text


def commit_learning(
    store: KernelLessonStore,
    envelope: AgentRunEnvelope,
    admission: GovernedWorkAdmission,
    status: KernelRunStatus,
) -> LearningOutcome:
    """Consume ``proposed_learning_delta`` into the lessons ledger, once.

    Returns ``LearningOutcome`` with ``receipt`` set only when a durable record
    was appended. Returns no receipt (and writes nothing) unless ALL hold:
      * ``status`` in {completed, review}
      * the admission permitted the run (``decision != 'block'``)
      * ``proposed_learning_delta`` is non-empty after stripping
      * the routed namespace is declared in ``write_namespaces``
    A routed namespace not in ``write_namespaces`` is refused (recorded in
    ``refusals``) with no row appended. Identical (run_id, namespace, delta) is
    deduped to a single row.
    """
    if status not in LEARNABLE_STATUSES:
        return LearningOutcome(skipped_reason=f"status_not_learnable:{status}")
    if admission.decision == "block":
        return LearningOutcome(skipped_reason="admission_blocked")

    raw_delta = str(envelope.memory.proposed_learning_delta or "").strip()
    if not raw_delta:
        return LearningOutcome(skipped_reason="empty_learning_delta")

    delta = _bounded_delta(raw_delta).strip()
    if not delta:
        return LearningOutcome(skipped_reason="empty_after_bounding")
    delta_hash = stable_payload_hash(delta)

    refusals: list[LearningRefusal] = []
    receipt: KernelLessonReceipt | None = None
    for namespace, declared in _target_namespaces(envelope):
        if not declared:
            refusals.append(
                LearningRefusal(
                    namespace=namespace,
                    reason="namespace_not_in_write_namespaces",
                    delta_hash=delta_hash,
                )
            )
            continue
        if receipt is not None:
            # One durable learning record per run; extra declared routes noop.
            continue
        if _is_duplicate(store, namespace, envelope.run_id, delta_hash):
            return LearningOutcome(skipped_reason="duplicate_delta", refusals=refusals)
        try:
            receipt = store.append_lesson(
                envelope.agent_uid,
                namespace,
                delta,
                run_id=envelope.run_id,
                provenance={
                    "executor": "automatic_learn",
                    "source": envelope.trigger.source,
                    "mission_id": envelope.trigger.mission_id,
                    "task_id": envelope.trigger.task_id,
                    "correlation_id": envelope.trigger.correlation_id,
                    "parent_run_id": envelope.trigger.parent_run_id,
                    "truncated": len(raw_delta) > LEARNING_DELTA_CAP,
                },
            )
        except EmptyLessonDeltaError:
            return LearningOutcome(skipped_reason="empty_learning_delta", refusals=refusals)
        except ValueError as exc:
            refusals.append(
                LearningRefusal(
                    namespace=namespace,
                    reason="namespace_unsafe",
                    delta_hash=delta_hash,
                    detail=f"{type(exc).__name__}:{exc}",
                )
            )

    return LearningOutcome(receipt=receipt, refusals=refusals)


def _is_duplicate(
    store: KernelLessonStore,
    namespace: str,
    run_id: str,
    delta_hash: str,
) -> bool:
    for existing in store.lessons(namespace):
        if existing.run_id == run_id and existing.delta_hash == delta_hash:
            return True
    return False
