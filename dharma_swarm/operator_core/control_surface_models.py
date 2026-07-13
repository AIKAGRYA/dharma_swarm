"""Pydantic models and row contract for the Control Surface Projector.

Extracted from control_surface.py to keep the projection engine under
the 1000-line module budget (Rule 10).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Structured sub-models (Pydantic 2)
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    """Structured evidence item with provenance."""

    kind: Literal[
        "file", "manifest_row", "api_route", "db_probe",
        "go_receipt", "recursive_receipt", "broken_register", "process", "test",
    ]
    source: str
    line_range: tuple[int, int] | None = None
    observed_at: str = ""
    raw_content: str | None = None
    status: str | None = None
    provenance_chain: list[str] = []


class SourceRef(BaseModel):
    """Structured reference to a source file/route/config."""

    kind: Literal["file", "manifest_section", "api_route", "config", "go_module"]
    path: str
    exists: bool = True
    line_range: tuple[int, int] | None = None


class HumanDecisionContext(BaseModel):
    """Context for why a row requires human decision."""

    required: bool
    why_now: str = ""
    recommended_action: str = ""
    evidence_count: int = 0
    staleness_hours: float | None = None


class VerificationEvent(BaseModel):
    """Timeline event for how a surface moved through declare→drift→fix→verify."""

    timestamp: str
    event_type: Literal[
        "observed", "drift_detected", "fix_attempted",
        "fix_verified", "closure",
    ]
    detail: str
    agent_id: str | None = None


class AgentHandoffPrompt(BaseModel):
    """Scoped agent prompt generated from a control surface row."""

    row_id: str
    label: str
    prompt_text: str
    context_files: list[str]
    expected_tests: list[str]
    invariant: str
    generated_at: str


class DisplayHints(BaseModel):
    """Frontend-safe rendering hints computed from row semantics."""

    severity_rank: int = 0
    tone: Literal["critical", "warning", "info", "ok"] = "info"
    icon_key: str = "circle"
    group: str = "other"
    freshness_state: Literal["fresh", "stale", "unknown"] = "unknown"
    available_actions: list[str] = []


class SourceError(BaseModel):
    """An error encountered while building the projection."""

    source: str
    error: str
    timestamp: str = ""


class ControlSurfaceEnvelope(BaseModel):
    """Typed wrapper for control surface API responses."""

    schema_version: str = "0.2.0"
    request_id: str = ""
    generated_at: str = ""
    source_errors: list[SourceError] = []
    freshness_window: str = ""
    data: Any = None


# ---------------------------------------------------------------------------
# Row contract
# ---------------------------------------------------------------------------

COHERENCE_STATES = ("bound", "partial", "drifted", "declared_only", "unknown")
AUTHORITY_ROLES = (
    "declared_authority",
    "observed_authority",
    "projection",
    "adapter",
    "evidence",
    "incubating",
    "frozen",
    "unknown",
)
PRIORITIES = ("p0", "p1", "p2", "backlog", "unknown")
ROW_KINDS = (
    "api_router",
    "dashboard_page",
    "runtime_store",
    "state_writer",
    "organ",
    "fleet",
    "memory_surface",
    "memory_adapter",
    "memory_census",
    "memory_context",
    "memory_knowledgeops",
    "memory_promotion",
    "memory_rollout",
    "memory_writer",
    "operator_smoke",
    "broken_register",
    "go_receipt",
    "recursive_discovery",
    "doc_surface",
    "integration",
    "feedback_loop",
    "agent_subsystem",
    "cron_job",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ControlSurfaceRow:
    """One row in the operator cockpit grid."""

    id: str
    kind: str
    label: str
    authority_role: str = "unknown"
    declared_state: str = ""
    desired_state: str = ""
    observed_state: str = ""
    coherence_state: str = "unknown"
    priority: str = "unknown"
    owner_module: str = ""
    truth_owner: str = ""
    evidence: list[EvidenceItem] = field(default_factory=list)
    evidence_labels: list[str] = field(default_factory=list)
    freshness: str = ""
    gap_codes: list[str] = field(default_factory=list)
    next_action: str = ""
    human_decision_required: bool = False
    human_decision: HumanDecisionContext | None = None
    source_refs: list[SourceRef] = field(default_factory=list)
    source_ref_labels: list[str] = field(default_factory=list)
    verification_timeline: list[VerificationEvent] = field(default_factory=list)
    display_hints: DisplayHints | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    # -- helpers for appending structured evidence/refs ----

    def add_evidence(
        self,
        kind: str,
        source: str,
        *,
        status: str | None = None,
        line_range: tuple[int, int] | None = None,
        raw_content: str | None = None,
        provenance_chain: list[str] | None = None,
    ) -> None:
        item = EvidenceItem(
            kind=kind,  # type: ignore[arg-type]
            source=source,
            observed_at=_utc_now_iso(),
            status=status,
            line_range=line_range,
            raw_content=raw_content[:500] if raw_content else None,
            provenance_chain=provenance_chain or [],
        )
        self.evidence.append(item)
        self.evidence_labels.append(source)

    def add_source_ref(
        self,
        kind: str,
        path: str,
        *,
        exists: bool = True,
        line_range: tuple[int, int] | None = None,
    ) -> None:
        ref = SourceRef(
            kind=kind,  # type: ignore[arg-type]
            path=path,
            exists=exists,
            line_range=line_range,
        )
        self.source_refs.append(ref)
        self.source_ref_labels.append(path)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence"] = [e.model_dump() for e in self.evidence]
        d["source_refs"] = [s.model_dump() for s in self.source_refs]
        if self.human_decision is not None:
            d["human_decision"] = self.human_decision.model_dump()
        d["verification_timeline"] = [
            v.model_dump() for v in self.verification_timeline
        ]
        if self.display_hints is not None:
            d["display_hints"] = self.display_hints.model_dump()
        return d


# ---------------------------------------------------------------------------
# Human-decision policy
# ---------------------------------------------------------------------------

_HUMAN_DECISION_KEYWORDS = (
    "auth", "credential", "vps", "node_gateway", "destructive",
    "hot-path", "hot_path",
)


def _needs_human_decision(row: ControlSurfaceRow) -> bool:
    if "human_authority_required" in row.gap_codes:
        return True
    if row.kind in ("runtime_store", "state_writer", "fleet") and row.authority_role == "incubating":
        return True
    if row.priority == "p0" and row.coherence_state in ("drifted", "unknown"):
        return True
    if row.authority_role == "incubating" and row.desired_state == "live":
        return True
    if row.kind == "broken_register" and row.raw.get("status") == "OPEN":
        return True
    if "go_world_receipt_rejections" in row.gap_codes:
        return True
    if row.kind == "recursive_discovery" and "human_promotion_required" in row.gap_codes:
        return True
    label_lower = row.label.lower()
    for kw in _HUMAN_DECISION_KEYWORDS:
        if kw in label_lower or kw in row.owner_module.lower():
            return True
    return False


def _build_human_decision_context(row: ControlSurfaceRow) -> HumanDecisionContext:
    """Build structured human-decision context for a row."""
    required = _needs_human_decision(row)
    if not required:
        return HumanDecisionContext(
            required=False,
            evidence_count=len(row.evidence),
        )

    why_now = ""
    recommended_action = ""

    if "human_authority_required" in row.gap_codes:
        why_now = "Surface is explicitly marked as requiring operator authority"
        recommended_action = row.next_action or f"Review {row.label} before action"
    elif row.kind in ("runtime_store", "state_writer", "fleet") and row.authority_role == "incubating":
        why_now = f"Incubating {row.kind} wants to go live"
        recommended_action = f"Review {row.label} and promote or archive"
    elif row.priority == "p0" and row.coherence_state == "drifted":
        why_now = "P0 surface has drifted from declared state"
        recommended_action = f"Investigate drift in {row.owner_module or row.label}"
    elif row.priority == "p0" and row.coherence_state == "unknown":
        why_now = "P0 surface has unknown coherence — no observation yet"
        recommended_action = f"Run observation for {row.label}"
    elif row.authority_role == "incubating" and row.desired_state == "live":
        why_now = "Incubating surface declared as desired=live"
        recommended_action = f"Implement or promote {row.label}"
    elif row.kind == "broken_register" and row.raw.get("status") == "OPEN":
        why_now = f"Open broken register entry: {row.label}"
        recommended_action = f"Fix root cause and close {row.id.replace('br.', 'BR-').replace('_', '-')}"
    elif row.kind == "recursive_discovery" and "human_promotion_required" in row.gap_codes:
        why_now = "Recursive discovery shadow has a candidate/promotion receipt"
        recommended_action = "Review the receipt and promote only through a human PR"
    else:
        for kw in _HUMAN_DECISION_KEYWORDS:
            if kw in row.label.lower() or kw in row.owner_module.lower():
                why_now = f"Sensitive keyword '{kw}' detected in surface"
                recommended_action = f"Review {row.label} before automated changes"
                break

    staleness_hours: float | None = None
    if row.freshness:
        try:
            observed_dt = datetime.fromisoformat(row.freshness)
            delta = datetime.now(timezone.utc) - observed_dt
            staleness_hours = round(delta.total_seconds() / 3600, 1)
        except (ValueError, TypeError):
            pass

    return HumanDecisionContext(
        required=True,
        why_now=why_now,
        recommended_action=recommended_action,
        evidence_count=len(row.evidence),
        staleness_hours=staleness_hours,
    )


# ---------------------------------------------------------------------------
# Display hints computation
# ---------------------------------------------------------------------------

_KIND_GROUP_MAP: dict[str, str] = {
    "api_router": "api",
    "dashboard_page": "dashboard",
    "runtime_store": "runtime",
    "state_writer": "runtime",
    "organ": "organs",
    "fleet": "runtime",
    "memory_surface": "runtime",
    "broken_register": "issues",
    "go_receipt": "go_sdk",
    "doc_surface": "docs",
    "integration": "integrations",
    "feedback_loop": "loops",
    "agent_subsystem": "agents",
    "cron_job": "cron",
}

_KIND_ICON_MAP: dict[str, str] = {
    "api_router": "server",
    "dashboard_page": "layout-dashboard",
    "runtime_store": "database",
    "state_writer": "hard-drive",
    "organ": "heart-pulse",
    "fleet": "users",
    "memory_surface": "brain",
    "broken_register": "alert-triangle",
    "go_receipt": "file-code",
    "doc_surface": "file-text",
    "integration": "plug",
    "feedback_loop": "refresh-cw",
    "agent_subsystem": "bot",
    "cron_job": "clock",
}

_PRIORITY_RANK: dict[str, int] = {"p0": 0, "p1": 1, "p2": 2, "backlog": 3, "unknown": 4}


def _compute_display_hints(row: ControlSurfaceRow) -> DisplayHints:
    """Derive frontend-safe rendering hints from row semantics."""
    cs = row.coherence_state
    pri = row.priority

    # severity_rank: lower = more severe
    base = _PRIORITY_RANK.get(pri, 4)
    if cs == "drifted":
        severity_rank = base
    elif cs == "unknown":
        severity_rank = base + 1
    elif cs == "partial":
        severity_rank = base + 5
    elif cs == "declared_only":
        severity_rank = base + 8
    else:
        severity_rank = base + 10

    # tone
    if cs == "drifted" or (cs == "unknown" and pri == "p0"):
        tone: str = "critical"
    elif cs in ("partial", "unknown"):
        tone = "warning"
    elif cs == "bound":
        tone = "ok"
    else:
        tone = "info"

    icon_key = _KIND_ICON_MAP.get(row.kind, "circle")
    group = _KIND_GROUP_MAP.get(row.kind, "other")

    # freshness_state
    freshness_state: str = "unknown"
    if row.freshness:
        try:
            observed_dt = datetime.fromisoformat(row.freshness)
            age_hours = (datetime.now(timezone.utc) - observed_dt).total_seconds() / 3600
            freshness_state = "fresh" if age_hours < 24 else "stale"
        except (ValueError, TypeError):
            pass

    # available_actions
    actions: list[str] = []
    if cs in ("drifted", "partial", "unknown"):
        actions.append("investigate")
    if row.human_decision_required:
        actions.append("decide")
    if cs != "bound":
        actions.append("handoff")
    if row.kind == "broken_register":
        actions.append("close_br")

    return DisplayHints(
        severity_rank=severity_rank,
        tone=tone,  # type: ignore[arg-type]
        icon_key=icon_key,
        group=group,
        freshness_state=freshness_state,  # type: ignore[arg-type]
        available_actions=actions,
    )
