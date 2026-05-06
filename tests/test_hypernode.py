"""Tests for Empty Quadrant revenue hypernode ontology, council, and scoring."""

from __future__ import annotations

from fastapi.testclient import TestClient

from dharma_swarm.api import create_app
from dharma_swarm.hypernode import (
    ACTION_PROPOSAL_ID,
    CLAIM_ID,
    COUNCIL_VERDICT_ID,
    DOCTRINE_ID,
    EVIDENCE_ID,
    FITNESS_VECTOR_ID,
    HYPERNODE_ID,
    QUESTION_ID,
    REVENUE_CELL_ID,
    SIGNAL_ID,
    VALUE_EVENT_ID,
    build_empty_quadrant_payload,
    evaluate_hypernode_council,
    score_hypernode,
)
from dharma_swarm.hypernode_seed import ensure_empty_quadrant_hypernode
from dharma_swarm.ontology import OntologyRegistry


def test_hypernode_types_register_in_canonical_registry() -> None:
    registry = OntologyRegistry.create_dharma_registry()
    for type_name in ("Hypernode", "RevenueCell", "CouncilVerdict", "FitnessVector"):
        assert registry.get_type(type_name) is not None

    hypernode_links = {link.name for link in registry.get_links_for("Hypernode")}
    assert "has_revenue_cell" in hypernode_links
    assert "has_council_verdict" in hypernode_links
    assert "has_fitness_vector" in hypernode_links
    assert "grounded_in_signal" in hypernode_links
    assert "has_value_event" in hypernode_links


def test_empty_quadrant_seed_creates_canonical_object_chains() -> None:
    registry = OntologyRegistry.create_dharma_registry()
    seeded = ensure_empty_quadrant_hypernode(registry)

    assert seeded.errors == []
    assert registry.get_object(HYPERNODE_ID).type_name == "Hypernode"
    assert registry.get_object(REVENUE_CELL_ID).type_name == "RevenueCell"
    assert registry.get_object(COUNCIL_VERDICT_ID).type_name == "CouncilVerdict"
    assert registry.get_object(FITNESS_VECTOR_ID).type_name == "FitnessVector"

    expected_links = {
        ("opens_question", SIGNAL_ID, QUESTION_ID),
        ("answered_by_claim", QUESTION_ID, CLAIM_ID),
        ("claim_has_evidence", CLAIM_ID, EVIDENCE_ID),
        ("derived_from_claim", DOCTRINE_ID, CLAIM_ID),
        ("has_gate_decision", ACTION_PROPOSAL_ID, "gate-empty-quadrant-page"),
        ("has_value_event", "outcome-empty-quadrant-page", VALUE_EVENT_ID),
    }
    actual_links = {
        (link.link_name, link.source_id, link.target_id)
        for link in registry.get_links()
    }
    assert expected_links.issubset(actual_links)


def test_empty_quadrant_seed_is_idempotent() -> None:
    registry = OntologyRegistry.create_dharma_registry()
    first = ensure_empty_quadrant_hypernode(registry)
    object_count = registry.stats()["total_objects"]
    link_count = registry.stats()["total_links"]
    second = ensure_empty_quadrant_hypernode(registry)

    assert first.errors == []
    assert second.errors == []
    assert registry.stats()["total_objects"] == object_count
    assert registry.stats()["total_links"] == link_count


def test_council_records_anekanta_steelman_dogma_and_mirofish() -> None:
    verdict = evaluate_hypernode_council()

    assert verdict.decision == "warn"
    assert verdict.gate_results["ANEKANTA"] == "PASS"
    assert verdict.gate_results["STEELMAN"] == "PASS"
    assert verdict.gate_results["DOGMA_DRIFT"] == "PASS"
    assert verdict.gate_results["MIROFISH"] == "WARN"
    assert verdict.mirofish_activated is True
    assert set(verdict.anekanta_frames) == {"mechanistic", "phenomenological", "systems"}


def test_fitness_scoring_uses_autograde_council_provenance_and_market() -> None:
    payload = build_empty_quadrant_payload()
    fitness = score_hypernode(payload.council_verdict, payload.revenue_cell)

    assert fitness.auto_grade_score >= 0.80
    assert fitness.council_score > 0
    assert fitness.provenance_score == 1.0
    assert fitness.market_value_score == 0.5
    assert fitness.composite_score >= fitness.promotion_threshold
    assert fitness.promotion_state == "public_artifact_ready"
    assert payload.revenue_cell.verified_revenue_usd == 0.0
    assert payload.revenue_cell.evidence_tier == "internal_estimate"


def test_api_returns_hypernode_payload_and_seeds_registry() -> None:
    registry = OntologyRegistry.create_dharma_registry()
    client = TestClient(create_app(registry=registry))

    response = client.get("/api/hypernodes/empty-quadrant")
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["id"] == HYPERNODE_ID
    assert data["slug"] == "empty-quadrant-revenue-cell"
    assert "High-governance, welfare-oriented" in data["thesis"]
    assert data["fitness_vector"]["promotion_state"] == "public_artifact_ready"
    assert data["council_verdict"]["gate_results"]["MIROFISH"] == "WARN"
    assert data["object_chain"]["inquiry"] == [
        SIGNAL_ID,
        QUESTION_ID,
        CLAIM_ID,
        EVIDENCE_ID,
        DOCTRINE_ID,
    ]
    assert registry.get_objects_by_type("Hypernode")[0].id == HYPERNODE_ID
