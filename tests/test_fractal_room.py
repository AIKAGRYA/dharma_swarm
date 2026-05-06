"""Comprehensive tests for fractal room / venture cell system.

Proves the Five Laws of Fractal Rooms:
  Law 1: Recursive Self-Similarity
  Law 2: Economic Accountability
  Law 3: Governed Autonomy
  Law 4: Knowledge Compounding
  Law 5: Dissolution with Recycling

Plus integration tests for CorrelationContext, SignalBus, RoomBridge.
"""

from __future__ import annotations

import json
import pytest

from dharma_swarm.fractal.fractal_room import (
    MAX_NESTING_DEPTH,
    FractalRoom,
    RoomKind,
    RoomRegistry,
    RoomStatus,
    RoomValidationError,
    VentureCellV1,
    WorkPacket,
    YDSRating,
    evaluate_kill_conditions,
    evaluate_spinout_conditions,
    validate_room,
    validate_venture_cell,
    validate_work_packet,
    validate_yds_rating,
)
from dharma_swarm.fractal.room_bridge import RoomBridge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _core_room(**overrides) -> FractalRoom:
    defaults = {
        "kind": RoomKind.OPERATIONS,
        "purpose": "Core operations",
        "operator": "dhyana",
        "budget_tokens": 10000,
        "memory_namespace": "core",
    }
    defaults.update(overrides)
    return FractalRoom(**defaults)


def _venture_cell(**overrides) -> VentureCellV1:
    defaults = {
        "kind": RoomKind.VENTURE_CELL,
        "purpose": "Revenue wedge",
        "operator": "dhyana",
        "budget_tokens": 5000,
        "revenue_target": 1000,
        "customer_or_beneficiary": "developer teams",
        "value_proposition": "AI-assisted code review",
        "kill_conditions": ["no_revenue_after_60_days"],
        "memory_namespace": "revenue_wedge",
    }
    defaults.update(overrides)
    return VentureCellV1(**defaults)


# ===================================================================
# LAW 1: Recursive Self-Similarity
# ===================================================================


class TestLaw1RecursiveSelfSimilarity:
    """Every room has identical structure (Beer VSM isomorphism)."""

    def test_room_has_all_six_components(self):
        room = _core_room()
        # S5 — Identity
        assert room.purpose
        assert room.operator
        # S1 — Operations (roster)
        assert isinstance(room.agents, list)
        # S3 — Control (economy + law)
        assert room.budget_tokens >= 0
        assert isinstance(room.gates, list)
        # S4 — Intelligence (memory)
        assert isinstance(room.report_paths, dict)
        assert room.memory_namespace
        # S2 — Coordination
        assert isinstance(room.signal_bus_topics, list)

    def test_child_room_has_same_schema(self):
        """Child room validates same fields as parent."""
        registry = RoomRegistry()
        parent = _core_room(id="parent")
        registry.register(parent)

        child = FractalRoom(
            id="child",
            kind=RoomKind.OPERATIONS,
            parent_id="parent",
            purpose="Sub-operations",
            operator="dhyana",
            budget_tokens=3000,
            forbidden_work=list(parent.forbidden_work),
            approval_required_for=list(parent.approval_required_for),
            memory_namespace="core/child",
        )
        registry.register(child)

        # Both have identical field names
        parent_fields = set(parent.__dataclass_fields__.keys())
        child_fields = set(child.__dataclass_fields__.keys())
        assert parent_fields == child_fields

    def test_venture_cell_extends_room(self):
        """VentureCell has all Room fields plus business/lifecycle."""
        vc = _venture_cell()

        # Has all FractalRoom fields
        room_fields = set(FractalRoom.__dataclass_fields__.keys())
        vc_fields = set(vc.__dataclass_fields__.keys())
        assert room_fields.issubset(vc_fields)

        # Plus venture-specific fields
        extra = vc_fields - room_fields
        assert "customer_or_beneficiary" in extra
        assert "kill_conditions" in extra
        assert "spinout_conditions" in extra
        assert "jagat_kalyan_constraint" in extra
        assert "welfare_tons_produced" in extra
        assert "autonomy_stage" in extra

    def test_room_json_roundtrip(self):
        room = _core_room(agents=["agent1", "agent2"])
        data = room.to_dict()
        restored = FractalRoom.from_dict(data)
        assert restored.id == room.id
        assert restored.purpose == room.purpose
        assert restored.agents == room.agents

    def test_venture_cell_json_roundtrip(self):
        vc = _venture_cell()
        data = vc.to_dict()
        restored = VentureCellV1.from_dict(data)
        assert restored.customer_or_beneficiary == vc.customer_or_beneficiary
        assert restored.kill_conditions == vc.kill_conditions


