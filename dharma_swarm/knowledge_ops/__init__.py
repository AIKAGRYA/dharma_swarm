"""KnowledgeOps: read-only semantic lifecycle projections for Dharma Swarm.

This package intentionally starts as a projection layer.  It reads existing
docs, wiki atoms, runtime maps, and code surfaces, then emits nodes, edges, and
context artifacts.  It does not mutate canonical docs, ontology rows, runtime
state, cron jobs, or archive paths.
"""

from dharma_swarm.knowledge_ops.extractor import KnowledgeOpsExtractor
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
    "NodeKind",
    "SourceRef",
]
