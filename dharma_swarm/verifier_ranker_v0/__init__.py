"""Starter package for DharmaVerifier-Ranker v0.

This package is advisory and offline-only. It provides schema, redaction,
inventory, and verification helpers for preparing a training-ready verifier /
ranker package without enabling autonomous dispatch or runtime authority.
"""

from dharma_swarm.verifier_ranker_v0.redaction import (
    RedactionFinding,
    RedactionResult,
    redact_record,
    redact_text,
)
from dharma_swarm.verifier_ranker_v0.schemas import (
    GRAPH_RECORD_TYPES,
    GRAPH_SCHEMA_VERSION,
    MODEL_OUTPUT_SCHEMA,
    MODEL_OUTPUT_SCHEMA_VERSION,
    SEMANTIC_RECEIPT_GRAPH_SCHEMA,
)

__all__ = [
    "GRAPH_RECORD_TYPES",
    "GRAPH_SCHEMA_VERSION",
    "MODEL_OUTPUT_SCHEMA",
    "MODEL_OUTPUT_SCHEMA_VERSION",
    "RedactionFinding",
    "RedactionResult",
    "SEMANTIC_RECEIPT_GRAPH_SCHEMA",
    "redact_record",
    "redact_text",
]
