"""Tests for dharma_swarm.world_model — system dynamics world model.

Validates:
- WorldStock, WorldFlow, FeedbackLoop dataclass construction
- WorldModelState composition
- WorldModelStore save_snapshot/load_latest round-trip
- _build_initial_state completeness (15 stocks, 8 flows, 6 loops)
- INITIAL_WORLD_STATE module-level singleton
- query_world_model text matching
- update_stock value mutation and trajectory inference
- assess_action_impact structure
- get_telos_pressure algedonic signal detection
- WorldModelAgent boot logic
"""

from __future__ import annotations

import copy
import json

import pytest

from dharma_swarm.world_model import (
    INITIAL_WORLD_STATE,
    FeedbackLoop,
    WorldFlow,
    WorldModelAgent,
    WorldModelStore,
    WorldStock,
    _build_initial_state,
    assess_action_impact,
    get_telos_pressure,
    query_world_model,
    update_stock,
)


@pytest.fixture(autouse=True)
def restore_initial_world_state():
    """Restore the module singleton in place after tests that mutate stocks."""
    snapshot = copy.deepcopy(INITIAL_WORLD_STATE)
    yield
    INITIAL_WORLD_STATE.version = snapshot.version
    INITIAL_WORLD_STATE.timestamp = snapshot.timestamp
    INITIAL_WORLD_STATE.stocks = snapshot.stocks
    INITIAL_WORLD_STATE.flows = snapshot.flows
    INITIAL_WORLD_STATE.feedback_loops = snapshot.feedback_loops
    INITIAL_WORLD_STATE.telos_attractors = snapshot.telos_attractors
    INITIAL_WORLD_STATE.confidence = snapshot.confidence
    INITIAL_WORLD_STATE.last_research_update = snapshot.last_research_update
    INITIAL_WORLD_STATE.agent_action_queue = snapshot.agent_action_queue


# ---------------------------------------------------------------------------
# Dataclass construction
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_world_stock_basic(self):
        s = WorldStock(
            id="T1", name="Test Stock", domain="biosphere",
            current_value=0.5, trajectory="rising",
            rate_of_change=0.01, threshold_critical=0.2,
            telos_relevance="KALYAN",
        )
        assert s.id == "T1"
        assert s.domain == "biosphere"
        assert s.inflows == []
        assert s.evidence_sources == []

    def test_world_flow_basic(self):
        f = WorldFlow(
            id="TF1", name="Test Flow", direction="inflow", magnitude=0.5,
        )
        assert f.dharmic_alignment == 0.5
        assert f.agent_actionable is False

    def test_feedback_loop_basic(self):
        loop = FeedbackLoop(
            id="TL1", name="Test Loop", loop_type="reinforcing",
        )
        assert loop.current_strength == 0.5
        assert loop.is_tipping_point_risk is False
        assert loop.telos_alignment == 0.5


# ---------------------------------------------------------------------------
# _build_initial_state
# ---------------------------------------------------------------------------


class TestBuildInitialState:
    def test_15_stocks(self):
        state = _build_initial_state()
        assert len(state.stocks) == 15

    def test_8_flows(self):
        state = _build_initial_state()
        assert len(state.flows) == 8

    def test_6_feedback_loops(self):
        state = _build_initial_state()
        assert len(state.feedback_loops) == 6

    def test_stock_ids_sequential(self):
        state = _build_initial_state()
        for i in range(1, 16):
            assert f"S{i:02d}" in state.stocks

    def test_flow_ids_sequential(self):
        state = _build_initial_state()
        for i in range(1, 9):
            assert f"F{i:02d}" in state.flows

    def test_loop_ids_sequential(self):
        state = _build_initial_state()
        for i in range(1, 7):
            assert f"L{i:02d}" in state.feedback_loops

    def test_all_stocks_normalized(self):
        state = _build_initial_state()
        for s in state.stocks.values():
            assert 0.0 <= s.current_value <= 1.0

    def test_all_flows_normalized(self):
        state = _build_initial_state()
        for f in state.flows.values():
            assert 0.0 <= f.magnitude <= 1.0

    def test_version_set(self):
        state = _build_initial_state()
        assert state.version == "0.1.0"

    def test_confidence_set(self):
        state = _build_initial_state()
        assert state.confidence == 0.6

    def test_has_reinforcing_and_balancing_loops(self):
        state = _build_initial_state()
        types = {loop.loop_type for loop in state.feedback_loops.values()}
        assert "reinforcing" in types
        assert "balancing" in types


# ---------------------------------------------------------------------------
# INITIAL_WORLD_STATE singleton
# ---------------------------------------------------------------------------


class TestInitialWorldState:
    def test_singleton_populated(self):
        assert INITIAL_WORLD_STATE is not None
        assert len(INITIAL_WORLD_STATE.stocks) == 15

    def test_co2_stock_present(self):
        s01 = INITIAL_WORLD_STATE.stocks["S01"]
        assert "CO2" in s01.name
        assert s01.trajectory == "rising"

    def test_ai_alignment_stock(self):
        s11 = INITIAL_WORLD_STATE.stocks["S11"]
        assert "Alignment" in s11.name
        assert s11.current_value < s11.threshold_critical + 0.2


# ---------------------------------------------------------------------------
# WorldModelStore
# ---------------------------------------------------------------------------