# ===================================================================
# LAW 2: Economic Accountability
# ===================================================================


class TestLaw2EconomicAccountability:
    """VentureCells must have revenue targets + kill conditions."""

    def test_venture_cell_requires_revenue_target(self):
        with pytest.raises(RoomValidationError, match="revenue_target"):
            validate_venture_cell(_venture_cell(revenue_target=0))

    def test_venture_cell_requires_customer(self):
        with pytest.raises(RoomValidationError, match="customer_or_beneficiary"):
            validate_venture_cell(_venture_cell(customer_or_beneficiary=""))

    def test_venture_cell_requires_kill_conditions(self):
        with pytest.raises(RoomValidationError, match="kill_condition"):
            validate_venture_cell(_venture_cell(kill_conditions=[]))

    def test_budget_conservation(self):
        """Child budgets sum <= parent budget."""
        registry = RoomRegistry()
        parent = _core_room(id="parent", budget_tokens=10000)
        registry.register(parent)

        # First child takes 6000
        child1 = _core_room(
            id="c1", parent_id="parent", budget_tokens=6000,
            forbidden_work=list(parent.forbidden_work),
            approval_required_for=list(parent.approval_required_for),
            memory_namespace="core/c1",
        )
        registry.register(child1)
        assert parent.remaining_budget() == 4000

        # Second child tries to take 5000 — should fail
        child2 = _core_room(
            id="c2", parent_id="parent", budget_tokens=5000,
            forbidden_work=list(parent.forbidden_work),
            approval_required_for=list(parent.approval_required_for),
            memory_namespace="core/c2",
        )
        with pytest.raises(RoomValidationError, match="exceeds parent"):
            registry.register(child2)

    def test_kill_condition_evaluation_triggered(self):
        kpis = {"revenue_usd": 0, "days_active": 90}
        assert evaluate_kill_conditions(["no_revenue_after_60_days"], kpis) is True

    def test_kill_condition_not_triggered(self):
        kpis = {"revenue_usd": 500, "days_active": 90}
        assert evaluate_kill_conditions(["no_revenue_after_60_days"], kpis) is False

    def test_kill_burn_exceeds_revenue(self):
        kpis = {"burn_usd": 900, "revenue_usd": 100}
        assert evaluate_kill_conditions(["burn_exceeds_3x_revenue"], kpis) is True

    def test_spinout_condition_all_met(self):
        kpis = {"revenue_usd": 1000, "burn_usd": 800, "paying_customers": 5}
        assert evaluate_spinout_conditions(
            ["revenue_covers_burn", "3_paying_customers"], kpis,
        ) is True

    def test_spinout_condition_partial(self):
        kpis = {"revenue_usd": 1000, "burn_usd": 800, "paying_customers": 1}
        assert evaluate_spinout_conditions(
            ["revenue_covers_burn", "3_paying_customers"], kpis,
        ) is False

    def test_spinout_empty_conditions(self):
        assert evaluate_spinout_conditions([], {}) is False

    def test_autonomy_stage_bounds(self):
        with pytest.raises(RoomValidationError, match="autonomy_stage"):
            validate_venture_cell(_venture_cell(autonomy_stage=0))
        with pytest.raises(RoomValidationError, match="autonomy_stage"):
            validate_venture_cell(_venture_cell(autonomy_stage=6))

    def test_work_packet_cost_ceiling_enforcement(self):
        """WorkPacket cost can't exceed room remaining budget."""
        registry = RoomRegistry()
        room = _core_room(id="r1", budget_tokens=100)
        registry.register(room)

        packet = WorkPacket(
            source_room_id="r1",
            purpose="test",
            cost_ceiling=200,
        )
        with pytest.raises(RoomValidationError, match="cost_ceiling"):
            registry.create_work_packet(packet)


