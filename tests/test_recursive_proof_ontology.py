from __future__ import annotations

from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.recursive_discovery import (
    CommandReceipt,
    build_recursive_shadow_run_receipts,
)
from dharma_swarm.assurance.recursive_proof_ontology import (
    mirror_recursive_receipts_to_ontology,
)


def test_recursive_receipts_mirror_to_existing_ontology_types_without_authority() -> None:
    registry = OntologyRegistry.create_dharma_registry()
    receipts = build_recursive_shadow_run_receipts(
        parent_id="foundry-run-001",
        limitation_id="lim-foundry-001",
        candidate_id="cand-foundry-001",
        eval_id="eval-foundry-001",
        prompt="Evaluate one no-apply foundry candidate.",
        model_id="deterministic-shadow",
        files_touched=["reports/evolution_foundry/README.md"],
        proof=CommandReceipt(command="python -c pass", exit_code=0),
        sandbox_path="/tmp/foundry/variant-01",
        source="evolution_foundry_shadow",
        metadata={"variant_id": "variant-01"},
    )

    result = mirror_recursive_receipts_to_ontology(receipts, registry=registry)

    assert result.ok is True
    assert len(result.experiment_ids) == 1
    assert len(result.knowledge_artifact_ids) == 3
    assert len(result.witness_log_ids) == 1
    assert len(result.gate_decision_ids) == 1
    assert len(result.link_ids) == 3
    assert len(registry.get_objects_by_type("Experiment")) == 1
    assert len(registry.get_objects_by_type("KnowledgeArtifact")) == 3
    assert len(registry.get_objects_by_type("WitnessLog")) == 1
    assert len(registry.get_objects_by_type("GateDecisionRecord")) == 1

    experiment = registry.get_object(result.experiment_ids[0])
    assert experiment is not None
    assert experiment.properties["results"]["candidate_diffs_applied"] is False
    assert experiment.properties["results"]["promotion_decisions"] == ["hold"]

    gate_decision = registry.get_object(result.gate_decision_ids[0])
    assert gate_decision is not None
    assert gate_decision.properties["decision"] == "review"
    assert "human promotion remains required" in gate_decision.properties["reason"]

    promotion_receipt = [r for r in receipts if r.receipt_type == "promotion_decision"][0]
    candidate_receipt = [r for r in receipts if r.receipt_type == "candidate_diff"][0]
    assert promotion_receipt.decision == "hold"
    assert candidate_receipt.metadata["diff_applied"] is False