class TestWorldModelStore:
    def test_save_and_load_latest(self, tmp_path):
        store = WorldModelStore(base_path=tmp_path / "wm")
        state = _build_initial_state()
        path = store.save_snapshot(state)
        assert path.exists()
        assert (tmp_path / "wm" / "latest.json").exists()

        loaded = store.load_latest()
        assert loaded is not None
        assert loaded.version == state.version
        assert len(loaded.stocks) == len(state.stocks)
        assert len(loaded.flows) == len(state.flows)

    def test_load_latest_empty(self, tmp_path):
        store = WorldModelStore(base_path=tmp_path / "empty")
        assert store.load_latest() is None

    def test_snapshot_filename_includes_version(self, tmp_path):
        store = WorldModelStore(base_path=tmp_path / "wm")
        state = _build_initial_state()
        path = store.save_snapshot(state)
        assert "0.1.0" in path.name

    def test_latest_json_valid(self, tmp_path):
        store = WorldModelStore(base_path=tmp_path / "wm")
        store.save_snapshot(_build_initial_state())
        data = json.loads((tmp_path / "wm" / "latest.json").read_text())
        assert "stocks" in data
        assert "flows" in data
        assert "feedback_loops" in data


# ---------------------------------------------------------------------------
# query_world_model
# ---------------------------------------------------------------------------


class TestQueryWorldModel:
    def test_query_by_stock_name(self):
        results = query_world_model("co2")
        assert len(results) >= 1
        assert any("CO2" in getattr(r, "name", "") for r in results)

    def test_query_by_domain(self):
        results = query_world_model("biosphere")
        assert len(results) >= 1

    def test_query_by_flow_name(self):
        results = query_world_model("emissions")
        assert len(results) >= 1

    def test_query_no_match(self):
        results = query_world_model("zzzznonexistent")
        assert results == []


# ---------------------------------------------------------------------------
# update_stock
# ---------------------------------------------------------------------------


class TestUpdateStock:
    def test_updates_value(self):
        old = INITIAL_WORLD_STATE.stocks["S01"].current_value
        result = update_stock("S01", 0.35, ["NOAA 2026"], "https://noaa.gov")
        assert result["old_value"] == old
        assert result["new_value"] == 0.35

    def test_trajectory_inference_rising(self):
        old = INITIAL_WORLD_STATE.stocks["S14"].current_value
        result = update_stock("S14", old + 0.05, [], "test")
        assert result["trajectory"] == "rising"

    def test_trajectory_inference_falling(self):
        old = INITIAL_WORLD_STATE.stocks["S14"].current_value
        result = update_stock("S14", old - 0.05, [], "test")
        assert result["trajectory"] == "falling"

    def test_unknown_stock_raises(self):
        with pytest.raises(ValueError, match="not found"):
            update_stock("S99", 0.5, [], "test")


# ---------------------------------------------------------------------------
# assess_action_impact
# ---------------------------------------------------------------------------


class TestAssessActionImpact:
    def test_returns_structured_dict(self):
        result = assess_action_impact("Deploy new AI agent")
        assert "action" in result
        assert "dharmic_alignment_score" in result
        assert "recommendation" in result

    def test_recommendation_is_review(self):
        result = assess_action_impact("anything")
        assert result["recommendation"] == "review"


# ---------------------------------------------------------------------------
# get_telos_pressure
# ---------------------------------------------------------------------------


class TestGetTelosPressure:
    def test_returns_dict(self):
        pressures = get_telos_pressure()
        assert isinstance(pressures, dict)

    def test_critical_stocks_detected(self):
        pressures = get_telos_pressure()
        for sid, info in pressures.items():
            assert "name" in info
            assert info["severity"] == "high"

    def test_alignment_stock_likely_pressured(self):
        pressures = get_telos_pressure()
        s11 = INITIAL_WORLD_STATE.stocks["S11"]
        if s11.trajectory == "rising" and s11.current_value > s11.threshold_critical - 0.1:
            assert "S11" in pressures


# ---------------------------------------------------------------------------
# WorldModelAgent
# ---------------------------------------------------------------------------


class TestWorldModelAgent:
    async def test_boot_loads_from_store(self, tmp_path):
        store = WorldModelStore(base_path=tmp_path / "wm")
        state = _build_initial_state()
        store.save_snapshot(state)

        agent = WorldModelAgent(store=store, search_tool=None, arxiv_tool=None)
        await agent.boot()
        assert agent._state is not None
        assert len(agent._state.stocks) == 15

    async def test_boot_fallback_to_initial(self, tmp_path):
        store = WorldModelStore(base_path=tmp_path / "empty_wm")
        agent = WorldModelAgent(store=store, search_tool=None, arxiv_tool=None)
        await agent.boot()
        assert agent._state is not None
        assert agent._state is INITIAL_WORLD_STATE


    async def test_run_cycle_persists_snapshot(self, tmp_path):
        # Regression (H02 P3.1): orchestrate_live called WorldModelAgent
        # (state_dir=...) + initialize()/run_cycle() against a class exposing
        # (store, search_tool, arxiv_tool) + boot() — 147 crashes/day, loop
        # abandoned. This mirrors the orchestrator construction path exactly.
        store = WorldModelStore(base_path=tmp_path / 'wm_cycle')
        agent = WorldModelAgent(store=store, search_tool=None, arxiv_tool=None)
        await agent.boot()
        await agent.run_cycle()
        snaps = list((tmp_path / 'wm_cycle').glob('snapshot_*.json'))
        assert len(snaps) == 1
