# spine: writes EvidenceReceipt
"""EvidenceReceipt — the one canonical artifact every dispatch attempt produces.

Designed to serialize cleanly to OpenTelemetry GenAI span attributes.
OTel is an EXPORT ADAPTER, not the truth surface. The receipt itself is
the canonical record.

See docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md §7 Fix 1.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

ReceiptStatus = Literal["ok", "failed", "dropped", "timeout", "cancelled"]

ErrorSource = Literal[
    "none",
    "task_missing",
    "runner_missing",
    "task_and_runner_missing",
    "claim_lost",
    "routing_failed",
    "provider_unreachable",
    "provider_failed",
    "guardrail_blocked",
    "cancelled",
    "timeout",
    "internal_error",
]


@dataclass(frozen=True, slots=True)
class EvidenceReceipt:
    """The one canonical artifact every dispatch attempt produces."""

    # Identity
    receipt_id: UUID = field(default_factory=uuid4)
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: Optional[str] = None
    context_id: str = ""
    task_id: str = ""
    claim_id: Optional[str] = None
    claim_status: Optional[str] = None

    # What was invoked
    agent_id: str = ""
    agent_card_version: str = ""
    provider: str = ""
    model: str = ""
    operation: str = "invoke_agent"
    provider_attempted: bool = False

    # Outcome
    status: ReceiptStatus = "ok"
    error_source: ErrorSource = "none"
    error_detail: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    latency_ms: Optional[int] = None

    # Cost & tokens (OTel gen_ai.usage.*)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None

    # Routing trace
    routing_decision_id: Optional[UUID] = None

    # Free-form attributes
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_otel_span(self) -> dict[str, Any]:
        """Serialize as OTel GenAI span attributes."""
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": self.operation,
            "gen_ai.system": self.provider,
            "gen_ai.request.model": self.model,
            "gen_ai.agent.id": self.agent_id,
            "dharma.context_id": self.context_id,
            "dharma.task_id": self.task_id,
            "dharma.agent_card_version": self.agent_card_version,
            "dharma.receipt_id": str(self.receipt_id),
            "dharma.status": self.status,
            "dharma.provider_attempted": self.provider_attempted,
        }
        if self.input_tokens is not None:
            attrs["gen_ai.usage.input_tokens"] = self.input_tokens
        if self.output_tokens is not None:
            attrs["gen_ai.usage.output_tokens"] = self.output_tokens
        if self.cost_usd is not None:
            attrs["gen_ai.usage.cost_usd"] = self.cost_usd
        if self.error_source != "none":
            attrs["dharma.error_source"] = self.error_source
        if self.error_detail:
            attrs["dharma.error_detail"] = self.error_detail
        if self.claim_id:
            attrs["dharma.claim_id"] = self.claim_id
            attrs["dharma.claim_status"] = self.claim_status or ""
        if self.routing_decision_id:
            attrs["dharma.routing_decision_id"] = str(self.routing_decision_id)
        attrs.update({f"dharma.attr.{k}": v for k, v in self.attributes.items()})
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": f"invoke_agent {self.agent_id}",
            "start_time": self.started_at.isoformat(),
            "end_time": (
                self.finished_at.isoformat() if self.finished_at else None
            ),
            "attributes": attrs,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        d = asdict(self)
        d["receipt_id"] = str(self.receipt_id)
        d["started_at"] = self.started_at.isoformat()
        if self.finished_at:
            d["finished_at"] = self.finished_at.isoformat()
        if self.routing_decision_id:
            d["routing_decision_id"] = str(self.routing_decision_id)
        return d
