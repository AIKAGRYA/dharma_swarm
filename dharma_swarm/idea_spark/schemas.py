"""Canonical objects for the Operator Idea Spark ingest lifecycle.

Three pydantic v2 models with versioned ``schema_version`` literals:

- ``OperatorInputReceipt`` (``operator_input_receipt.v0``) — one immutable
  receipt for the fired-in thing. Never mutates trusted memory.
- ``IdeaSparkCandidate`` (``idea_spark_candidate.v0``) — the normalized middle
  object shared by operator input, latent idea shards, and world radar. Embeds
  the existing ``idea_spark_triage.v0`` tuple verbatim.
- ``OperatorInputLifecycleReceipt`` (``operator_input_lifecycle_receipt.v0``) —
  the closure receipt joining every hop by ``correlation_id``.

IDs are content-derived and deterministic (no clock, no randomness) so the same
fired-in content reproduces the same ``input_id`` / ``correlation_id`` /
``candidate_id`` and the lifecycle is idempotent. Every id is constrained to the
MemoryKernel ``source_atom_ids`` grammar (``^[A-Za-z0-9][A-Za-z0-9:._-]{0,159}$``)
so it can flow into governed write receipts without redaction.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

OPERATOR_INPUT_RECEIPT_SCHEMA = "operator_input_receipt.v0"
IDEA_SPARK_CANDIDATE_SCHEMA = "idea_spark_candidate.v0"
OPERATOR_INPUT_LIFECYCLE_RECEIPT_SCHEMA = "operator_input_lifecycle_receipt.v0"
IDEA_SPARK_TRIAGE_SCHEMA = "idea_spark_triage.v0"

SourceKind = Literal[
    "note",
    "transcript",
    "youtube_transcript",
    "session",
    "url",
    "file",
    "world_signal",
    "go_receipt",
    "idea_shard",
]
SourceRights = Literal[
    "owned",
    "operator_supplied",
    "public_excerpt",
    "link_only",
    "unknown",
]
RedactionPolicy = Literal["none", "pii_redacted", "summary_only", "link_only"]
PromotionStatus = Literal["rejected", "watchlist", "incubating", "promotion_ready"]
RoutingStatus = Literal[
    "unrouted",
    "routed",
    "proposal_queued",
    "task_queued",
    "bet_opened",
    "implemented",
    "blocked",
]
AuthorityLevel = Literal[
    "observation",
    "proposal",
    "task_candidate",
    "experiment_candidate",
    "trusted_memory",
]
LifecycleStatus = Literal[
    "captured",
    "staged",
    "routed",
    "tasked",
    "implemented",
    "blocked",
    "archived",
]

# Source rights that allow retaining raw supplied content (spec section 4 rules).
RAW_CONTENT_RIGHTS = frozenset({"owned", "operator_supplied"})

_ID_GRAMMAR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,159}$")
_NON_ID_CHARS = re.compile(r"[^A-Za-z0-9:._-]+")
_WHITESPACE = re.compile(r"\s+")


def utc_now_iso() -> str:
    """UTC timestamp, second precision, trailing ``Z`` (matches agent_onboard)."""
    return (
        datetime.now(tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def content_hash(content: str) -> str:
    """``sha256:<hex>`` of the supplied content/extract."""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _normalize_claim(claim: str) -> str:
    return _WHITESPACE.sub(" ", claim.strip().lower())


def _short(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def is_valid_lifecycle_id(value: str) -> bool:
    """True when ``value`` is a clean MemoryKernel source_atom_id."""
    return bool(_ID_GRAMMAR.match(value))


def sanitize_lifecycle_id(value: str) -> str:
    """Coerce ``value`` to the source_atom_id grammar (for foreign ids)."""
    cleaned = _NON_ID_CHARS.sub("-", value).strip("-")
    cleaned = cleaned or "x"
    if not re.match(r"^[A-Za-z0-9]", cleaned):
        cleaned = f"x{cleaned}"
    return cleaned[:160]


def derive_input_id(source_kind: str, source_ref: str, content_digest: str) -> str:
    return f"input_{_short(f'{source_kind}|{source_ref}|{content_digest}')}"


def derive_correlation_id(source_ref: str, content_digest: str) -> str:
    """Stable lifecycle join key for one fired-in thing."""
    return f"corr_{_short(f'{source_ref}|{content_digest}')}"


def derive_candidate_id(source_receipt_ref: str, claim: str) -> str:
    """Stable candidate id over source receipt + normalized claim (spec)."""
    return f"cand_{_short(f'{source_receipt_ref}|{_normalize_claim(claim)}')}"


class OperatorInputReceipt(BaseModel):
    """One immutable receipt for the fired-in thing (``operator_input_receipt.v0``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["operator_input_receipt.v0"] = OPERATOR_INPUT_RECEIPT_SCHEMA
    input_id: str
    correlation_id: str
    source_kind: SourceKind
    source_ref: str
    source_rights: SourceRights
    content_hash: str
    captured_at: str
    captured_by: str
    raw_storage_ref: str = ""
    redaction_policy: RedactionPolicy = "none"

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class IdeaSparkCandidate(BaseModel):
    """Normalized middle object (``idea_spark_candidate.v0``)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["idea_spark_candidate.v0"] = IDEA_SPARK_CANDIDATE_SCHEMA
    candidate_id: str
    correlation_id: str
    title: str
    claim: str
    why_now: str = ""
    domain: str = ""
    source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    triage: dict[str, Any] = Field(default_factory=dict)
    promotion_status: PromotionStatus = "watchlist"
    routing_status: RoutingStatus = "unrouted"
    owner_surface: str = ""
    authority_level: AuthorityLevel = "observation"
    created_at: str = Field(default_factory=utc_now_iso)

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class OperatorInputLifecycleReceipt(BaseModel):
    """Closure receipt joining the whole chain (``operator_input_lifecycle_receipt.v0``)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["operator_input_lifecycle_receipt.v0"] = (
        OPERATOR_INPUT_LIFECYCLE_RECEIPT_SCHEMA
    )
    correlation_id: str
    input_id: str = ""
    candidate_id: str = ""
    chetana_staged_atom_id: str = ""
    chetana_trusted_atom_id: str = ""
    memory_write_receipt_id: str = ""
    memory_canonical_receipt_id: str = ""
    semantic_route: str = ""
    owner_surface: str = ""
    proposal_id: str = ""
    task_id: str = ""
    bet_id: str = ""
    implementation_receipt_id: str = ""
    retrieval_probe_id: str = ""
    status: LifecycleStatus = "captured"
    blockers: list[str] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
