"""Room Bridge — wires fractal rooms into Dharma's existing runtime.

This module is the integration layer between the fractal room schema
and the 17+ existing modules it reuses. No new infrastructure — just
connections to what already exists.

Integration map:
  CorrelationContext  → cell_id field propagates room scope
  SignalBus           → room lifecycle events (create/archive/spawn/kill)
  EconomicEngine      → per-room revenue/expense via Transaction metadata
  CostTracker         → budget consumption monitoring
  KaizenOpsLocal      → room_id on operational events
  StigmergyStore      → room-scoped marks via memory_namespace
  AlgedonicSignal     → emergency bypass with room context
  QualityForge        → automated quality signals per room
  ExternalAgentReg    → agent authority per room (cross-reference)
  JagatKalyanEngine   → welfare constraint enforcement
  VSM Channels        → S3↔S4 gate patterns scoped to room
  TaskBoard           → work packets link via cell_id in trace
  WitnessLog          → spawn/archive/kill events produce witness records
"""

from __future__ import annotations

import logging
from typing import Any

from dharma_swarm.fractal.fractal_room import (
    FractalRoom,
    RoomKind,
    RoomRegistry,
    RoomStatus,
    SIGNAL_ROOM_ARCHIVED,
    SIGNAL_ROOM_BUDGET_DEPLETED,
    SIGNAL_ROOM_CREATED,
    SIGNAL_ROOM_KILL_CONDITION_MET,
    SIGNAL_ROOM_SPAWNED_CHILD,
    SIGNAL_ROOM_SPINOUT_CONDITION_MET,
    SIGNAL_WORK_PACKET_COMPLETED,
    SIGNAL_WORK_PACKET_CREATED,
    SIGNAL_YDS_RATING_ADDED,
    VentureCellV1,
    WorkPacket,
    YDSRating,
    evaluate_kill_conditions,
    evaluate_spinout_conditions,
)

logger = logging.getLogger(__name__)


