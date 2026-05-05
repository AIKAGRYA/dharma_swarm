"""Tests for pre-defined room configurations (Build 5).

Proves the Revenue Wedge and Core Ops rooms are valid, well-formed,
and satisfy all Five Laws of Fractal Rooms.
"""

from __future__ import annotations

import pytest

from dharma_swarm.fractal.fractal_room import (
    FractalRoom,
    RoomKind,
    RoomRegistry,
    RoomStatus,
    VentureCellV1,
    WorkPacket,
    evaluate_kill_conditions,
    evaluate_spinout_conditions,
    validate_room,
    validate_venture_cell,
)
from dharma_swarm.fractal.room_brief import render_room_section, render_room_summary_line
from dharma_swarm.fractal.room_configs import (
    bootstrap_registry,
    make_agentops_room,
    make_core_ops_room,
    make_revenue_wedge_cell,
)


# -----------------------------------------------------------------------
# Room validity
# -----------------------------------------------------------------------

class TestCoreOpsRoom:

    def test_valid(self):
        room = make_core_ops_room()
        validate_room(room)

    def test_is_root(self):
        room = make_core_ops_room()
        assert room.parent_id is None

    def test_has_operator(self):
        room = make_core_ops_room()
        assert room.operator == "dhyana"

    def test_has_agents(self):
        room = make_core_ops_room()
        assert len(room.agents) >= 2

    def test_forbidden_work_set(self):
        room = make_core_ops_room()
        assert "live autonomy" in room.forbidden_work

    def test_approval_required(self):
        room = make_core_ops_room()
        assert "merge to main" in room.approval_required_for


class TestRevenueWedgeCell:

    def test_valid(self):
        cell = make_revenue_wedge_cell()
        validate_venture_cell(cell)

    def test_is_venture_cell(self):
        cell = make_revenue_wedge_cell()
        assert cell.kind == RoomKind.VENTURE_CELL
        assert isinstance(cell, VentureCellV1)

    def test_has_parent(self):
        cell = make_revenue_wedge_cell()
        assert cell.parent_id == "core-ops"

    def test_has_revenue_target(self):
        cell = make_revenue_wedge_cell()
        assert cell.revenue_target > 0

    def test_has_customer(self):
        cell = make_revenue_wedge_cell()
        assert cell.customer_or_beneficiary != ""

    def test_has_kill_conditions(self):
        cell = make_revenue_wedge_cell()
        assert len(cell.kill_conditions) >= 2
        assert "no_revenue_after_60_days" in cell.kill_conditions

    def test_has_spinout_conditions(self):
        cell = make_revenue_wedge_cell()
        assert len(cell.spinout_conditions) >= 2
        assert "revenue_exceeds_burn" in cell.spinout_conditions

    def test_has_jagat_kalyan_constraint(self):
        cell = make_revenue_wedge_cell()
        assert "welfare" in cell.jagat_kalyan_constraint.lower()

    def test_forbidden_work_more_restrictive_than_parent(self):
        core = make_core_ops_room()
        cell = make_revenue_wedge_cell()
        # Revenue wedge has more forbidden items than core ops
        assert len(cell.forbidden_work) > len(core.forbidden_work)

    def test_budget_less_than_parent(self):
        core = make_core_ops_room()
        cell = make_revenue_wedge_cell()
        assert cell.budget_tokens < core.budget_tokens


class TestAgentOpsRoom:

    def test_valid(self):
        room = make_agentops_room()
        validate_room(room)

    def test_child_of_core(self):
        room = make_agentops_room()
        assert room.parent_id == "core-ops"


# -----------------------------------------------------------------------
# Registry bootstrap
# -----------------------------------------------------------------------

class TestBootstrapRegistry:

    def test_creates_3_rooms(self):
        registry = bootstrap_registry()
        assert len(registry.all_rooms()) == 3

    def test_hierarchy(self):
        registry = bootstrap_registry()
        children = registry.children_of("core-ops")
        child_ids = {c.id for c in children}
        assert "revenue-wedge" in child_ids
        assert "agentops" in child_ids

    def test_all_active(self):
        registry = bootstrap_registry()
        active = registry.active_rooms()
        assert len(active) == 3

    def test_venture_cells_count(self):
        registry = bootstrap_registry()
        vcs = registry.venture_cells()
        assert len(vcs) == 1
        assert vcs[0].id == "revenue-wedge"


