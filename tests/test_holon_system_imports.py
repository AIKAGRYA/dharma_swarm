"""Import checks for the thin holon_system facade package.

The package must organize existing organs without redefining canonical runtime
primitives such as load_holon or holon_wake_cycle.
"""

from __future__ import annotations

import importlib


FACADE_MODULES = [
    "dharma_swarm.holon_system",
    "dharma_swarm.holon_system.identity",
    "dharma_swarm.holon_system.identity.registry",
    "dharma_swarm.holon_system.identity.cards",
    "dharma_swarm.holon_system.identity.canonical_names",
    "dharma_swarm.holon_system.runtime",
    "dharma_swarm.holon_system.runtime.bridge",
    "dharma_swarm.holon_system.runtime.wake_cycle",
    "dharma_swarm.holon_system.runtime.persistence",
    "dharma_swarm.holon_system.runtime.health",
    "dharma_swarm.holon_system.kernel",
    "dharma_swarm.holon_system.kernel.living_kernel",
    "dharma_swarm.holon_system.authority",
    "dharma_swarm.holon_system.authority.execution_lease",
    "dharma_swarm.holon_system.authority.reversibility_gate",
    "dharma_swarm.holon_system.authority.permissions",
    "dharma_swarm.holon_system.orchestration",
    "dharma_swarm.holon_system.orchestration.fanout",
    "dharma_swarm.holon_system.orchestration.agent_pool",
    "dharma_swarm.holon_system.orchestration.intent",
    "dharma_swarm.holon_system.transport",
    "dharma_swarm.holon_system.transport.a2a_send",
    "dharma_swarm.holon_system.transport.inbox_bridge",
    "dharma_swarm.holon_system.transport.reply_capture",
    "dharma_swarm.holon_system.transport.domain_reply",
    "dharma_swarm.holon_system.responders",
    "dharma_swarm.holon_system.responders.wake_profiles",
    "dharma_swarm.holon_system.gateway",
    "dharma_swarm.holon_system.gateway.base",
    "dharma_swarm.holon_system.gateway.operator_brief",
    "dharma_swarm.holon_system.observability",
    "dharma_swarm.holon_system.observability.proof_gates",
    "dharma_swarm.holon_system.observability.scoreboard",
    "dharma_swarm.holon_system.cli",
    "dharma_swarm.holon_system.cli.commands",
    "dharma_swarm.holon_system.api",
    "dharma_swarm.holon_system.api.routes",
    "dharma_swarm.holon_system.sarathi",
    "dharma_swarm.holon_system.sarathi.gateway",
    "dharma_swarm.holon_system.sarathi.pulse",
    "dharma_swarm.holon_system.sarathi.roster",
    "dharma_swarm.holon_system.sarathi.brief",
    "dharma_swarm.holon_system.sarathi.scoreboard",
]


def test_all_holon_system_facades_import() -> None:
    for module_name in FACADE_MODULES:
        assert importlib.import_module(module_name)


def test_runtime_facades_point_to_canonical_primitives() -> None:
    from dharma_swarm import holon_bridge, holon_runtime
    from dharma_swarm.holon_system.runtime import bridge, wake_cycle

    assert bridge.load_holon is holon_bridge.load_holon
    assert wake_cycle.holon_wake_cycle is holon_runtime.holon_wake_cycle


def test_sarathi_gateway_snapshot_is_honest_not_alive_claim() -> None:
    from dharma_swarm.holon_system.sarathi.gateway import gateway_snapshot

    snapshot = gateway_snapshot()

    assert snapshot["schema_version"] == "dharma.sarathi.gateway_snapshot.v1"
    assert snapshot["wake_loop_active"] is False
    assert snapshot["alive_claim"] is False
    assert "not alive" in snapshot["brief"]