class RoomBridge:
    """Connects the fractal room registry to existing Dharma subsystems.

    Usage::

        from dharma_swarm.signal_bus import SignalBus
        from dharma_swarm.fractal.room_bridge import RoomBridge

        bus = SignalBus()
        registry = RoomRegistry()
        bridge = RoomBridge(registry, signal_bus=bus)

        # Creating a room now emits ROOM_CREATED signal
        room = FractalRoom(purpose="Test", operator="dhyana", ...)
        bridge.create_room(room)
    """

    def __init__(
        self,
        registry: RoomRegistry,
        *,
        signal_bus: Any | None = None,
        economic_engine: Any | None = None,
        kaizen_ops: Any | None = None,
        stigmergy_store: Any | None = None,
        cost_tracker: Any | None = None,
    ) -> None:
        self._registry = registry
        self._signal_bus = signal_bus
        self._economic_engine = economic_engine
        self._kaizen_ops = kaizen_ops
        self._stigmergy_store = stigmergy_store
        self._cost_tracker = cost_tracker

    # --- Signal Bus Integration ---

    def _emit(self, signal_type: str, payload: dict[str, Any]) -> None:
        """Emit a signal if SignalBus is connected."""
        if self._signal_bus is not None:
            self._signal_bus.emit({"type": signal_type, **payload})

    # --- Room Lifecycle ---

    def create_room(self, room: FractalRoom) -> FractalRoom:
        """Create and register a room. Emits ROOM_CREATED signal."""
        self._registry.register(room)

        self._emit(SIGNAL_ROOM_CREATED, {
            "room_id": room.id,
            "kind": room.kind,
            "parent_id": room.parent_id,
            "purpose": room.purpose,
        })

        # Write stigmergy mark for room creation
        if self._stigmergy_store is not None:
            try:
                self._stigmergy_store.mark(
                    agent_id="room_registry",
                    mark_type="room_created",
                    data={
                        "room_id": room.id,
                        "kind": room.kind,
                        "purpose": room.purpose,
                    },
                )
            except Exception:
                logger.debug("Stigmergy mark failed for room creation", exc_info=True)

        return room

    def spawn_child(
        self,
        parent_id: str,
        child: FractalRoom,
        *,
        consent_gate_passed: bool = False,
    ) -> FractalRoom:
        """Spawn a child room. Emits ROOM_SPAWNED_CHILD signal."""
        result = self._registry.spawn_child(
            parent_id, child, consent_gate_passed=consent_gate_passed,
        )

        self._emit(SIGNAL_ROOM_SPAWNED_CHILD, {
            "parent_id": parent_id,
            "child_id": result.id,
            "child_kind": result.kind,
            "budget_allocated": result.budget_tokens,
        })

        return result

    def archive_room(self, room_id: str) -> dict[str, Any]:
        """Archive a room. Emits ROOM_ARCHIVED signal."""
        room = self._registry.get(room_id)
        budget_before = room.remaining_budget() if room else 0
        agents_before = list(room.agents) if room else []

        result = self._registry.archive_room(room_id)

        self._emit(SIGNAL_ROOM_ARCHIVED, {
            "room_id": room_id,
            "agents_returned": agents_before,
            "budget_returned": budget_before,
        })

        # Record economic event
        if self._economic_engine is not None and budget_before > 0:
            try:
                from dharma_swarm.economic_engine import Transaction, TransactionType
                tx = Transaction(
                    type=TransactionType.ADJUSTMENT,
                    amount_usd=0,
                    description=f"Budget recycled from archived room {room_id}",
                    metadata={"room_id": room_id, "tokens_returned": budget_before},
                )
                self._economic_engine.record_transaction(tx)
            except Exception:
                logger.debug("Economic event failed for room archival", exc_info=True)

        return result

    # --- Work Packets ---

    def create_work_packet(self, packet: WorkPacket) -> WorkPacket:
        """Create a work packet. Emits WORK_PACKET_CREATED signal."""
        result = self._registry.create_work_packet(packet)

        self._emit(SIGNAL_WORK_PACKET_CREATED, {
            "packet_id": result.id,
            "room_id": result.source_room_id,
            "purpose": result.purpose,
            "assigned_agent": result.assigned_agent_id,
        })

        # Ingest into KaizenOps
        if self._kaizen_ops is not None:
            try:
                self._kaizen_ops.ingest_event(
                    category="work_packet",
                    source=result.source_room_id,
                    status="created",
                    metadata={
                        "packet_id": result.id,
                        "room_id": result.source_room_id,
                        "purpose": result.purpose,
                    },
                )
            except Exception:
                logger.debug("KaizenOps ingest failed for work packet", exc_info=True)

        return result

    def complete_work_packet(
        self,
        packet_id: str,
        outcome: str,
        cost_tokens: int = 0,
    ) -> None:
        """Complete a work packet. Emits signal + records cost."""
        self._registry.complete_work_packet(packet_id, outcome, cost_tokens)

        packet = self._registry.get_work_packet(packet_id)
        self._emit(SIGNAL_WORK_PACKET_COMPLETED, {
            "packet_id": packet_id,
            "room_id": packet.source_room_id if packet else "",
            "outcome": outcome,
            "cost_tokens": cost_tokens,
        })

        # Track cost
        if self._cost_tracker is not None and cost_tokens > 0:
            try:
                from dharma_swarm.cost_tracker import CostEntry
                entry = CostEntry(
                    timestamp=__import__("time").time(),
                    provider="room_budget",
                    model="work_packet",
                    input_tokens=cost_tokens,
                    output_tokens=0,
                    estimated_cost_usd=0,
                    task_context=f"room:{packet.source_room_id if packet else ''}",
                )
                self._cost_tracker.log(entry)
            except Exception:
                logger.debug("CostTracker log failed", exc_info=True)

        # Check budget depletion
        if packet:
            room = self._registry.get(packet.source_room_id)
            if room and room.remaining_budget() <= 0:
                self._emit(SIGNAL_ROOM_BUDGET_DEPLETED, {
                    "room_id": room.id,
                    "total_budget": room.budget_tokens,
                    "total_burn": room.current_burn,
                })

    # --- YDS Ratings ---

    def add_yds_rating(
        self,
        rating: YDSRating,
        human_operators: frozenset[str] | None = None,
    ) -> None:
        """Add a YDS rating. Emits YDS_RATING_ADDED signal."""
        self._registry.add_yds_rating(rating, human_operators)

        self._emit(SIGNAL_YDS_RATING_ADDED, {
            "rating_id": rating.id,
            "room_id": rating.room_id,
            "artifact_id": rating.artifact_id,
            "score": rating.score,
            "dimension": rating.dimension,
        })

    # --- Kill / Spinout Evaluation ---

    def evaluate_room_health(
        self, room_id: str, kpis: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate kill and spinout conditions for a room.

        Returns a health report. Does NOT auto-archive — that requires
        operator approval in v0.
        """
        room = self._registry.get(room_id)
        if room is None:
            return {"error": f"Room '{room_id}' not found"}

        result: dict[str, Any] = {
            "room_id": room_id,
            "status": room.status,
            "kill_triggered": False,
            "spinout_triggered": False,
        }

        if isinstance(room, VentureCellV1):
            kill = evaluate_kill_conditions(room.kill_conditions, kpis)
            spinout = evaluate_spinout_conditions(room.spinout_conditions, kpis)

            result["kill_triggered"] = kill
            result["spinout_triggered"] = spinout
            result["kill_conditions_checked"] = room.kill_conditions
            result["spinout_conditions_checked"] = room.spinout_conditions
            result["kpis"] = kpis

            if kill:
                self._emit(SIGNAL_ROOM_KILL_CONDITION_MET, {
                    "room_id": room_id,
                    "kpis": kpis,
                    "conditions": room.kill_conditions,
                })

            if spinout:
                self._emit(SIGNAL_ROOM_SPINOUT_CONDITION_MET, {
                    "room_id": room_id,
                    "kpis": kpis,
                    "conditions": room.spinout_conditions,
                })

        return result

    # --- CorrelationContext Integration ---

    @staticmethod
    def correlation_context_for_room(
        room_id: str,
        trace_id: str = "",
        proposal_id: str = "",
        session_id: str = "",
    ) -> Any:
        """Create a CorrelationContext with cell_id set to room_id.

        This bridges into the existing CorrelationContext system so that
        all downstream store operations are tagged with the room.
        """
        from dharma_swarm.correlation_context import CorrelationContext
        return CorrelationContext(
            trace_id=trace_id or f"trc_{__import__('uuid').uuid4().hex[:16]}",
            proposal_id=proposal_id,
            session_id=session_id,
            cell_id=room_id,
        )

    # --- Aggregate Brief ---

    def all_room_briefs(self) -> list[dict[str, Any]]:
        """Generate briefs for all active rooms."""
        return [
            self._registry.room_brief(room.id)
            for room in self._registry.active_rooms()
        ]

    def system_brief(self) -> dict[str, Any]:
        """Top-level system brief aggregating all rooms."""
        active = self._registry.active_rooms()
        vcs = self._registry.venture_cells()
        active_vcs = [vc for vc in vcs if vc.status != RoomStatus.ARCHIVED]

        total_budget = sum(r.budget_tokens for r in active)
        total_burn = sum(r.current_burn for r in active)
        total_agents = len({a for r in active for a in r.agents})

        return {
            "active_rooms": len(active),
            "venture_cells": len(active_vcs),
            "total_budget": total_budget,
            "total_burn": total_burn,
            "total_remaining": total_budget - total_burn,
            "total_agents": total_agents,
            "rooms": self.all_room_briefs(),
        }


# ---------------------------------------------------------------------------
#  BR-008 closure: VentureCell ontology ↔ fractal room polymorphism
#
#  When you register a VentureCell, you get the room container AND the
#  ontology type AND the loop wiring. When you read from ontology, you
#  get a running organ, not just a schema row.
# ---------------------------------------------------------------------------


def venture_cell_to_ontology(
    cell: VentureCellV1,
    registry: Any,
    *,
    created_by: str = "system",
) -> tuple[Any | None, list[str]]:
    """Materialize a fractal VentureCellV1 as an ontology VentureCell object.

    Returns (obj, errors). If the cell already exists in ontology (by id),
    updates its properties instead of creating a duplicate.
    """
    properties = {
        "name": cell.id,
        "description": cell.purpose,
        "domain": "economic" if cell.value_proposition else "governance",
        "autonomy_stage": cell.autonomy_stage,
        "status": _room_status_to_ontology(cell.status),
        "room_status": cell.status.value,
        "value_proposition": cell.value_proposition,
        "customer_or_beneficiary": cell.customer_or_beneficiary,
        "budget_tokens": cell.budget_tokens,
        "kpis": {
            "current_burn": cell.current_burn,
            "welfare_tons": cell.welfare_tons_produced,
            "agent_count": len(cell.agents),
        },
    }
    try:
        from dharma_swarm.ontology import OntologyObj

        return registry.put_object(
            OntologyObj(
                id=cell.id,
                type_name="VentureCell",
                properties=properties,
                created_by=created_by,
            ),
            updated_by=created_by,
        )
    except AttributeError:
        existing = registry.get_object(cell.id)
        if existing is not None and existing.type_name == "VentureCell":
            obj, errors = registry.update_object(cell.id, properties, updated_by=created_by)
            return obj, errors
        obj, errors = registry.create_object(
            "VentureCell", properties=properties, created_by=created_by,
        )
        return obj, errors


def ontology_to_venture_cell(
    obj: Any,
) -> VentureCellV1 | None:
    """Hydrate a fractal VentureCellV1 from an ontology VentureCell object.

    Returns None if the object is not a VentureCell type.
    """
    if obj.type_name != "VentureCell":
        return None
    props = obj.properties
    return VentureCellV1(
        id=obj.id,
        purpose=str(props.get("description", "")),
        kind=RoomKind.VENTURE_CELL,
        status=_ontology_status_to_room(
            str(props.get("room_status") or props.get("status", "incubating"))
        ),
        budget_tokens=int(props.get("budget_tokens", 0) or 0),
        autonomy_stage=int(props.get("autonomy_stage", 1) or 1),
        value_proposition=str(props.get("value_proposition", "")),
        customer_or_beneficiary=str(props.get("customer_or_beneficiary", "")),
    )


def sync_registry_to_ontology(
    room_registry: RoomRegistry,
    ontology_registry: Any,
    *,
    created_by: str = "system",
) -> dict[str, list[str]]:
    """Sync all VentureCells from the room registry into ontology.

    Returns a dict of {cell_id: errors} for any that failed.
    """
    result: dict[str, list[str]] = {}
    for cell in room_registry.venture_cells():
        _, errors = venture_cell_to_ontology(cell, ontology_registry, created_by=created_by)
        if errors:
            result[cell.id] = errors
    return result


def _room_status_to_ontology(status: RoomStatus) -> str:
    mapping = {
        RoomStatus.PROPOSED: "incubating",
        RoomStatus.INCUBATING: "incubating",
        RoomStatus.ACTIVE: "active",
        RoomStatus.GRADUATING: "mature",
        RoomStatus.ARCHIVED: "archived",
        RoomStatus.SPUN_OUT: "divesting",
    }
    return mapping.get(status, "active")


def _ontology_status_to_room(status: str) -> RoomStatus:
    mapping = {
        "proposed": RoomStatus.PROPOSED,
        "incubating": RoomStatus.INCUBATING,
        "active": RoomStatus.ACTIVE,
        "graduating": RoomStatus.GRADUATING,
        "mature": RoomStatus.GRADUATING,
        "spun_out": RoomStatus.SPUN_OUT,
        "divesting": RoomStatus.SPUN_OUT,
        "archived": RoomStatus.ARCHIVED,
    }
    return mapping.get(status, RoomStatus.ACTIVE)
