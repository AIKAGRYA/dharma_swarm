"""Fractal Room — the recursive building block for governed venture cells.

Implements the Five Laws derived from Beer VSM, Haier RenDanHeYi, Holacracy,
Nonaka dynamic fractal orgs, De Florio recursive architectures, and BAMAS
budget-aware multi-agent systems.

Law 1: Recursive Self-Similarity (every room has S1-S5)
Law 2: Economic Accountability (VCs have revenue targets + kill conditions)
Law 3: Governed Autonomy (forbidden_work inherits, approvals propagate)
Law 4: Knowledge Compounding (work → outcome → review → playbook)
Law 5: Dissolution with Recycling (archive returns agents + budget to parent)

Integration points (existing modules reused):
  - CorrelationContext.cell_id — trace propagation scoped to room
  - SignalBus — room lifecycle events (ROOM_CREATED, ROOM_ARCHIVED, etc.)
  - EconomicEngine — per-room revenue/expense via Transaction.metadata
  - CostTracker — budget consumption monitoring
  - TelosGatekeeper — room-level gate policy (gates field)
  - ExternalAgentRegistration — agent authority scoping per room
  - StigmergyStore — room-scoped memory namespace
  - KaizenOpsLocal — room_id on operational events
  - AlgedonicSignal — emergency bypass preserves room context
  - JagatKalyanEngine — welfare constraint on VentureCells
  - TaskBoard — work packet links via trace_id + cell_id
  - QualityForge — automated quality signals per room
  - Operator Brief — room sections in daily brief
  - WitnessLog — spawn/archive events witnessed

See: docs/research/FRACTAL_VENTURE_CELL_RESEARCH.md
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

MAX_NESTING_DEPTH = 3


def _new_room_id() -> str:
    return f"room_{uuid4().hex[:12]}"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RoomKind(StrEnum):
    OPERATIONS = "operations"
    GOVERNANCE = "governance"
    VENTURE_CELL = "venture_cell"
    RESEARCH = "research"


class RoomStatus(StrEnum):
    PROPOSED = "proposed"
    INCUBATING = "incubating"
    ACTIVE = "active"
    GRADUATING = "graduating"
    ARCHIVED = "archived"
    SPUN_OUT = "spun_out"


# ---------------------------------------------------------------------------
# SignalBus event types for room lifecycle
# ---------------------------------------------------------------------------

SIGNAL_ROOM_CREATED = "ROOM_CREATED"
SIGNAL_ROOM_ARCHIVED = "ROOM_ARCHIVED"
SIGNAL_ROOM_SPAWNED_CHILD = "ROOM_SPAWNED_CHILD"
SIGNAL_ROOM_KILL_CONDITION_MET = "ROOM_KILL_CONDITION_MET"
SIGNAL_ROOM_SPINOUT_CONDITION_MET = "ROOM_SPINOUT_CONDITION_MET"
SIGNAL_ROOM_BUDGET_DEPLETED = "ROOM_BUDGET_DEPLETED"
SIGNAL_WORK_PACKET_CREATED = "WORK_PACKET_CREATED"
SIGNAL_WORK_PACKET_COMPLETED = "WORK_PACKET_COMPLETED"
SIGNAL_YDS_RATING_ADDED = "YDS_RATING_ADDED"


# ---------------------------------------------------------------------------
# Core Types
# ---------------------------------------------------------------------------


@dataclass
class FractalRoom:
    """The recursive building block — a governed operating container.

    Every room maps to Beer's VSM:
      S1 (Operations): agents + work packets
      S2 (Coordination): signal_bus_topics
      S3 (Control): gates + approval_required_for + budget
      S4 (Intelligence): report_paths + memory_namespace
      S5 (Identity): purpose + operator
    """

    # S5 — Identity
    id: str = field(default_factory=_new_room_id)
    kind: RoomKind = RoomKind.OPERATIONS
    parent_id: str | None = None
    purpose: str = ""
    status: RoomStatus = RoomStatus.PROPOSED
    operator: str = ""

    # S1 — Operations (roster)
    agents: list[str] = field(default_factory=list)
    agent_authorities: dict[str, str] = field(default_factory=dict)

    # S3 — Control (economy)
    budget_tokens: int = 0
    current_burn: int = 0
    revenue_target: int = 0

    # S3 — Control (law)
    allowed_work: list[str] = field(default_factory=list)
    forbidden_work: list[str] = field(default_factory=list)
    gates: list[str] = field(default_factory=lambda: ["AHIMSA", "SATYA", "REVERSIBILITY"])
    approval_required_for: list[str] = field(default_factory=list)

    # S4 — Intelligence (memory)
    report_paths: dict[str, str] = field(default_factory=dict)
    memory_namespace: str = ""

    # S2 — Coordination (signal bus topics this room subscribes to)
    signal_bus_topics: list[str] = field(default_factory=list)

    # Pulse (S4/S1 feedback)
    last_brief_date: str | None = None
    next_packet_recommendation: str | None = None

    # Metadata
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def remaining_budget(self) -> int:
        return max(0, self.budget_tokens - self.current_burn)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FractalRoom:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class VentureCellV1(FractalRoom):
    """A room with economic survival pressure (Haier RenDanHeYi model).

    Extends FractalRoom with:
      - customer_or_beneficiary (Haier zero-distance-to-user)
      - kill_conditions (Haier dissolution threshold)
      - spinout_conditions (venture studio graduation)
      - jagat_kalyan_constraint (welfare economics)
    """

    # Business
    customer_or_beneficiary: str = ""
    value_proposition: str = ""

    # Hypothesis
    self_funding_hypothesis: str = ""
    first_revenue_proof: str = ""

    # Lifecycle
    kill_conditions: list[str] = field(default_factory=list)
    spinout_conditions: list[str] = field(default_factory=list)

    # Welfare (Jagat Kalyan)
    jagat_kalyan_constraint: str = ""
    welfare_tons_produced: float = 0.0

    # Autonomy (maps to ontology VentureCell.autonomy_stage)
    autonomy_stage: int = 1

    # Forge feed — "no side quest without a forge-feed contract".
    # How this cell feeds the Dharma Reward Forge: the verifiable tasks, outcomes,
    # failures, receipts, or ontology objects it emits. Optional field; enforced at
    # Forge-feed/admission time (graded), not retroactively breaking existing cells.
    forge_feed_contract: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VentureCellV1:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def forge_feed_contract_status(cell: VentureCellV1) -> str:
    """Return 'present' if a VentureCell declares how it feeds the Reward Forge, else 'missing'.

    The rule (Dharma Reward Forge doctrine): every side-organ — app, bounty,
    publication, trading experiment, NGO tool, or Polsia-like shell — must emit
    verifiable tasks/outcomes/failures/receipts/ontology-objects to the Forge.
    This is the graded admission check; it does not retroactively invalidate cells.
    """
    return "present" if str(getattr(cell, "forge_feed_contract", "")).strip() else "missing"


@dataclass
class WorkPacket:
    """A scoped unit of work inside a room.

    Links to ontology ActionProposal via action_proposal_id.
    Links to TaskBoard via trace_id from CorrelationContext.
    """

    id: str = field(default_factory=lambda: f"wp_{uuid4().hex[:12]}")
    source_room_id: str = ""
    purpose: str = ""
    action_proposal_id: str | None = None
    assigned_agent_id: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    forbidden_mutations: list[str] = field(default_factory=list)
    gate_requirements: list[str] = field(default_factory=list)
    success_criteria: str = ""
    timeout_seconds: int = 3600
    cost_ceiling: int = 0
    report_target: str = ""
    status: str = "pending"
    created_at: str = field(default_factory=_now_iso)
    completed_at: str | None = None
    outcome: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class YDSRating:
    """Human-only quality rating (Yosemite Decimal System).

    Separated from QualityForge (automated scoring) because YDS is
    human practical wisdom — phronesis (Nonaka 2014).
    """

    id: str = field(default_factory=lambda: f"yds_{uuid4().hex[:12]}")
    artifact_id: str = ""
    room_id: str = ""
    rater: str = ""
    score: int = 5
    dimension: str = "craft"
    comment: str = ""
    timestamp: str = field(default_factory=_now_iso)

    VALID_DIMENSIONS = frozenset({"craft", "truth", "usefulness", "beauty", "coherence"})


# ---------------------------------------------------------------------------
# Kill Condition Evaluation
# ---------------------------------------------------------------------------

# Registry of named kill conditions → evaluator functions.
# Each takes a KPI dict and returns True if the kill condition is met.
_KILL_CONDITION_EVALUATORS: dict[str, Any] = {
    "no_revenue_after_60_days": lambda kpis: (
        kpis.get("revenue_usd", 0) == 0 and kpis.get("days_active", 0) > 60
    ),
    "burn_exceeds_3x_revenue": lambda kpis: (
        kpis.get("burn_usd", 0) > 3 * max(kpis.get("revenue_usd", 0), 0.01)
    ),
    "budget_exceeded": lambda kpis: (
        kpis.get("budget_ratio", 0) > 1.2
    ),
    "no_work_packets_30_days": lambda kpis: (
        kpis.get("days_since_last_packet", 0) > 30
    ),
    "zero_agents_assigned": lambda kpis: (
        kpis.get("agent_count", 0) == 0
    ),
    "welfare_tons_negative": lambda kpis: (
        kpis.get("welfare_tons", 0) < 0
    ),
    "operator_override": lambda kpis: (
        kpis.get("operator_kill", False) is True
    ),
}

_SPINOUT_CONDITION_EVALUATORS: dict[str, Any] = {
    "revenue_covers_burn": lambda kpis: (
        kpis.get("revenue_usd", 0) >= kpis.get("burn_usd", 0)
        and kpis.get("revenue_usd", 0) > 0
    ),
    "revenue_exceeds_burn": lambda kpis: (
        kpis.get("monthly_revenue_gt_burn_months", 0) >= 3
    ),
    "3_paying_customers": lambda kpis: (
        kpis.get("paying_customers", 0) >= 3
    ),
    "customer_validation": lambda kpis: (
        kpis.get("paying_customers", 0) >= 3
    ),
    "operator_approval": lambda kpis: (
        kpis.get("operator_approved_graduation", False) is True
    ),
    "autonomy_stage_5": lambda kpis: (
        kpis.get("autonomy_stage", 0) >= 5
    ),
}


def evaluate_kill_conditions(conditions: list[str], kpis: dict[str, Any]) -> bool:
    """Pure function: returns True if ANY kill condition is met."""
    for cond in conditions:
        evaluator = _KILL_CONDITION_EVALUATORS.get(cond)
        if evaluator and evaluator(kpis):
            return True
    return False


def evaluate_spinout_conditions(conditions: list[str], kpis: dict[str, Any]) -> bool:
    """Pure function: returns True if ALL spinout conditions are met."""
    if not conditions:
        return False
    for cond in conditions:
        evaluator = _SPINOUT_CONDITION_EVALUATORS.get(cond)
        if not evaluator or not evaluator(kpis):
            return False
    return True


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class RoomValidationError(Exception):
    """Raised when a room fails validation rules."""


def validate_room(room: FractalRoom, registry: RoomRegistry | None = None) -> None:
    """Validate a FractalRoom against the spec rules."""
    if not room.purpose:
        raise RoomValidationError("Room purpose must be non-empty")

    if not room.operator:
        raise RoomValidationError("Room operator must be non-empty")

    if room.budget_tokens < 0:
        raise RoomValidationError("budget_tokens must be non-negative")

    if registry:
        if room.id in registry._rooms and registry._rooms[room.id] is not room:
            raise RoomValidationError(f"Room ID '{room.id}' already exists in registry")

        if room.parent_id is not None:
            parent = registry.get(room.parent_id)
            if parent is None:
                raise RoomValidationError(
                    f"Parent room '{room.parent_id}' does not exist"
                )

            depth = registry.nesting_depth(room.parent_id)
            if depth >= MAX_NESTING_DEPTH:
                raise RoomValidationError(
                    f"Nesting depth {depth + 1} exceeds max {MAX_NESTING_DEPTH}"
                )

            if room.budget_tokens > parent.remaining_budget():
                raise RoomValidationError(
                    f"Child budget {room.budget_tokens} exceeds parent "
                    f"remaining budget {parent.remaining_budget()}"
                )

            # Law 3: forbidden_work inherits additively
            parent_forbidden = set(parent.forbidden_work)
            child_forbidden = set(room.forbidden_work)
            if not parent_forbidden.issubset(child_forbidden):
                missing = parent_forbidden - child_forbidden
                raise RoomValidationError(
                    f"Child must inherit parent's forbidden_work: missing {missing}"
                )

            # Law 3: approval_required_for inherits
            parent_approvals = set(parent.approval_required_for)
            child_approvals = set(room.approval_required_for)
            if not parent_approvals.issubset(child_approvals):
                missing = parent_approvals - child_approvals
                raise RoomValidationError(
                    f"Child must inherit parent's approval_required_for: "
                    f"missing {missing}"
                )


def validate_venture_cell(cell: VentureCellV1, registry: RoomRegistry | None = None) -> None:
    """Validate a VentureCell against additional VC-specific rules."""
    validate_room(cell, registry)

    if cell.kind != RoomKind.VENTURE_CELL:
        raise RoomValidationError("VentureCell kind must be 'venture_cell'")

    if not cell.customer_or_beneficiary:
        raise RoomValidationError(
            "VentureCell must have customer_or_beneficiary (Haier zero-distance)"
        )

    if cell.revenue_target <= 0:
        raise RoomValidationError("VentureCell revenue_target must be > 0")

    if not cell.kill_conditions:
        raise RoomValidationError("VentureCell must have at least one kill_condition")

    if not (1 <= cell.autonomy_stage <= 5):
        raise RoomValidationError("autonomy_stage must be 1-5")


def validate_work_packet(
    packet: WorkPacket,
    registry: RoomRegistry | None = None,
) -> None:
    """Validate a WorkPacket against its source room's constraints."""
    if not packet.purpose:
        raise RoomValidationError("WorkPacket purpose must be non-empty")
    if not packet.source_room_id:
        raise RoomValidationError("WorkPacket must have source_room_id")

    if registry:
        room = registry.get(packet.source_room_id)
        if room is None:
            raise RoomValidationError(
                f"Source room '{packet.source_room_id}' does not exist"
            )
        if room.status == RoomStatus.ARCHIVED:
            raise RoomValidationError("Cannot create work packet for archived room")

        if packet.cost_ceiling > 0 and packet.cost_ceiling > room.remaining_budget():
            raise RoomValidationError(
                f"WorkPacket cost_ceiling {packet.cost_ceiling} exceeds "
                f"room remaining budget {room.remaining_budget()}"
            )

        if packet.assigned_agent_id and packet.assigned_agent_id not in room.agents:
            raise RoomValidationError(
                f"Agent '{packet.assigned_agent_id}' not in room roster"
            )

        room_forbidden = set(room.forbidden_work)
        packet_forbidden = set(packet.forbidden_mutations)
        if not room_forbidden.issubset(packet_forbidden):
            missing = room_forbidden - packet_forbidden
            raise RoomValidationError(
                f"WorkPacket must inherit room's forbidden_work: missing {missing}"
            )


