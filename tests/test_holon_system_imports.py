"""The holon_system facade package must re-export the SAME objects as the
canonical owners - never a second implementation.

This test is the executable proof for deliverable #4 (target package skeleton).
If a facade ever drifts into a real reimplementation, is-identity breaks and
this test fails, which is exactly the anti-sprawl guarantee we want.
"""

from __future__ import annotations

import importlib


def test_identity_facade_reexports_canonical_symbols() -> None:
    import dharma_swarm.agent_registry as reg
    import dharma_swarm.holon_bridge as bridge
    from dharma_swarm.holon_system import identity

    assert identity.AgentRegistry is reg.AgentRegistry
    assert identity.load_holon is bridge.load_holon
    assert identity.RunningHolon is bridge.RunningHolon


def test_runtime_bridge_facade_is_identity_not_copy() -> None:
    import dharma_swarm.holon_bridge as bridge
    from dharma_swarm.holon_system.runtime import bridge as facade

    for name in (
        "RunningHolon",
        "build_request",
        "get_holon_provider",
        "guard_outcome_claim",
        "holon_reply",
        "load_holon",
    ):
        assert getattr(facade, name) is getattr(bridge, name), name


def test_runtime_wake_facade_reexports_wake_cycle() -> None:
    import dharma_swarm.holon_runtime as rt
    from dharma_swarm.holon_system.runtime import wake

    assert wake.holon_wake_cycle is rt.holon_wake_cycle
    assert wake.run_holon_loop is rt.run_holon_loop


def test_runtime_persistence_facade_reexports() -> None:
    import dharma_swarm.holon_persistence as persist
    from dharma_swarm.holon_system.runtime import persistence

    assert persistence.save_cycle_record is persist.save_cycle_record
    assert persistence.resume_point is persist.resume_point


def test_kernel_facade_reexports_living_agent_kernel() -> None:
    import dharma_swarm.operator_core.living_agent_kernel as lak
    from dharma_swarm.holon_system.kernel import living

    assert living.LivingAgentKernel is lak.LivingAgentKernel


def test_authority_leases_facade_reexports() -> None:
    import dharma_swarm.operator_core.execution_lease as lease
    from dharma_swarm.holon_system.authority import leases

    assert leases.build_execution_lease is lease.build_execution_lease
    assert leases.validate_execution_lease is lease.validate_execution_lease


def test_authority_reversibility_facade_reexports_gate() -> None:
    import dharma_swarm.operator_core.reversibility_gate as gate
    from dharma_swarm.holon_system.authority import reversibility

    assert reversibility.ReversibilityGate is gate.ReversibilityGate
    assert reversibility.classify_action is gate.classify_action
    assert reversibility.ActionClass is gate.ActionClass


def test_orchestration_facade_reexports() -> None:
    import dharma_swarm.holon_orchestrate as orch
    from dharma_swarm.holon_system.orchestration import holon_orchestrate as facade

    assert facade.run_holon_orchestration is orch.run_holon_orchestration
    assert facade.HolonOrchestrationConfig is orch.HolonOrchestrationConfig


def test_observability_facade_reexports() -> None:
    import dharma_swarm.holon_canonical_state as canon
    import dharma_swarm.holon_health as health
    from dharma_swarm.holon_system import observability

    assert observability.holon_status is health.holon_status
    assert observability.project_canonical_holon_state is canon.project_canonical_holon_state


def test_all_subpackages_import_cleanly() -> None:
    # Every declared organ subpackage must import without error, including the
    # "no library yet" pointers (transport/responders/gateway/cli/api) and the
    # not-yet-implemented sarathi package.
    for name in (
        "dharma_swarm.holon_system",
        "dharma_swarm.holon_system.identity",
        "dharma_swarm.holon_system.runtime",
        "dharma_swarm.holon_system.runtime.bridge",
        "dharma_swarm.holon_system.runtime.wake",
        "dharma_swarm.holon_system.runtime.persistence",
        "dharma_swarm.holon_system.kernel",
        "dharma_swarm.holon_system.kernel.living",
        "dharma_swarm.holon_system.authority",
        "dharma_swarm.holon_system.authority.leases",
        "dharma_swarm.holon_system.authority.reversibility",
        "dharma_swarm.holon_system.orchestration",
        "dharma_swarm.holon_system.orchestration.holon_orchestrate",
        "dharma_swarm.holon_system.observability",
        "dharma_swarm.holon_system.transport",
        "dharma_swarm.holon_system.responders",
        "dharma_swarm.holon_system.gateway",
        "dharma_swarm.holon_system.cli",
        "dharma_swarm.holon_system.api",
        "dharma_swarm.holon_system.sarathi",
    ):
        assert importlib.import_module(name) is not None, name


def test_sarathi_package_is_specified_not_implemented() -> None:
    # Guardrail: the apex package must stay honestly empty of behavior until the
    # proof gates are met. If someone ships a stub gateway, flip IMPLEMENTED and
    # this test forces them to prove it instead of silently claiming an apex.
    from dharma_swarm.holon_system import sarathi

    assert sarathi.IMPLEMENTED is False
    assert sarathi.PLANNED_MODULES == ("gateway", "pulse", "roster", "brief", "scoreboard")