# ===================================================================
# LAW 3: Governed Autonomy
# ===================================================================


class TestLaw3GovernedAutonomy:
    """forbidden_work inherits additively, approvals propagate."""

    def test_forbidden_work_inherits_additively(self):
        registry = RoomRegistry()
        parent = _core_room(
            id="parent",
            forbidden_work=["dashboard_expansion", "live_autonomy"],
            approval_required_for=["merge"],
        )
        registry.register(parent)

        # Child must include parent's forbidden_work
        child = _core_room(
            id="child", parent_id="parent", budget_tokens=3000,
            forbidden_work=["dashboard_expansion", "live_autonomy", "ontology_refactor"],
            approval_required_for=["merge"],
            memory_namespace="core/child",
        )
        registry.register(child)
        assert "dashboard_expansion" in child.forbidden_work
        assert "live_autonomy" in child.forbidden_work
        assert "ontology_refactor" in child.forbidden_work

    def test_child_cannot_remove_parent_forbidden_work(self):
        registry = RoomRegistry()
        parent = _core_room(
            id="parent",
            forbidden_work=["dashboard_expansion", "live_autonomy"],
        )
        registry.register(parent)

        child = _core_room(
            id="child", parent_id="parent", budget_tokens=3000,
            forbidden_work=["dashboard_expansion"],  # missing live_autonomy
            memory_namespace="core/child",
        )
        with pytest.raises(RoomValidationError, match="forbidden_work"):
            registry.register(child)

    def test_child_cannot_remove_parent_approval_requirement(self):
        registry = RoomRegistry()
        parent = _core_room(
            id="parent",
            approval_required_for=["merge", "external_outreach"],
        )
        registry.register(parent)

        child = _core_room(
            id="child", parent_id="parent", budget_tokens=3000,
            forbidden_work=list(parent.forbidden_work),
            approval_required_for=["merge"],  # missing external_outreach
            memory_namespace="core/child",
        )
        with pytest.raises(RoomValidationError, match="approval_required_for"):
            registry.register(child)

    def test_child_cannot_exceed_parent_budget(self):
        registry = RoomRegistry()
        parent = _core_room(id="parent", budget_tokens=5000)
        registry.register(parent)

        child = _core_room(
            id="child", parent_id="parent", budget_tokens=6000,
            forbidden_work=list(parent.forbidden_work),
            approval_required_for=list(parent.approval_required_for),
            memory_namespace="core/child",
        )
        with pytest.raises(RoomValidationError, match="exceeds parent"):
            registry.register(child)

    def test_spawn_requires_consent_gate(self):
        registry = RoomRegistry()
        parent = _core_room(id="parent")
        registry.register(parent)

        child = _core_room(id="child", budget_tokens=2000)
        with pytest.raises(RoomValidationError, match="CONSENT"):
            registry.spawn_child("parent", child, consent_gate_passed=False)

    def test_spawn_with_consent_succeeds(self):
        registry = RoomRegistry()
        parent = _core_room(
            id="parent",
            forbidden_work=["live_autonomy"],
            approval_required_for=["merge"],
        )
        registry.register(parent)

        child = _core_room(id="child", budget_tokens=2000)
        result = registry.spawn_child("parent", child, consent_gate_passed=True)
        assert result.parent_id == "parent"
        assert "live_autonomy" in result.forbidden_work
        assert "merge" in result.approval_required_for

    def test_spawn_auto_inherits_constraints(self):
        """spawn_child automatically unions parent constraints."""
        registry = RoomRegistry()
        parent = _core_room(
            id="parent",
            forbidden_work=["live_autonomy"],
            approval_required_for=["merge", "push"],
        )
        registry.register(parent)

        child = FractalRoom(
            id="child", purpose="test", operator="dhyana",
            budget_tokens=2000,
            forbidden_work=["ontology_refactor"],
            approval_required_for=["budget_increase"],
        )
        result = registry.spawn_child("parent", child, consent_gate_passed=True)

        assert set(result.forbidden_work) == {"live_autonomy", "ontology_refactor"}
        assert set(result.approval_required_for) == {"merge", "push", "budget_increase"}

    def test_work_packet_inherits_room_forbidden(self):
        registry = RoomRegistry()
        room = _core_room(
            id="r1",
            forbidden_work=["live_autonomy", "dashboard_expansion"],
        )
        registry.register(room)

        packet = WorkPacket(
            source_room_id="r1",
            purpose="test",
            forbidden_mutations=["live_autonomy"],  # missing dashboard_expansion
        )
        with pytest.raises(RoomValidationError, match="forbidden_work"):
            registry.create_work_packet(packet)

    def test_work_packet_agent_must_be_in_roster(self):
        registry = RoomRegistry()
        room = _core_room(id="r1", agents=["agent1", "agent2"])
        registry.register(room)

        packet = WorkPacket(
            source_room_id="r1",
            purpose="test",
            assigned_agent_id="agent3",
            forbidden_mutations=list(room.forbidden_work),
        )
        with pytest.raises(RoomValidationError, match="not in room roster"):
            registry.create_work_packet(packet)


