"""GAIA/reciprocity adapter for livelihood outcome records."""

from __future__ import annotations

from dharma_swarm.venture_cell.livelihood_loom.ontology import OutcomeClaim


def outcome_to_gaia_record(outcome: OutcomeClaim) -> dict[str, object]:
    return {
        "schema": "gaia.livelihood_outcome.v1",
        "subject_ref": outcome.subject_ref,
        "outcome_metric": outcome.outcome_metric,
        "outcome_value": outcome.outcome_value,
        "evidence_refs": list(outcome.evidence_refs),
        "audit_status": outcome.audit_status,
        "source_claim_id": outcome.claim_id,
    }
