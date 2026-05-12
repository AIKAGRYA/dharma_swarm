"""KnowledgeOps: read-only semantic lifecycle projections for Dharma Swarm.

This package intentionally starts as a projection layer.  It reads existing
docs, wiki atoms, runtime maps, and code surfaces, then emits nodes, edges, and
context artifacts.  It does not mutate canonical docs, ontology rows, runtime
state, cron jobs, or archive paths.
"""

from dharma_swarm.knowledge_ops.extractor import KnowledgeOpsExtractor
from dharma_swarm.knowledge_ops.memory_intake import (
    MemoryEvidenceReview,
    MemoryKernelIntake,
    MemoryKernelIntakeConfig,
    memory_atoms_to_snapshot,
    merge_snapshots,
    render_memory_evidence_review_markdown,
    review_memory_atoms,
)
from dharma_swarm.knowledge_ops.memory_conflict_review import (
    MemoryConflictProjectionReview,
    MemoryPromotionCandidate,
    MemoryReviewFinding,
    MemoryReviewSeverity,
    render_memory_conflict_review_markdown,
    review_memory_conflicts,
)
from dharma_swarm.knowledge_ops.memory_decision_ledger import (
    MemoryPromotionDecision,
    MemoryPromotionDecisionKind,
    MemoryPromotionDecisionLedger,
    MemoryPromotionDecisionReview,
    MemoryPromotionDecisionValidity,
    build_memory_decision_ledger,
    load_memory_promotion_decisions,
    render_memory_decision_ledger_markdown,
)
from dharma_swarm.knowledge_ops.memory_promotion_queue import (
    MemoryPromotionGate,
    MemoryPromotionProposal,
    MemoryPromotionProposalQueue,
    MemoryPromotionQueueStatus,
    build_memory_promotion_queue,
    render_memory_promotion_queue_markdown,
)
from dharma_swarm.knowledge_ops.schema import (
    EdgeKind,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeOpsSnapshot,
    KnowledgeOpsMode,
    LifecycleStatus,
    NodeKind,
    SourceRef,
)

__all__ = [
    "EdgeKind",
    "KnowledgeEdge",
    "KnowledgeNode",
    "KnowledgeOpsExtractor",
    "KnowledgeOpsMode",
    "KnowledgeOpsSnapshot",
    "LifecycleStatus",
    "MemoryEvidenceReview",
    "MemoryConflictProjectionReview",
    "MemoryKernelIntake",
    "MemoryKernelIntakeConfig",
    "MemoryPromotionGate",
    "MemoryPromotionCandidate",
    "MemoryPromotionDecision",
    "MemoryPromotionDecisionKind",
    "MemoryPromotionDecisionLedger",
    "MemoryPromotionDecisionReview",
    "MemoryPromotionDecisionValidity",
    "MemoryPromotionProposal",
    "MemoryPromotionProposalQueue",
    "MemoryPromotionQueueStatus",
    "MemoryReviewFinding",
    "MemoryReviewSeverity",
    "NodeKind",
    "SourceRef",
    "build_memory_decision_ledger",
    "build_memory_promotion_queue",
    "load_memory_promotion_decisions",
    "memory_atoms_to_snapshot",
    "merge_snapshots",
    "render_memory_conflict_review_markdown",
    "render_memory_decision_ledger_markdown",
    "render_memory_evidence_review_markdown",
    "render_memory_promotion_queue_markdown",
    "review_memory_conflicts",
    "review_memory_atoms",
]