# ===================================================================
# LAW 4: Knowledge Compounding
# ===================================================================


class TestLaw4KnowledgeCompounding:
    """work → outcome → review → playbook → better work."""

    def test_work_packet_links_to_room(self):
        packet = WorkPacket(source_room_id="room_abc", purpose="test")
        assert packet.source_room_id == "room_abc"

    def test_yds_rating_links_to_room(self):
        rating = YDSRating(
            room_id="room_abc",
            artifact_id="art_123",
            rater="dhyana",
            score=8,
        )
        assert rating.room_id == "room_abc"

    def test_yds_rating_valid_dimensions(self):
        for dim in YDSRating.VALID_DIMENSIONS:
            rating = YDSRating(
                room_id="r1", artifact_id="a1", rater="dhyana",
                score=7, dimension=dim,
            )
            validate_yds_rating(rating)

    def test_yds_invalid_dimension_rejected(self):
        rating = YDSRating(
            room_id="r1", artifact_id="a1", rater="dhyana",
            score=7, dimension="invalid",
        )
        with pytest.raises(RoomValidationError, match="dimension"):
            validate_yds_rating(rating)

    def test_yds_requires_human_rater(self):
        rating = YDSRating(
            room_id="r1", artifact_id="a1", rater="agent_bot",
            score=7,
        )
        with pytest.raises(RoomValidationError, match="human operator"):
            validate_yds_rating(rating, human_operators=frozenset({"dhyana"}))

    def test_yds_score_bounds(self):
        with pytest.raises(RoomValidationError, match="1-10"):
            validate_yds_rating(YDSRating(
                room_id="r1", artifact_id="a1", rater="dhyana", score=0,
            ))
        with pytest.raises(RoomValidationError, match="1-10"):
            validate_yds_rating(YDSRating(
                room_id="r1", artifact_id="a1", rater="dhyana", score=11,
            ))

    def test_room_brief_generation(self):
        registry = RoomRegistry()
        room = _core_room(id="r1", agents=["agent1"])
        registry.register(room)

        packet = WorkPacket(
            source_room_id="r1", purpose="task 1",
            forbidden_mutations=list(room.forbidden_work),
        )
        registry.create_work_packet(packet)

        brief = registry.room_brief("r1")
        assert brief["room_id"] == "r1"
        assert brief["work_packets"]["total"] == 1
        assert brief["roster"]["count"] == 1

    def test_room_brief_includes_venture_cell_fields(self):
        registry = RoomRegistry()
        vc = _venture_cell(id="vc1")
        registry.register(vc)

        brief = registry.room_brief("vc1")
        assert "venture_cell" in brief
        assert brief["venture_cell"]["customer"] == "developer teams"
        assert brief["venture_cell"]["revenue_target"] == 1000

    def test_work_packet_complete_records_outcome(self):
        registry = RoomRegistry()
        room = _core_room(id="r1")
        registry.register(room)

        packet = WorkPacket(
            source_room_id="r1", purpose="task",
            forbidden_mutations=list(room.forbidden_work),
        )
        registry.create_work_packet(packet)
        registry.complete_work_packet(packet.id, "success", cost_tokens=50)

        completed = registry.get_work_packet(packet.id)
        assert completed.status == "completed"
        assert completed.outcome == "success"
        assert completed.completed_at is not None


