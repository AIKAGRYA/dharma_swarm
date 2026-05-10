from __future__ import annotations

import pytest

from dharma_swarm.models import GateCheckResult, GateDecision, GateResult
from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.ontology_action_gateway import (
    OntologyActionGateway,
    OntologyGatewayError,
)


class _AllowingGatekeeper:
    def check(self, **_kwargs):
        return GateCheckResult(
            decision=GateDecision.ALLOW,
            reason="ok",
            gate_results={
                "AHIMSA": (GateResult.PASS, ""),
                "SATYA": (GateResult.PASS, ""),
            },
        )


class _BlockingGatekeeper:
    def check(self, **_kwargs):
        return GateCheckResult(
            decision=GateDecision.BLOCK,
            reason="unsafe action",
            gate="SATYA",
            gate_results={
                "AHIMSA": (GateResult.PASS, ""),
                "SATYA": (GateResult.FAIL, "unsafe action"),
            },
        )


def test_gateway_creates_and_executes_gated_action() -> None:
    registry = OntologyRegistry.create_dharma_registry()
    gateway = OntologyActionGateway(registry=registry, gatekeeper=_AllowingGatekeeper())

    experiment = gateway.create_object_or_fail(
        "Experiment",
        {"name": "gateway smoke", "status": "designed"},
    )
    execution = gateway.execute_action_or_fail(
        "Experiment",
        "Run",
        experiment.id,
        {"gpu": "A100"},
    )

    assert execution.result == "success"
    assert execution.gate_results == {"AHIMSA": "PASS", "SATYA": "PASS"}


def test_gateway_fails_closed_for_invalid_writes() -> None:
    gateway = OntologyActionGateway(
        registry=OntologyRegistry.create_dharma_registry(),
        gatekeeper=_AllowingGatekeeper(),
    )

    with pytest.raises(OntologyGatewayError, match="create_object failed"):
        gateway.create_object_or_fail("MissingType", {})

    with pytest.raises(OntologyGatewayError, match="link failed"):
        gateway.link_or_fail("has_experiment", "missing-source", "missing-target")


def test_gateway_blocks_failed_telos_gate() -> None:
    registry = OntologyRegistry.create_dharma_registry()
    gateway = OntologyActionGateway(registry=registry, gatekeeper=_BlockingGatekeeper())
    experiment = gateway.create_object_or_fail(
        "Experiment",
        {"name": "blocked gateway smoke", "status": "designed"},
    )

    with pytest.raises(OntologyGatewayError, match="telos gate blocked"):
        gateway.execute_action_or_fail("Experiment", "Run", experiment.id, {})

    history = registry.action_history(object_id=experiment.id)
    assert history[0].result == "blocked"
    assert history[0].gate_results == {"SATYA": "BLOCK"}
