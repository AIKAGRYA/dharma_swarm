"""EAS attestation payload builder for public non-PII livelihood claims."""

from __future__ import annotations

from dharma_swarm.venture_cell.livelihood_loom.ontology import PublicProofClaim


def build_eas_attestation_payload(claim: PublicProofClaim) -> dict[str, object]:
    public_payload = claim.to_public_payload()
    return {
        "schema": "livelihood_loom.public_outcome.v1",
        "recipient": "0x0000000000000000000000000000000000000000",
        "revocable": True,
        "data": public_payload,
    }