# ===================================================================
# LAW 5: Dissolution with Recycling
# ===================================================================


class TestLaw5DissolutionWithRecycling:
    """Archived rooms return agents + budget to parent."""

    def test_archive_returns_agents_to_parent(self):
        registry = RoomRegistry()
        parent = _core_room(id="parent", agents=["agent1"])
        registry.register(parent)

        child = FractalRoom(
            id="child", purpose="test", operator="dhyana",
            budget_tokens=3000,
            agents=["agent2", "agent3"],
            memory_namespace="core/child",
        )
        registry.spawn_child("parent", child, consent_gate_passed=True)

        registry.archive_room("child")

        assert "agent2" in parent.agents
        assert "agent3" in parent.agents
        assert registry.get("child").status == RoomStatus.ARCHIVED

    def test_archive_returns_budget_to_parent(self):
        registry = RoomRegistry()
        parent = _core_room(id="parent", budget_tokens=10000)
        registry.register(parent)

        child = FractalRoom(
            id="child", purpose="test", operator="dhyana",
            budget_tokens=4000,
            memory_namespace="core/child",
        )
        registry.spawn_child("parent", child, consent_gate_passed=True)

        assert parent.remaining_budget() == 6000

        registry.archive_room("child")

        # Parent should get budget back (burn reduced)
        assert parent.remaining_budget() == 10000

    def test_archive_preserves_knowledge(self):
        registry = RoomRegistry()
        room = _core_room(id="r1")
        registry.register(room)

        packet = WorkPacket(
            source_room_id="r1", purpose="important work",
            forbidden_mutations=list(room.forbidden_work),
        )
        registry.create_work_packet(packet)
        registry.complete_work_packet(packet.id, "valuable outcome")

        registry.archive_room("r1")

        knowledge = registry.archived_knowledge("r1")
        assert knowledge is not None
        assert len(knowledge["work_packets"]) == 1
        assert knowledge["work_packets"][0]["outcome"] == "valuable outcome"

    def test_archived_room_rejects_new_work(self):
        registry = RoomRegistry()
        room = _core_room(id="r1")
        registry.register(room)
        registry.archive_room("r1")

        packet = WorkPacket(
            source_room_id="r1", purpose="new work",
            forbidden_mutations=list(room.forbidden_work),
        )
        with pytest.raises(RoomValidationError, match="archived"):
            registry.create_work_packet(packet)

    def test_archive_recursive_children(self):
        registry = RoomRegistry()
        root = _core_room(id="root", budget_tokens=10000)
        registry.register(root)

        mid = FractalRoom(
            id="mid", purpose="middle", operator="dhyana",
            budget_tokens=5000, memory_namespace="core/mid",
        )
        registry.spawn_child("root", mid, consent_gate_passed=True)

        leaf = FractalRoom(
            id="leaf", purpose="leaf", operator="dhyana",
            budget_tokens=2000, memory_namespace="core/mid/leaf",
        )
        registry.spawn_child("mid", leaf, consent_gate_passed=True)

        result = registry.archive_room("mid")
        assert registry.get("leaf").status == RoomStatus.ARCHIVED
        assert registry.get("mid").status == RoomStatus.ARCHIVED
        assert len(result["children_archived"]) == 1


# ===================================================================
# Additional Validation
# ===================================================================


