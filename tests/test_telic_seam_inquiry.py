from __future__ import annotations

import pytest

from dharma_swarm.lineage import LineageGraph
from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.telic_seam import TelicSeam


@pytest.fixture
def registry() -> OntologyRegistry:
    return OntologyRegistry.create_dharma_registry()


@pytest.fixture
def seam(registry: OntologyRegistry, tmp_path) -> TelicSeam:
    return TelicSeam(
        registry=registry,
        lineage=LineageGraph(db_path=tmp_path / "lineage.db"),
    )


def _agent(
    registry: OntologyRegistry,
    name: str,
    *,
    is_principal: bool = False,
) -> str:
    obj, errors = registry.create_object(
        "AgentIdentity",
        {
            "name": name,
            "role": "operator" if is_principal else "worker",
            "status": "idle",
            "is_principal": is_principal,
        },
        created_by="test",
    )
    assert obj is not None, errors
    return obj.id


def test_record_signal_creates_signal_and_observer_link(
    seam: TelicSeam,
    registry: OntologyRegistry,
) -> None:
    observer_id = _agent(registry, "observer")

    signal_id = seam.record_signal(
        "user_note",
        "The inquiry chain should surface open claims.",
        observer_id,
        source_kind="user_note",
    )

    assert signal_id is not None
    signal = registry.get_object(signal_id)
    assert signal is not None
    assert signal.type_name == "Signal"
    assert signal.properties["source_kind"] == "user_note"
    assert signal.properties["observer_ref"] == observer_id
    assert registry.get_links(
        source_id=signal_id,
        target_id=observer_id,
        link_name="observed_by",
    )


def test_record_question_creates_open_question(
    seam: TelicSeam,
    registry: OntologyRegistry,
) -> None:
    opener_id = _agent(registry, "questioner")

    question_id = seam.record_question(
        "What evidence would falsify this claim?",
        opener_id,
        domain="governance",
        priority="high",
    )

    assert question_id is not None
    question = registry.get_object(question_id)
    assert question is not None
    assert question.type_name == "Question"
    assert question.properties["lifecycle_state"] == "open"
    assert question.properties["priority"] == "high"
    assert registry.get_links(
        source_id=question_id,
        target_id=opener_id,
        link_name="opened_by",
    )


def test_record_claim_uses_proposed_lifecycle_and_links_question(
    seam: TelicSeam,
    registry: OntologyRegistry,
) -> None:
    proposer_id = _agent(registry, "proposer")
    question_id = seam.record_question("Should this be accepted?", proposer_id)
    assert question_id is not None

    claim_id = seam.record_claim(
        "Phase 1 inquiry chain writes through the ontology.",
        proposer_id,
        confidence=0.72,
        parent_question_id=question_id,
    )

    assert claim_id is not None
    claim = registry.get_object(claim_id)
    assert claim is not None
    assert claim.type_name == "Claim"
    assert claim.properties["lifecycle_state"] == "proposed"
    assert claim.properties["confidence"] == 0.72
    assert registry.get_links(
        source_id=claim_id,
        target_id=proposer_id,
        link_name="claim_proposed_by",
    )
    assert registry.get_links(
        source_id=question_id,
        target_id=claim_id,
        link_name="answered_by_claim",
    )


def test_record_evidence_creates_linked_evidence(
    seam: TelicSeam,
    registry: OntologyRegistry,
) -> None:
    proposer_id = _agent(registry, "evidence-attacher")
    claim_id = seam.record_claim("Evidence must be typed.", proposer_id)
    assert claim_id is not None

    evidence_id = seam.record_evidence(
        claim_id,
        "citation",
        "supports",
        proposer_id,
        source_artifact_ref="docs/plans/example.md",
        strength=0.8,
    )

    assert evidence_id is not None
    evidence = registry.get_object(evidence_id)
    assert evidence is not None
    assert evidence.type_name == "Evidence"
    assert evidence.properties["claim_ref"] == claim_id
    assert evidence.properties["direction"] == "supports"
    assert registry.get_links(
        source_id=claim_id,
        target_id=evidence_id,
        link_name="claim_has_evidence",
    )


def test_record_doctrine_requires_principal_signer(
    seam: TelicSeam,
    registry: OntologyRegistry,
) -> None:
    worker_id = _agent(registry, "not-principal")

    doctrine_id = seam.record_doctrine(
        "Only a principal can sign Doctrine rows.",
        worker_id,
    )

    assert doctrine_id is None
    assert registry.get_objects_by_type("Doctrine") == []


def test_record_doctrine_uses_schema_fields_and_links_claim(
    seam: TelicSeam,
    registry: OntologyRegistry,
) -> None:
    principal_id = _agent(registry, "dhyana", is_principal=True)
    claim_id = seam.record_claim(
        "R_V_Measurement is not a peer ObjectType.",
        principal_id,
        confidence=0.95,
    )
    assert claim_id is not None

    doctrine_id = seam.record_doctrine(
        "R_V_Measurement remains represented through Experiment fields.",
        principal_id,
        derived_from_claim_id=claim_id,
    )

    assert doctrine_id is not None
    doctrine = registry.get_object(doctrine_id)
    assert doctrine is not None
    assert doctrine.type_name == "Doctrine"
    assert doctrine.properties["lifecycle_state"] == "signed"
    assert "kernel_signature" in doctrine.properties
    assert "signed_by_human_at" in doctrine.properties
    assert "signer_agent_id" not in doctrine.properties
    assert registry.get_links(
        source_id=doctrine_id,
        target_id=claim_id,
        link_name="derived_from_claim",
    )
