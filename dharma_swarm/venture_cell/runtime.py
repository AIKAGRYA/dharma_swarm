"""Runtime scaffold for governed VentureCell CEO missions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dharma_swarm.venture_cell.domain_ceo import DomainCEOContract, DomainCEOContractError
from dharma_swarm.venture_cell.external_actions import (
    ExternalActionQueue,
    ExternalActionRequest,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentLane:
    lane_id: str
    role: str
    mission_id: str
    depth: int = 0
    status: str = "planned"
    proof_refs: list[str] = field(default_factory=list)
    spent_usd: float = 0.0
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class Mission:
    mission_id: str
    cell_id: str
    title: str
    success_contract: list[str]
    status: str = "active"
    lanes: list[AgentLane] = field(default_factory=list)
    spent_usd: float = 0.0
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["lanes"] = [lane.to_dict() for lane in self.lanes]
        return payload


class VentureCellRuntime:
    """Small runtime facade that binds a CEO contract to missions and approvals."""

    def __init__(self, contract: DomainCEOContract, external_action_log: str | Path):
        contract.validate()
        self.contract = contract
        self.missions: dict[str, Mission] = {}
        self.external_actions = ExternalActionQueue(contract, external_action_log)

    def start_mission(
        self,
        *,
        title: str,
        success_contract: list[str],
        mission_id: str | None = None,
    ) -> Mission:
        resolved_id = mission_id or self.contract.mission_id or f"mission_{uuid4().hex[:12]}"
        mission = Mission(
            mission_id=resolved_id,
            cell_id=self.contract.cell_id,
            title=title,
            success_contract=list(success_contract),
        )
        self.missions[mission.mission_id] = mission
        return mission

    def spawn_lane(
        self,
        mission_id: str,
        *,
        role: str,
        depth: int = 1,
        lane_id: str | None = None,
    ) -> AgentLane:
        mission = self._mission(mission_id)
        self.contract.check_spawn(
            requested_role=role,
            current_children=len(mission.lanes),
            requested_depth=depth,
        )
        lane = AgentLane(
            lane_id=lane_id or f"lane_{uuid4().hex[:12]}",
            role=role,
            mission_id=mission_id,
            depth=depth,
        )
        mission.lanes.append(lane)
        return lane

    def record_lane_spend(self, mission_id: str, lane_id: str, spent_usd: float) -> None:
        mission = self._mission(mission_id)
        lane = self._lane(mission, lane_id)
        self.contract.budget_policy.check_lane_spend(lane_id, spent_usd=spent_usd)
        lane.spent_usd = spent_usd
        mission.spent_usd = sum(item.spent_usd for item in mission.lanes)
        self.contract.budget_policy.check_mission_spend(spent_usd=mission.spent_usd)

    def draft_external_action(self, request: ExternalActionRequest) -> ExternalActionRequest:
        return self.external_actions.draft(request)

    def _mission(self, mission_id: str) -> Mission:
        mission = self.missions.get(mission_id)
        if mission is None:
            raise DomainCEOContractError(f"mission not found: {mission_id}")
        return mission

    @staticmethod
    def _lane(mission: Mission, lane_id: str) -> AgentLane:
        for lane in mission.lanes:
            if lane.lane_id == lane_id:
                return lane
        raise DomainCEOContractError(f"lane not found: {lane_id}")