class TestAdditionalValidation:

    def test_max_nesting_depth(self):
        registry = RoomRegistry()
        parent = _core_room(id="d0", budget_tokens=100000)
        registry.register(parent)

        prev_id = "d0"
        for i in range(1, MAX_NESTING_DEPTH + 1):
            child = FractalRoom(
                id=f"d{i}", purpose=f"depth {i}", operator="dhyana",
                budget_tokens=1000, memory_namespace=f"ns/d{i}",
            )
            registry.spawn_child(prev_id, child, consent_gate_passed=True)
            prev_id = f"d{i}"

        # One more should fail
        too_deep = FractalRoom(
            id="too_deep", purpose="too deep", operator="dhyana",
            budget_tokens=100, memory_namespace="ns/too_deep",
        )
        with pytest.raises(RoomValidationError, match="Nesting depth"):
            registry.spawn_child(prev_id, too_deep, consent_gate_passed=True)

    def test_room_id_uniqueness(self):
        registry = RoomRegistry()
        room1 = _core_room(id="same_id")
        registry.register(room1)

        room2 = _core_room(id="same_id")
        with pytest.raises(RoomValidationError, match="already exists"):
            registry.register(room2)

    def test_operations_room_no_revenue_target_needed(self):
        room = _core_room(revenue_target=0)
        validate_room(room)  # Should not raise

    def test_empty_purpose_rejected(self):
        with pytest.raises(RoomValidationError, match="purpose"):
            validate_room(_core_room(purpose=""))

    def test_empty_operator_rejected(self):
        with pytest.raises(RoomValidationError, match="operator"):
            validate_room(_core_room(operator=""))

    def test_negative_budget_rejected(self):
        with pytest.raises(RoomValidationError, match="non-negative"):
            validate_room(_core_room(budget_tokens=-1))

    def test_venture_cell_kind_enforced(self):
        vc = _venture_cell(kind=RoomKind.OPERATIONS)
        with pytest.raises(RoomValidationError, match="venture_cell"):
            validate_venture_cell(vc)

    def test_registry_active_rooms(self):
        registry = RoomRegistry()
        r1 = _core_room(id="r1")
        r2 = _core_room(id="r2")
        registry.register(r1)
        registry.register(r2)

        assert len(registry.active_rooms()) == 2
        registry.archive_room("r1")
        assert len(registry.active_rooms()) == 1

    def test_registry_venture_cells(self):
        registry = RoomRegistry()
        room = _core_room(id="r1")
        vc = _venture_cell(id="vc1")
        registry.register(room)
        registry.register(vc)

        vcs = registry.venture_cells()
        assert len(vcs) == 1
        assert vcs[0].id == "vc1"

    def test_registry_json_serialization(self):
        registry = RoomRegistry()
        room = _core_room(id="r1")
        registry.register(room)
        data = json.loads(registry.to_json())
        assert "r1" in data["rooms"]


# ===================================================================
# Integration: CorrelationContext cell_id
# ===================================================================


class TestCorrelationContextCellId:

    def test_cell_id_field_exists(self):
        from dharma_swarm.correlation_context import CorrelationContext
        ctx = CorrelationContext()
        assert ctx.cell_id == ""

    def test_cell_id_in_constructor(self):
        from dharma_swarm.correlation_context import CorrelationContext
        ctx = CorrelationContext(trace_id="trc_test", cell_id="room_abc")
        assert ctx.cell_id == "room_abc"

    def test_with_cell_returns_new_context(self):
        from dharma_swarm.correlation_context import CorrelationContext
        ctx = CorrelationContext(trace_id="trc_test", proposal_id="p1")
        ctx2 = ctx.with_cell("room_xyz")
        assert ctx2.cell_id == "room_xyz"
        assert ctx2.trace_id == ctx.trace_id
        assert ctx2.proposal_id == ctx.proposal_id

    def test_with_cell_preserves_immutability(self):
        from dharma_swarm.correlation_context import CorrelationContext
        ctx = CorrelationContext(trace_id="trc_test")
        ctx2 = ctx.with_cell("room_abc")
        assert ctx.cell_id == ""
        assert ctx2.cell_id == "room_abc"

    def test_as_dict_includes_cell_id_when_set(self):
        from dharma_swarm.correlation_context import CorrelationContext
        ctx = CorrelationContext(trace_id="trc_test", cell_id="room_abc")
        d = ctx.as_dict()
        assert d["cell_id"] == "room_abc"

    def test_as_dict_omits_cell_id_when_empty(self):
        from dharma_swarm.correlation_context import CorrelationContext
        ctx = CorrelationContext(trace_id="trc_test")
        d = ctx.as_dict()
        assert "cell_id" not in d

    def test_correlation_scope_sync_with_cell_id(self):
        from dharma_swarm.correlation_context import (
            correlation_scope_sync,
            get_correlation,
        )
        with correlation_scope_sync(
            trace_id="trc_test", cell_id="room_abc",
        ) as ctx:
            assert ctx.cell_id == "room_abc"
            assert get_correlation().cell_id == "room_abc"
        assert get_correlation().cell_id == ""

    def test_with_proposal_preserves_cell_id(self):
        from dharma_swarm.correlation_context import CorrelationContext
        ctx = CorrelationContext(
            trace_id="trc_test", cell_id="room_abc",
        )
        ctx2 = ctx.with_proposal("prop_xyz")
        assert ctx2.cell_id == "room_abc"
        assert ctx2.proposal_id == "prop_xyz"


