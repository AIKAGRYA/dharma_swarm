"""Readiness projection for the Livelihood Loom VentureCell."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.venture_cell.domain_ceo import ProviderProof
from dharma_swarm.venture_cell.livelihood_loom import (
    DEFAULT_CHARTER_PATH,
    load_livelihood_loom_contract,
)
from dharma_swarm.venture_cell.livelihood_loom.ceo_agent import AGENT_ID, CALLSIGN, DEFAULT_DHARMA_HOME
from dharma_swarm.venture_cell.workflow_plan import livelihood_pilot_workflow_spec

DEFAULT_CYCLE_LATEST = Path("reports/livelihood_loom/cycles/latest.json")


@dataclass(frozen=True)
class ReadinessGate:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class LivelihoodLoomReadiness:
    cell_id: str
    overall_status: str
    gates: tuple[ReadinessGate, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "cell_id": self.cell_id,
            "overall_status": self.overall_status,
            "gates": [gate.to_dict() for gate in self.gates],
        }


def project_readiness(
    *,
    provider_proof: ProviderProof | None = None,
    charter_path: str | Path = DEFAULT_CHARTER_PATH,
    dharma_home: str | Path = DEFAULT_DHARMA_HOME,
) -> LivelihoodLoomReadiness:
    """Project readiness without claiming production liveness."""
    charter = Path(charter_path)
    if charter == DEFAULT_CHARTER_PATH:
        contract = load_livelihood_loom_contract()
    else:
        from dharma_swarm.venture_cell.domain_ceo import load_domain_ceo_contract

        contract = load_domain_ceo_contract(charter)

    workflow = livelihood_pilot_workflow_spec(
        mission_id=contract.mission_id,
        trace_id=f"trace_{contract.cell_id}_readiness",
    )
    home = Path(dharma_home).expanduser()
    registration_path = home / "external_agents" / AGENT_ID / "registration.json"
    living_agent_path = home / "agents" / AGENT_ID / "living_agent.json"
    card_path = home / "a2a" / "cards" / f"{CALLSIGN}.json"
    registered = registration_path.exists() and living_agent_path.exists() and card_path.exists()
    latest_bootstrap = Path("reports/livelihood_loom/bootstrap/latest.json")
    latest_cycle = DEFAULT_CYCLE_LATEST
    cultivation_ready = latest_cycle.exists()
    provider_green = bool(provider_proof and provider_proof.is_green())
    gates = (
        ReadinessGate(
            "charter_contract",
            "green",
            f"{contract.cell_id} CEO contract validates",
        ),
        ReadinessGate(
            "capital_firewall",
            "green",
            contract.capital_boundary,
        ),
        ReadinessGate(
            "workflow_contract",
            "green",
            f"{workflow.workflow_name} has {len(workflow.activities)} activities",
        ),
        ReadinessGate(
            "external_action_mode",
            "green",
            contract.external_action_policy.external_action_mode,
        ),
        ReadinessGate(
            "ceo_registration",
            "green" if registered else "yellow",
            str(living_agent_path) if registered else "persistent CEO not registered in DHARMA_HOME",
        ),
        ReadinessGate(
            "safe_bootstrap",
            "green" if latest_bootstrap.exists() else "yellow",
            str(latest_bootstrap) if latest_bootstrap.exists() else "no local bootstrap receipt yet",
        ),
        ReadinessGate(
            "cultivation_cycle",
            "green" if cultivation_ready else "yellow",
            str(latest_cycle)
            if cultivation_ready
            else "no cultivation-cycle receipt yet",
        ),
        ReadinessGate(
            "provider_proof",
            "green" if provider_green else "red",
            "complete provider proof present"
            if provider_green
            else "missing complete provider proof",
        ),
    )
    if provider_green:
        overall = "control_plane_ready"
    elif cultivation_ready:
        overall = "cultivation_ready_provider_blocked"
    else:
        overall = "contract_ready_provider_blocked"
    return LivelihoodLoomReadiness(
        cell_id=contract.cell_id,
        overall_status=overall,
        gates=gates,
    )
