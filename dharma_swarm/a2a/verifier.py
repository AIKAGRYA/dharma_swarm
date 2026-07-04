"""Read-only A2A population verifier.

This module verifies denominator shape only. It does not claim liveness for
local or cloud agents; live contact still comes from receipts and transport
probes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dharma_swarm.a2a.contact_registry import (
    CONTACT_KIND_CLOUD_AGENT,
    CONTACT_KIND_LOCAL_AGENT,
    ContactRegistry,
    default_contact_registry,
)


@dataclass(frozen=True)
class A2ADenominatorReport:
    total_agent_denominator: int
    local_agent_denominator: int
    cloud_agent_denominator: int
    contacts: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "dharma.a2a.denominator.v1",
            "total_agent_denominator": self.total_agent_denominator,
            "local_agent_denominator": self.local_agent_denominator,
            "cloud_agent_denominator": self.cloud_agent_denominator,
            "contacts": list(self.contacts),
            "liveness_claim": "not_claimed_by_denominator_report",
        }


def build_denominator_report(
    registry: ContactRegistry | None = None,
) -> A2ADenominatorReport:
    resolved = registry or default_contact_registry()
    contacts = resolved.list_all()
    local_agents = [item for item in contacts if item.kind == CONTACT_KIND_LOCAL_AGENT]
    cloud_agents = [item for item in contacts if item.kind == CONTACT_KIND_CLOUD_AGENT]
    return A2ADenominatorReport(
        total_agent_denominator=len(contacts),
        local_agent_denominator=len(local_agents),
        cloud_agent_denominator=len(cloud_agents),
        contacts=tuple(item.to_dict() for item in contacts),
    )


def cloud_agent_denominator(registry: ContactRegistry | None = None) -> int:
    return build_denominator_report(registry).cloud_agent_denominator