# ===================================================================
# Integration: SignalBus
# ===================================================================


class TestSignalBusIntegration:

    def test_room_created_emits_signal(self):
        from dharma_swarm.signal_bus import SignalBus
        from dharma_swarm.fractal.fractal_room import SIGNAL_ROOM_CREATED

        bus = SignalBus()
        signals = []
        bus.subscribe(SIGNAL_ROOM_CREATED, lambda e: signals.append(e))

        registry = RoomRegistry()
        bridge = RoomBridge(registry, signal_bus=bus)
        room = _core_room(id="r1")
        bridge.create_room(room)

        assert len(signals) == 1
        assert signals[0]["room_id"] == "r1"
        assert signals[0]["type"] == SIGNAL_ROOM_CREATED

    def test_room_archived_emits_signal(self):
        from dharma_swarm.signal_bus import SignalBus
        from dharma_swarm.fractal.fractal_room import SIGNAL_ROOM_ARCHIVED

        bus = SignalBus()
        signals = []
        bus.subscribe(SIGNAL_ROOM_ARCHIVED, lambda e: signals.append(e))

        registry = RoomRegistry()
        bridge = RoomBridge(registry, signal_bus=bus)
        room = _core_room(id="r1")
        bridge.create_room(room)
        bridge.archive_room("r1")

        assert len(signals) == 1
        assert signals[0]["room_id"] == "r1"

    def test_spawn_child_emits_signal(self):
        from dharma_swarm.signal_bus import SignalBus
        from dharma_swarm.fractal.fractal_room import SIGNAL_ROOM_SPAWNED_CHILD

        bus = SignalBus()
        signals = []
        bus.subscribe(SIGNAL_ROOM_SPAWNED_CHILD, lambda e: signals.append(e))

        registry = RoomRegistry()
        bridge = RoomBridge(registry, signal_bus=bus)

        parent = _core_room(id="parent")
        bridge.create_room(parent)

        child = FractalRoom(
            id="child", purpose="test", operator="dhyana",
            budget_tokens=2000,
        )
        bridge.spawn_child("parent", child, consent_gate_passed=True)

        assert len(signals) == 1
        assert signals[0]["parent_id"] == "parent"
        assert signals[0]["child_id"] == "child"

    def test_work_packet_lifecycle_signals(self):
        from dharma_swarm.signal_bus import SignalBus
        from dharma_swarm.fractal.fractal_room import (
            SIGNAL_WORK_PACKET_COMPLETED,
            SIGNAL_WORK_PACKET_CREATED,
        )

        bus = SignalBus()
        created_signals = []
        completed_signals = []
        bus.subscribe(SIGNAL_WORK_PACKET_CREATED, lambda e: created_signals.append(e))
        bus.subscribe(SIGNAL_WORK_PACKET_COMPLETED, lambda e: completed_signals.append(e))

        registry = RoomRegistry()
        bridge = RoomBridge(registry, signal_bus=bus)
        room = _core_room(id="r1")
        bridge.create_room(room)

        packet = WorkPacket(
            source_room_id="r1", purpose="work",
            forbidden_mutations=list(room.forbidden_work),
        )
        bridge.create_work_packet(packet)
        assert len(created_signals) == 1

        bridge.complete_work_packet(packet.id, "done", cost_tokens=100)
        assert len(completed_signals) == 1
        assert completed_signals[0]["outcome"] == "done"

    def test_budget_depleted_signal(self):
        from dharma_swarm.signal_bus import SignalBus
        from dharma_swarm.fractal.fractal_room import SIGNAL_ROOM_BUDGET_DEPLETED

        bus = SignalBus()
        signals = []
        bus.subscribe(SIGNAL_ROOM_BUDGET_DEPLETED, lambda e: signals.append(e))

        registry = RoomRegistry()
        bridge = RoomBridge(registry, signal_bus=bus)
        room = _core_room(id="r1", budget_tokens=100)
        bridge.create_room(room)

        packet = WorkPacket(
            source_room_id="r1", purpose="big job",
            forbidden_mutations=list(room.forbidden_work),
        )
        bridge.create_work_packet(packet)
        bridge.complete_work_packet(packet.id, "done", cost_tokens=100)

        assert len(signals) == 1
        assert signals[0]["room_id"] == "r1"

    def test_kill_condition_emits_signal(self):
        from dharma_swarm.signal_bus import SignalBus
        from dharma_swarm.fractal.fractal_room import SIGNAL_ROOM_KILL_CONDITION_MET

        bus = SignalBus()
        signals = []
        bus.subscribe(SIGNAL_ROOM_KILL_CONDITION_MET, lambda e: signals.append(e))

        registry = RoomRegistry()
        bridge = RoomBridge(registry, signal_bus=bus)
        vc = _venture_cell(id="vc1")
        bridge.create_room(vc)

        kpis = {"revenue_usd": 0, "days_active": 90}
        result = bridge.evaluate_room_health("vc1", kpis)

        assert result["kill_triggered"] is True
        assert len(signals) == 1

    def test_yds_rating_emits_signal(self):
        from dharma_swarm.signal_bus import SignalBus
        from dharma_swarm.fractal.fractal_room import SIGNAL_YDS_RATING_ADDED

        bus = SignalBus()
        signals = []
        bus.subscribe(SIGNAL_YDS_RATING_ADDED, lambda e: signals.append(e))

        registry = RoomRegistry()
        bridge = RoomBridge(registry, signal_bus=bus)

        rating = YDSRating(
            room_id="r1", artifact_id="a1", rater="dhyana", score=8,
        )
        bridge.add_yds_rating(rating)

        assert len(signals) == 1
        assert signals[0]["score"] == 8


