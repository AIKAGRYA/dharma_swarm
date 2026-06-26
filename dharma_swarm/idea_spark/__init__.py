"""Operator Idea Spark ingest lifecycle.

Receipt-backed spine from a fired-in operator idea/transcript/signal to a routed
action and later recall:

    operator input
      -> OperatorInputReceipt          (immutable source receipt)
      -> IdeaSparkCandidate            (normalized middle object, idea_spark_triage.v0)
      -> Chetana staged atom           (untrusted; promotion is gate-governed)
      -> MemoryKernel receipt          (governed, human-gated; no silent mutation)
      -> Semantic Commons owner route  (fail-closed)
      -> proposal / task / BetCard     (dispatch_authority off by default)
      -> implementation / experiment receipt
      -> retrieval proof by correlation_id

This package OWNS the lifecycle plumbing only. It reuses existing owners for
every substantive capability (world_radar triage, Chetana, MemoryKernel,
Semantic Commons, Darwin proposals, frontier tasks, Verified Experiment Loop)
and never re-implements them. Controlling spec:
``docs/specs/OPERATOR_IDEA_SPARK_INGEST_LONGRUN_BUILD.md``.
"""

from __future__ import annotations

from .schemas import (
    IDEA_SPARK_CANDIDATE_SCHEMA,
    OPERATOR_INPUT_LIFECYCLE_RECEIPT_SCHEMA,
    OPERATOR_INPUT_RECEIPT_SCHEMA,
    IdeaSparkCandidate,
    OperatorInputLifecycleReceipt,
    OperatorInputReceipt,
    content_hash,
    derive_candidate_id,
    derive_correlation_id,
    derive_input_id,
    utc_now_iso,
)

__all__ = [
    "OPERATOR_INPUT_RECEIPT_SCHEMA",
    "IDEA_SPARK_CANDIDATE_SCHEMA",
    "OPERATOR_INPUT_LIFECYCLE_RECEIPT_SCHEMA",
    "OperatorInputReceipt",
    "IdeaSparkCandidate",
    "OperatorInputLifecycleReceipt",
    "content_hash",
    "derive_input_id",
    "derive_correlation_id",
    "derive_candidate_id",
    "utc_now_iso",
]