def validate_yds_rating(
    rating: YDSRating,
    human_operators: frozenset[str] | None = None,
) -> None:
    """Validate a YDS rating — enforces human-only constraint."""
    if not rating.artifact_id:
        raise RoomValidationError("YDS rating must reference an artifact_id")
    if not rating.room_id:
        raise RoomValidationError("YDS rating must reference a room_id")
    if not rating.rater:
        raise RoomValidationError("YDS rating must have a rater")
    if not (1 <= rating.score <= 10):
        raise RoomValidationError("YDS score must be 1-10")
    if rating.dimension not in YDSRating.VALID_DIMENSIONS:
        raise RoomValidationError(
            f"YDS dimension must be one of {YDSRating.VALID_DIMENSIONS}"
        )
    if human_operators and rating.rater not in human_operators:
        raise RoomValidationError(
            f"YDS rater '{rating.rater}' must be a human operator"
        )


# ---------------------------------------------------------------------------
# Room Registry (in-memory, JSON-serializable)
# ---------------------------------------------------------------------------


class RoomRegistry:
    """In-memory registry of all fractal rooms.

    Enforces uniqueness, provides parent/child traversal, and handles
    spawn/archive lifecycle operations.

    Integration with existing systems:
      - Emits SignalBus events for lifecycle transitions
      - Tracks budget conservation across parent-child relationships
      - Preserves knowledge artifacts on archival (Law 5)
    """

    def __init__(self) -> None:
        self._rooms: dict[str, FractalRoom] = {}
        self._work_packets: dict[str, WorkPacket] = {}
        self._yds_ratings: list[YDSRating] = []
        self._archived_knowledge: dict[str, list[dict[str, Any]]] = {}

    def register(self, room: FractalRoom) -> None:
        """Register a room after validation. Deducts budget from parent."""
        if isinstance(room, VentureCellV1):
            validate_venture_cell(room, self)
        else:
            validate_room(room, self)

        self._rooms[room.id] = room

        if room.parent_id:
            parent = self._rooms[room.parent_id]
            parent.current_burn += room.budget_tokens
            parent.updated_at = _now_iso()

        room.updated_at = _now_iso()

    def get(self, room_id: str) -> FractalRoom | None:
        return self._rooms.get(room_id)

    def children(self, room_id: str) -> list[FractalRoom]:
        return [r for r in self._rooms.values() if r.parent_id == room_id]

    def nesting_depth(self, room_id: str) -> int:
        """Calculate nesting depth of a room (root = 0)."""
        depth = 0
        current = self._rooms.get(room_id)
        while current and current.parent_id:
            depth += 1
            current = self._rooms.get(current.parent_id)
            if depth > MAX_NESTING_DEPTH + 1:
                break
        return depth

    def all_rooms(self) -> list[FractalRoom]:
        return list(self._rooms.values())

    def active_rooms(self) -> list[FractalRoom]:
        return [
            r for r in self._rooms.values()
            if r.status not in (RoomStatus.ARCHIVED, RoomStatus.SPUN_OUT)
        ]

    def children_of(self, room_id: str) -> list[FractalRoom]:
        return [
            r for r in self._rooms.values()
            if r.parent_id == room_id
        ]

    def venture_cells(self) -> list[VentureCellV1]:
        return [
            r for r in self._rooms.values()
            if isinstance(r, VentureCellV1)
        ]

    # --- Work Packets ---

    def create_work_packet(self, packet: WorkPacket) -> WorkPacket:
        """Create and register a work packet."""
        validate_work_packet(packet, self)
        self._work_packets[packet.id] = packet
        return packet

    def get_work_packet(self, packet_id: str) -> WorkPacket | None:
        return self._work_packets.get(packet_id)

    def room_work_packets(self, room_id: str) -> list[WorkPacket]:
        return [
            p for p in self._work_packets.values()
            if p.source_room_id == room_id
        ]

    def complete_work_packet(
        self, packet_id: str, outcome: str, cost_tokens: int = 0,
    ) -> None:
        """Mark a work packet complete. Deducts cost from room budget."""
        packet = self._work_packets.get(packet_id)
        if not packet:
            raise RoomValidationError(f"WorkPacket '{packet_id}' not found")
        packet.status = "completed"
        packet.completed_at = _now_iso()
        packet.outcome = outcome

        if cost_tokens > 0:
            room = self._rooms.get(packet.source_room_id)
            if room:
                room.current_burn += cost_tokens
                room.updated_at = _now_iso()

    # --- YDS Ratings ---

    def add_yds_rating(
        self,
        rating: YDSRating,
        human_operators: frozenset[str] | None = None,
    ) -> None:
        """Add a YDS rating after validation."""
        validate_yds_rating(rating, human_operators)
        self._yds_ratings.append(rating)

    def room_yds_ratings(self, room_id: str) -> list[YDSRating]:
        return [r for r in self._yds_ratings if r.room_id == room_id]

    # --- Lifecycle: Spawn ---

    def spawn_child(
        self,
        parent_id: str,
        child: FractalRoom,
        *,
        consent_gate_passed: bool = False,
    ) -> FractalRoom:
        """Spawn a child room from a parent. Enforces spawn protocol.

        Spawn protocol (from spec):
          1. CONSENT gate must pass
          2. Parent has sufficient budget
          3. Nesting depth < max
          4. Child inherits parent's forbidden_work + own
          5. Child inherits parent's approval_required_for + own
          6. Parent budget deducted
          7. Child registered
        """
        if not consent_gate_passed:
            raise RoomValidationError(
                "Spawn requires CONSENT gate approval"
            )

        parent = self.get(parent_id)
        if parent is None:
            raise RoomValidationError(f"Parent room '{parent_id}' not found")

        child.parent_id = parent_id

        # Ensure child inherits parent constraints
        parent_forbidden = set(parent.forbidden_work)
        child.forbidden_work = list(
            parent_forbidden | set(child.forbidden_work)
        )

        parent_approvals = set(parent.approval_required_for)
        child.approval_required_for = list(
            parent_approvals | set(child.approval_required_for)
        )

        # If memory_namespace not set, derive from parent
        if not child.memory_namespace:
            child.memory_namespace = f"{parent.memory_namespace}/{child.id}"

        self.register(child)
        return child

    # --- Lifecycle: Archive (Dissolution with Recycling) ---

    def archive_room(self, room_id: str) -> dict[str, Any]:
        """Archive a room. Returns agents and budget to parent.

        Law 5: Dissolution with Recycling
          1. Status → archived
          2. Agents → parent roster
          3. Unspent budget → parent
          4. Knowledge preserved in _archived_knowledge
          5. Sub-rooms recursively archived
          6. No new work packets accepted
        """
        room = self.get(room_id)
        if room is None:
            raise RoomValidationError(f"Room '{room_id}' not found")
        if room.status == RoomStatus.ARCHIVED:
            raise RoomValidationError(f"Room '{room_id}' already archived")

        recycled = {
            "room_id": room_id,
            "agents_returned": list(room.agents),
            "budget_returned": room.remaining_budget(),
            "children_archived": [],
            "knowledge_preserved": True,
        }

        # Recursively archive children first
        for child in self.children(room_id):
            if child.status != RoomStatus.ARCHIVED:
                child_result = self.archive_room(child.id)
                recycled["children_archived"].append(child_result)

        # Return agents to parent
        if room.parent_id:
            parent = self.get(room.parent_id)
            if parent:
                for agent in room.agents:
                    if agent not in parent.agents:
                        parent.agents.append(agent)

                # Return unspent budget
                returned = room.remaining_budget()
                parent.current_burn = max(0, parent.current_burn - returned)
                parent.updated_at = _now_iso()

        # Preserve knowledge
        packets = self.room_work_packets(room_id)
        ratings = self.room_yds_ratings(room_id)
        self._archived_knowledge[room_id] = {
            "work_packets": [p.to_dict() for p in packets],
            "yds_ratings": [asdict(r) for r in ratings],
            "room_snapshot": room.to_dict(),
        }

        room.status = RoomStatus.ARCHIVED
        room.agents = []
        room.updated_at = _now_iso()

        return recycled

    def archived_knowledge(self, room_id: str) -> dict[str, Any] | None:
        """Retrieve preserved knowledge from an archived room."""
        return self._archived_knowledge.get(room_id)

    # --- Serialization ---

    def to_json(self) -> str:
        """Serialize entire registry to JSON."""
        data = {
            "rooms": {
                rid: r.to_dict() for rid, r in self._rooms.items()
            },
            "work_packets": {
                pid: p.to_dict() for pid, p in self._work_packets.items()
            },
            "yds_ratings": [asdict(r) for r in self._yds_ratings],
        }
        return json.dumps(data, indent=2)

    # --- Room Brief Generation ---

    def room_brief(self, room_id: str) -> dict[str, Any]:
        """Generate a room-level brief for the Operator Brief.

        Integrates with operator_brief/insight_brief.py as an additional
        section in the daily brief.
        """
        room = self.get(room_id)
        if room is None:
            return {"error": f"Room '{room_id}' not found"}

        packets = self.room_work_packets(room_id)
        completed = [p for p in packets if p.status == "completed"]
        pending = [p for p in packets if p.status == "pending"]
        children = self.children(room_id)
        ratings = self.room_yds_ratings(room_id)

        brief: dict[str, Any] = {
            "room_id": room.id,
            "kind": room.kind,
            "purpose": room.purpose,
            "status": room.status,
            "budget": {
                "allocated": room.budget_tokens,
                "burned": room.current_burn,
                "remaining": room.remaining_budget(),
                "utilization_pct": round(
                    (room.current_burn / max(room.budget_tokens, 1)) * 100, 1
                ),
            },
            "roster": {
                "agents": room.agents,
                "count": len(room.agents),
            },
            "work_packets": {
                "total": len(packets),
                "completed": len(completed),
                "pending": len(pending),
            },
            "children": [
                {"id": c.id, "kind": c.kind, "status": c.status}
                for c in children
            ],
            "yds_ratings": {
                "count": len(ratings),
                "avg_score": (
                    round(sum(r.score for r in ratings) / len(ratings), 1)
                    if ratings else None
                ),
            },
            "last_brief_date": room.last_brief_date,
            "next_recommendation": room.next_packet_recommendation,
        }

        if isinstance(room, VentureCellV1):
            brief["venture_cell"] = {
                "customer": room.customer_or_beneficiary,
                "revenue_target": room.revenue_target,
                "autonomy_stage": room.autonomy_stage,
                "kill_conditions": room.kill_conditions,
                "spinout_conditions": room.spinout_conditions,
                "welfare_tons": room.welfare_tons_produced,
                "jagat_kalyan": room.jagat_kalyan_constraint,
            }

        return brief