# ===================================================================
# Integration: RoomBridge
# ===================================================================


class TestRoomBridge:

    def test_bridge_creates_correlation_context(self):
        ctx = RoomBridge.correlation_context_for_room("room_abc")
        assert ctx.cell_id == "room_abc"
        assert ctx.trace_id.startswith("trc_")

    def test_bridge_system_brief(self):
        registry = RoomRegistry()
        bridge = RoomBridge(registry)

        room1 = _core_room(id="r1", agents=["a1"])
        room2 = _core_room(id="r2", agents=["a2", "a3"])
        bridge.create_room(room1)
        bridge.create_room(room2)

        brief = bridge.system_brief()
        assert brief["active_rooms"] == 2
        assert brief["total_agents"] == 3
        assert len(brief["rooms"]) == 2

    def test_bridge_all_room_briefs(self):
        registry = RoomRegistry()
        bridge = RoomBridge(registry)

        bridge.create_room(_core_room(id="r1"))
        bridge.create_room(_core_room(id="r2"))

        briefs = bridge.all_room_briefs()
        assert len(briefs) == 2

    def test_bridge_no_signal_bus_doesnt_crash(self):
        """RoomBridge works fine without SignalBus (optional)."""
        registry = RoomRegistry()
        bridge = RoomBridge(registry)  # no signal_bus

        room = _core_room(id="r1")
        bridge.create_room(room)
        bridge.archive_room("r1")

    def test_bridge_evaluate_health_non_vc(self):
        registry = RoomRegistry()
        bridge = RoomBridge(registry)

        room = _core_room(id="r1")
        bridge.create_room(room)

        result = bridge.evaluate_room_health("r1", {})
        assert result["kill_triggered"] is False
        assert result["spinout_triggered"] is False

    def test_bridge_evaluate_health_spinout(self):
        registry = RoomRegistry()
        bridge = RoomBridge(registry)

        vc = _venture_cell(
            id="vc1",
            spinout_conditions=["revenue_covers_burn", "3_paying_customers"],
        )
        bridge.create_room(vc)

        kpis = {
            "revenue_usd": 2000, "burn_usd": 1500,
            "paying_customers": 5, "days_active": 30,
        }
        result = bridge.evaluate_room_health("vc1", kpis)
        assert result["spinout_triggered"] is True
        assert result["kill_triggered"] is False
