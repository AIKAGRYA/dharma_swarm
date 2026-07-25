"""Compat re-export — redaction now lives at dharma_swarm.redaction.

Promoted to a shared module (PR audit/pr10): the scanner is a core dependency
of the memory-plane write boundaries, not just verifier/ranker packaging.
"""

from __future__ import annotations

from dharma_swarm.redaction import (
    SENSITIVE_FIELD_NAMES,
    RedactionFinding,
    RedactionResult,
    redact_record,
    redact_text,
    stable_hash,
)

__all__ = [
    "SENSITIVE_FIELD_NAMES",
    "RedactionFinding",
    "RedactionResult",
    "redact_record",
    "redact_text",
    "stable_hash",
]
