from __future__ import annotations

import re
from datetime import datetime

import pytest

from dharma_swarm.models import GateCheckResult, GateDecision, GateResult
from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.ontology_action_gateway import (
    OntologyActionGateway,
    OntologyGatewayError,
)
from dharma_swarm.wiki_loom import LoomRevelationBuilder


class RecordingGatekeeper:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def check(self, **kwargs):
        self.calls.append(kwargs)
        return GateCheckResult(
            decision=GateDecision.ALLOW,
            reason="ok",
            gate_results={
                "BHED_GNAN": (GateResult.PASS, ""),
                "STEELMAN": (GateResult.PASS, ""),
                "DOGMA_DRIFT": (GateResult.PASS, ""),
                "CONSENT": (GateResult.PASS, ""),
            },
        )


@pytest.fixture()
def registry() -> OntologyRegistry:
    return OntologyRegistry.create_dharma_registry()


@pytest.fixture()
def gatekeeper() -> RecordingGatekeeper:
    return RecordingGatekeeper()


@pytest.fixture()
def gateway(registry: OntologyRegistry, gatekeeper: RecordingGatekeeper) -> OntologyActionGateway:
    return OntologyActionGateway(registry=registry, gatekeeper=gatekeeper)


def _now() -> datetime:
    return datetime(2026, 5, 7, 9, 30)


def _outcome(registry: OntologyRegistry):
    obj, errors = registry.create_object(
        "Outcome",
        {
            "proposal_id": "proposal-loom-1",
            "task_id": "task-loom-1",
            "agent_id": "agent-alpha",
            "success": True,
            "result_summary": "A real source row became a Loom page with resolvable citations.",
            "error": "",
            "duration_ms": 42.0,
            "fitness_score": 0.91,
        },
        created_by="test",
    )
    assert obj is not None, errors
    return obj


def _signal(registry: OntologyRegistry):
    obj, errors = registry.create_object(
        "Signal",
        {
            "signal_id": "signal-loom-1",
            "source": "unit-test",
            "captured_at": _now().isoformat(),
            "payload": "A scout signal identified a public Loom page candidate.",
            "observer_ref": "test",
            "source_kind": "manual",
            "sensitivity": "internal",
        },
        created_by="test",
    )
    assert obj is not None, errors
    return obj


def test_loom_revelation_creates_links_and_publishes(
    registry: OntologyRegistry,
    gateway: OntologyActionGateway,
    gatekeeper: RecordingGatekeeper,
    tmp_path,
) -> None:
    outcome = _outcome(registry)
    builder = LoomRevelationBuilder(gateway, output_dir=tmp_path, now_fn=_now)
    artifact = builder.compose(outcome)
    path = builder.publish(artifact)

    assert path.exists()
    assert artifact.type_name == "KnowledgeArtifact"
    assert registry.get_links(source_id=artifact.id, link_name="derived_from")
    assert registry.get_links(source_id=artifact.id, link_name="cites_witness")
    assert gatekeeper.calls
    assert registry.action_history(artifact.id, "Publish")

    content = path.read_text(encoding="utf-8")
    citations = re.findall(
        r"ontology://KnowledgeArtifact/([0-9a-f]+)#cites/Outcome/([0-9a-f]+)",
        content,
    )
    assert citations == [(artifact.id, outcome.id)]
    for artifact_id, outcome_id in citations:
        assert registry.get_object(artifact_id) is not None
        assert registry.get_object(outcome_id) is not None


def test_loom_signal_source_has_resolvable_citation_without_schema_link(
    registry: OntologyRegistry,
    gateway: OntologyActionGateway,
    tmp_path,
) -> None:
    signal = _signal(registry)
    builder = LoomRevelationBuilder(gateway, output_dir=tmp_path, now_fn=_now)
    artifact = builder.compose(signal)

    content = str(artifact.properties["content"])
    citations = re.findall(
        r"ontology://KnowledgeArtifact/([0-9a-f]+)#observes/Signal/([0-9a-f]+)",
        content,
    )
    assert citations == [(artifact.id, signal.id)]
    assert registry.get_object(signal.id) is not None
    assert registry.get_links(source_id=artifact.id, link_name="cites_witness")
    assert not registry.get_links(source_id=artifact.id, link_name="derived_from")


def test_loom_publish_bypass_fails(
    registry: OntologyRegistry,
    gateway: OntologyActionGateway,
    tmp_path,
) -> None:
    raw, errors = registry.create_object(
        "KnowledgeArtifact",
        {
            "title": "Bypass",
            "artifact_type": "finding",
            "domain": "dharma_swarm",
            "content": "ontology://fake",
        },
        created_by="test",
    )
    assert raw is not None, errors
    builder = LoomRevelationBuilder(gateway, output_dir=tmp_path, now_fn=_now)

    with pytest.raises(OntologyGatewayError, match="Loom-composed"):
        builder.publish(raw)