# -----------------------------------------------------------------------
# Revenue Wedge kill/spinout evaluation
# -----------------------------------------------------------------------

class TestRevenueWedgeHealth:

    def test_healthy_when_revenue_flowing(self):
        cell = make_revenue_wedge_cell()
        kpis = {
            "revenue_usd": 100,
            "days_active": 10,
            "budget_ratio": 0.5,
            "monthly_revenue_gt_burn_months": 1,
        }
        assert not evaluate_kill_conditions(cell.kill_conditions, kpis)
        assert not evaluate_spinout_conditions(cell.spinout_conditions, kpis)

    def test_kill_triggered_no_revenue(self):
        cell = make_revenue_wedge_cell()
        kpis = {"revenue_usd": 0, "days_active": 65, "budget_ratio": 0.5}
        assert evaluate_kill_conditions(cell.kill_conditions, kpis)

    def test_kill_triggered_budget_exceeded(self):
        cell = make_revenue_wedge_cell()
        kpis = {"revenue_usd": 100, "days_active": 10, "budget_ratio": 1.25}
        assert evaluate_kill_conditions(cell.kill_conditions, kpis)

    def test_spinout_ready(self):
        cell = make_revenue_wedge_cell()
        kpis = {
            "monthly_revenue_gt_burn_months": 4,
            "paying_customers": 5,
            "operator_approved_graduation": True,
        }
        assert evaluate_spinout_conditions(cell.spinout_conditions, kpis)

    def test_spinout_not_ready_missing_approval(self):
        cell = make_revenue_wedge_cell()
        kpis = {
            "monthly_revenue_gt_burn_months": 4,
            "paying_customers": 5,
            "operator_approved_graduation": False,
        }
        assert not evaluate_spinout_conditions(cell.spinout_conditions, kpis)


# -----------------------------------------------------------------------
# Brief rendering with bootstrapped registry
# -----------------------------------------------------------------------

class TestRevenueWedgeBrief:

    def test_summary_line(self):
        registry = bootstrap_registry()
        line = render_room_summary_line(registry)
        assert "3 active" in line
        assert "1 venture cells" in line

    def test_room_section_includes_revenue_wedge(self):
        registry = bootstrap_registry()
        section = render_room_section(registry)
        assert "revenue-wedge" in section
        assert "venture_cell" in section
        assert "self-funding" in section.lower()

    def test_room_section_shows_core_ops(self):
        registry = bootstrap_registry()
        section = render_room_section(registry)
        assert "core-ops" in section

    def test_room_section_shows_agentops(self):
        registry = bootstrap_registry()
        section = render_room_section(registry)
        assert "agentops" in section


# -----------------------------------------------------------------------
# Integration: work packet in revenue wedge
# -----------------------------------------------------------------------

class TestRevenueWedgeWorkPacket:

    def _rev_wedge_forbidden(self) -> list[str]:
        return make_revenue_wedge_cell().forbidden_work

    def test_create_work_packet_in_revenue_wedge(self):
        registry = bootstrap_registry()
        packet = WorkPacket(
            id="wp_rv_001",
            source_room_id="revenue-wedge",
            purpose="Identify 10 potential customers for Dharma Swarm",
            assigned_agent_id="claude.local",
            cost_ceiling=5000,
            forbidden_mutations=self._rev_wedge_forbidden(),
        )
        registry.create_work_packet(packet)
        packets = registry.room_work_packets("revenue-wedge")
        assert len(packets) == 1
        assert "customers" in packets[0].purpose.lower()

    def test_work_packet_cost_deducted_from_budget(self):
        registry = bootstrap_registry()
        packet = WorkPacket(
            id="wp_rv_002",
            source_room_id="revenue-wedge",
            purpose="Build MVP prototype",
            assigned_agent_id="devin.cloud",
            cost_ceiling=10000,
            forbidden_mutations=self._rev_wedge_forbidden(),
        )
        registry.create_work_packet(packet)
        registry.complete_work_packet("wp_rv_002", "success", cost_tokens=3000)
        cell = registry.get("revenue-wedge")
        assert cell is not None
        assert cell.remaining_budget() == 50_000 - 3000
