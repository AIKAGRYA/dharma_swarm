"""BoardStore data models — Card schema and supporting types.

Implements §3 (The Card Schema) of SWARM_BOARDSTORE_SPEC.md.
The Card schema is stable for 1-3 years. Additive changes must go
through adapters, capabilities, receipts, or render hints.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, NewType

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

CardId = NewType("CardId", str)
ObjectiveId = NewType("ObjectiveId", str)
AgentId = NewType("AgentId", str)
LeaseId = NewType("LeaseId", str)
ReceiptId = NewType("ReceiptId", str)
EventId = NewType("EventId", str)
IsoDatetime = NewType("IsoDatetime", str)
MoneyUSD = Decimal
Version = NewType("Version", int)

CardStatus = Literal[
    "inbox",
    "triaged",
    "planned",
    "blocked",
    "claimable",
    "claimed",
    "running",
    "review",
    "done",
    "failed",
    "cancelled",
    "quarantined",
]

AssigneeKind = Literal[
    "human",
    "codex",
    "claude_code",
    "cursor",
    "devin",
    "warp",
    "perplexity",
    "daemon",
    "roaming",
    "unknown",
]

SourceSurface = Literal[
    "dashboard",
    "cli",
    "telegram",
    "github",
    "email",
    "voice",
    "noticer",
    "ci",
    "recursive_discovery",
    "operator_bridge",
    "task_board",
    "runtime_state",
    "api_admin",
    "unknown",
]

# ---------------------------------------------------------------------------
# Nested objects
# ---------------------------------------------------------------------------


class ClaimLease(BaseModel):
    """Prevents two agents from mutating the same work concurrently."""

    lease_id: LeaseId
    card_id: CardId
    agent_id: AgentId
    agent_kind: AssigneeKind
    claimed_at: IsoDatetime
    heartbeat_at: IsoDatetime | None = None
    expires_at: IsoDatetime
    revoked_at: IsoDatetime | None = None
    revoke_reason: str = ""
    cost_burn_usd: MoneyUSD = Decimal("0.00")
    capability_manifest: dict[str, str | int | float | bool | list[str]] = Field(
        default_factory=dict
    )


class AcceptanceCriterion(BaseModel):
    """Machine-verifiable or human-attestable completion gate."""

    id: str
    text: str
    kind: Literal["test", "doc", "artifact", "manual", "external", "receipt"]
    required: bool = True
    verifier: str = ""
    evidence_ref: str = ""


class ReceiptRef(BaseModel):
    """Pointer to a durable receipt in any store."""

    receipt_id: ReceiptId
    kind: str
    store: Literal[
        "runtime_state", "event_log", "roaming_mailbox", "artifact_store", "external"
    ]
    uri: str
    checksum: str = ""
    created_at: IsoDatetime
    summary: str = ""


class AuditEntry(BaseModel):
    """Single event in a card's audit log."""

    event_id: EventId
    actor_id: str
    actor_kind: Literal["operator", "agent", "noticer", "facade", "admin"]
    action: str
    at: IsoDatetime
    idempotency_key: str
    previous_version: Version | None = None
    next_version: Version | None = None
    reason: str = ""


class RenderHints(BaseModel):
    """Display guidance for surfaces (kanban, table, telegram, etc.)."""

    view_priority: int = 0
    color_key: str = ""
    icon_key: str = ""
    column_hint: str = ""
    lane_hint: str = ""
    thread_hint: str = ""
    map_node_kind: str = ""


# ---------------------------------------------------------------------------
# The Card — central schema
# ---------------------------------------------------------------------------


class Card(BaseModel):
    """The stable unit of work in the BoardStore facade.

    Maps to TaskBoard tasks, OperatorBridge work orders, or
    facade-generated cards. Never reused once created.
    """

    id: CardId
    parent_objective: ObjectiveId | None = None
    title: str
    body: str
    status: CardStatus
    claim_lease: ClaimLease | None = None
    assignee_kind: AssigneeKind = "unknown"
    capability_required: list[str] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    receipt_refs: list[ReceiptRef] = Field(default_factory=list)
    cost_ceiling_usd: MoneyUSD = Decimal("0.00")
    audit_log: list[AuditEntry] = Field(default_factory=list)
    version: Version = Version(1)
    idempotency_key: str = ""
    arjuna_weight: float = 0.0
    created_by: str = ""
    created_at: IsoDatetime = IsoDatetime("")
    updated_at: IsoDatetime = IsoDatetime("")
    last_transitioned_at: IsoDatetime = IsoDatetime("")
    source_surface: SourceSurface = "unknown"
    render_hints: RenderHints = Field(default_factory=RenderHints)
