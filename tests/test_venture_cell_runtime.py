from __future__ import annotations

import pytest

from dharma_swarm.venture_cell import DomainCEOContractError, VentureCellRuntime
from dharma_swarm.venture_cell.livelihood_loom import load_livelihood_loom_contract


def test_runtime_starts_mission_and_spawns_bounded_lanes(tmp_path):
    contract = load_livelihood_loom_contract()
    runtime = VentureCellRuntime(contract, tmp_path / "external_actions.jsonl")
    mission = runtime.start_mission(
        title="Informal Economy Enablement Pilot 001",
        success_contract=[
            "100 enriched records",
            "5 enablement packets",
            "1 measured livelihood outcome",
        ],
    )
    lane = runtime.spawn_lane(
        mission.mission_id,
        role="field_cartography",
        depth=1,
        lane_id="lane_field_1",
    )
    assert lane.role == "field_cartography"
    assert mission.lanes[0].lane_id == "lane_field_1"


def test_runtime_enforces_lane_budget(tmp_path):
    contract = load_livelihood_loom_contract()
    runtime = VentureCellRuntime(contract, tmp_path / "external_actions.jsonl")
    mission = runtime.start_mission(title="Pilot", success_contract=["receipt"])
    lane = runtime.spawn_lane(mission.mission_id, role="offer_builder", depth=1)
    with pytest.raises(Exception, match="cost cap exceeded"):
        runtime.record_lane_spend(
            mission.mission_id,
            lane.lane_id,
            spent_usd=contract.budget_policy.lane_cap_usd,
        )


def test_runtime_rejects_unknown_mission(tmp_path):
    contract = load_livelihood_loom_contract()
    runtime = VentureCellRuntime(contract, tmp_path / "external_actions.jsonl")
    with pytest.raises(DomainCEOContractError, match="mission not found"):
        runtime.spawn_lane("missing", role="field_cartography")
