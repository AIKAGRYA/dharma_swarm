"""Livelihood Loom VentureCell."""

from pathlib import Path

from dharma_swarm.venture_cell.domain_ceo import DomainCEOContract, load_domain_ceo_contract
from dharma_swarm.venture_cell.livelihood_loom.ceo_agent import (
    AGENT_ID as CEO_AGENT_ID,
    CALLSIGN as CEO_CALLSIGN,
    build_external_worker_registration,
    register_livelihood_loom_ceo,
    register_livelihood_loom_ceo_sync,
)

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_CHARTER_PATH = PACKAGE_ROOT / "charter.yaml"


def load_livelihood_loom_contract() -> DomainCEOContract:
    return load_domain_ceo_contract(DEFAULT_CHARTER_PATH)


__all__ = [
    "CEO_AGENT_ID",
    "CEO_CALLSIGN",
    "DEFAULT_CHARTER_PATH",
    "PACKAGE_ROOT",
    "build_external_worker_registration",
    "load_livelihood_loom_contract",
    "register_livelihood_loom_ceo",
    "register_livelihood_loom_ceo_sync",
]
