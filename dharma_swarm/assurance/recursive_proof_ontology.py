"""Non-authoritative ontology mirror for recursive proof receipts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from dharma_swarm.ontology import OntologyObj, OntologyRegistry
from dharma_swarm.recursive_discovery import (
    CandidateDiffReceipt,
    ExperimentResultReceipt,
    GeneratedEvalReceipt,
    PromotionDecisionReceipt,
    RecursiveReceipt,
    WitnessVerdictReceipt,
    receipt_counts_by_type,
)


@dataclass(frozen=True)
class RecursiveProofOntologyMirrorResult:
    """Object IDs produced by the recursive proof ontology mirror."""

    experiment_ids: tuple[str, ...] = ()
    knowledge_artifact_ids: tuple[str, ...] = ()
    witness_log_ids: tuple[str, ...] = ()
    gate_decision_ids: tuple[str, ...] = ()
    link_ids: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    objects_by_receipt_id: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def mirror_recursive_receipts_to_ontology(
    receipts: Sequence[RecursiveReceipt],
    *,
    registry: OntologyRegistry | None = None,
    created_by: str = "recursive_proof_ontology_mirror",
) -> RecursiveProofOntologyMirrorResult:
    """Mirror recursive receipts into existing ontology object types.

    The mirror is intentionally read-only with respect to recursive semantics:
    candidate diffs remain no-apply, promotion decisions stay human-held, and
    the ontology objects are evidence projections rather than authorities.
    """

    reg = registry or OntologyRegistry.create_dharma_registry()
    errors: list[str] = []
    experiment_ids: list[str] = []
    artifact_ids: list[str] = []
    witness_ids: list[str] = []
    gate_decision_ids: list[str] = []
    link_ids: list[str] = []
    objects_by_receipt_id: dict[str, str] = {}

    for parent_id, chain in _group_receipts_by_parent(receipts).items():
        experiment = _create_experiment(
            reg,
            parent_id=parent_id,
            receipts=chain,
            created_by=created_by,
            errors=errors,
        )
        if experiment is None:
            continue
        experiment_ids.append(experiment.id)
        for receipt in chain:
            if isinstance(receipt, (GeneratedEvalReceipt, CandidateDiffReceipt, ExperimentResultReceipt)):
                artifact = _create_knowledge_artifact(
                    reg,
                    receipt=receipt,
                    created_by=created_by,
                    errors=errors,
                )
                if artifact is not None:
                    artifact_ids.append(artifact.id)
                    objects_by_receipt_id[receipt.receipt_id] = artifact.id
                    link = _create_link(
                        reg,
                        "produces",
                        experiment.id,
                        artifact.id,
                        created_by=created_by,
                        errors=errors,
                    )
                    if link is not None:
                        link_ids.append(link.id)
            elif isinstance(receipt, WitnessVerdictReceipt):
                witness = _create_witness_log(
                    reg,
                    receipt=receipt,
                    created_by=created_by,
                    errors=errors,
                )
                if witness is not None:
                    witness_ids.append(witness.id)
                    objects_by_receipt_id[receipt.receipt_id] = witness.id
            elif isinstance(receipt, PromotionDecisionReceipt):
                decision = _create_gate_decision(
                    reg,
                    receipt=receipt,
                    created_by=created_by,
                    errors=errors,
                )
                if decision is not None:
                    gate_decision_ids.append(decision.id)
                    objects_by_receipt_id[receipt.receipt_id] = decision.id

    return RecursiveProofOntologyMirrorResult(
        experiment_ids=tuple(experiment_ids),
        knowledge_artifact_ids=tuple(artifact_ids),
        witness_log_ids=tuple(witness_ids),
        gate_decision_ids=tuple(gate_decision_ids),
        link_ids=tuple(link_ids),
        errors=tuple(errors),
        objects_by_receipt_id=objects_by_receipt_id,
    )


def _group_receipts_by_parent(
    receipts: Sequence[RecursiveReceipt],
) -> dict[str, list[RecursiveReceipt]]:
    grouped: dict[str, list[RecursiveReceipt]] = {}
    for receipt in receipts:
        parent_id = receipt.parent_id or receipt.receipt_id
        grouped.setdefault(parent_id, []).append(receipt)
    return grouped


def _create_experiment(
    registry: OntologyRegistry,
    *,
    parent_id: str,
    receipts: Sequence[RecursiveReceipt],
    created_by: str,
    errors: list[str],
) -> OntologyObj | None:
    blocked = any(receipt.status == "blocked" for receipt in receipts)
    counts = receipt_counts_by_type(list(receipts))
    obj, obj_errors = registry.create_object(
        "Experiment",
        {
            "name": f"recursive proof run {parent_id}",
            "status": "failed" if blocked else "completed",
            "model": _first_nonempty(receipt.model_id for receipt in receipts),
            "config": {
                "parent_id": parent_id,
                "receipt_count": len(receipts),
                "receipt_counts": counts,
                "mirror_authority": "non_authoritative",
            },
            "results": {
                "candidate_diffs_applied": any(
                    bool(receipt.metadata.get("diff_applied"))
                    for receipt in receipts
                    if receipt.receipt_type == "candidate_diff"
                ),
                "promotion_decisions": [
                    getattr(receipt, "decision", "")
                    for receipt in receipts
                    if receipt.receipt_type == "promotion_decision"
                ],
            },
        },
        created_by=created_by,
    )
    if obj is None:
        errors.extend(f"Experiment:{parent_id}:{error}" for error in obj_errors)
    return obj


def _create_knowledge_artifact(
    registry: OntologyRegistry,
    *,
    receipt: GeneratedEvalReceipt | CandidateDiffReceipt | ExperimentResultReceipt,
    created_by: str,
    errors: list[str],
) -> OntologyObj | None:
    artifact_type = "code" if receipt.receipt_type in {"generated_eval", "candidate_diff"} else "result"
    obj, obj_errors = registry.create_object(
        "KnowledgeArtifact",
        {
            "title": f"{receipt.receipt_type} receipt {receipt.receipt_id}",
            "artifact_type": artifact_type,
            "domain": "dharma_swarm",
            "content": receipt.summary,
            "file_path": ",".join(receipt.files_touched),
            "provenance": f"recursive_discovery:{receipt.receipt_id}",
            "confidence": 1.0,
            "verified": True,
        },
        created_by=created_by,
    )
    if obj is None:
        errors.extend(f"KnowledgeArtifact:{receipt.receipt_id}:{error}" for error in obj_errors)
    return obj


def _create_witness_log(
    registry: OntologyRegistry,
    *,
    receipt: WitnessVerdictReceipt,
    created_by: str,
    errors: list[str],
) -> OntologyObj | None:
    verdicts = [
        f"{verdict.phase}:{verdict.verdict}:{verdict.reason}"
        for verdict in receipt.witness_verdicts
    ]
    obj, obj_errors = registry.create_object(
        "WitnessLog",
        {
            "observation": receipt.summary or "; ".join(verdicts),
            "observer": _first_nonempty(
                verdict.witness_id for verdict in receipt.witness_verdicts
            )
            or "recursive_proof_witness",
            "context": f"recursive_discovery:{receipt.receipt_id}",
            "witness_quality": 0.8,
            "contraction_level": "governed-no-apply",
        },
        created_by=created_by,
    )
    if obj is None:
        errors.extend(f"WitnessLog:{receipt.receipt_id}:{error}" for error in obj_errors)
    return obj


def _create_gate_decision(
    registry: OntologyRegistry,
    *,
    receipt: PromotionDecisionReceipt,
    created_by: str,
    errors: list[str],
) -> OntologyObj | None:
    obj, obj_errors = registry.create_object(
        "GateDecisionRecord",
        {
            "proposal_id": receipt.candidate_id or receipt.parent_id or receipt.receipt_id,
            "decision": _gate_decision_for_promotion(receipt),
            "reason": (
                f"recursive promotion decision {receipt.decision}; "
                "mirror is non-authoritative and human promotion remains required"
            ),
            "gate_results": {
                "recursive_promotion_boundary": {
                    "receipt_id": receipt.receipt_id,
                    "receipt_status": receipt.status,
                    "promotion_decision": receipt.decision,
                    "autonomous": False,
                }
            },
            "witness_reroutes": 0,
        },
        created_by=created_by,
    )
    if obj is None:
        errors.extend(f"GateDecisionRecord:{receipt.receipt_id}:{error}" for error in obj_errors)
    return obj


def _gate_decision_for_promotion(receipt: PromotionDecisionReceipt) -> str:
    if receipt.status == "blocked" or receipt.decision == "reject":
        return "block"
    return "review"


def _create_link(
    registry: OntologyRegistry,
    link_name: str,
    source_id: str,
    target_id: str,
    *,
    created_by: str,
    errors: list[str],
) -> Any | None:
    link, link_errors = registry.create_link(
        link_name,
        source_id,
        target_id,
        created_by=created_by,
        metadata={"mirror_authority": "non_authoritative"},
    )
    if link is None:
        errors.extend(f"Link:{source_id}:{link_name}:{target_id}:{error}" for error in link_errors)
    return link


def _first_nonempty(values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""
