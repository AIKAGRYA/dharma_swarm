"""DecisionLog adapter for Darshan decision deltas."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.decision_ontology import (
    DecisionChallenge,
    DecisionClaim,
    DecisionContext,
    DecisionEvidence,
    DecisionLog,
    DecisionMetric,
    DecisionOption,
    DecisionRecord,
    DecisionState,
    EvidenceKind,
    ReviewVerdict,
    DecisionReview,
)
from dharma_swarm.venture_cell.darshan.bundle import validate_bundle
from dharma_swarm.venture_cell.darshan.schema import ClaimLedger, DecisionDelta, SourcePack


def record_decision_delta(
    bundle_path: Path,
    *,
    log_path: Path | None = None,
) -> DecisionRecord:
    result = validate_bundle(bundle_path)
    if not result.valid:
        raise ValueError("; ".join(result.errors))
    manifest = result.manifest
    if manifest is None:
        raise ValueError("bundle manifest missing")

    delta = DecisionDelta.model_validate(
        json.loads((result.bundle_path / "decision_delta.json").read_text(encoding="utf-8"))
    )
    claim_ledger = ClaimLedger.model_validate(
        json.loads((result.bundle_path / "claim_ledger.json").read_text(encoding="utf-8"))
    )
    source_pack = SourcePack.model_validate(
        json.loads((result.bundle_path / "source_pack.json").read_text(encoding="utf-8"))
    )
    selected_option = "ship_manual_artifact_transaction"
    decision = DecisionRecord(
        title=f"Materialize Darshan delta: {manifest.title}",
        statement=delta.delta_summary or "Materialize the Darshan artifact transaction.",
        state=DecisionState.PROPOSED,
        context=DecisionContext(
            mission="Prove Darshan as a world-facing conductor cell.",
            owner=delta.followup_owner or "Dhyana",
            time_horizon="Season 0 / 30 days",
            domains=["darshan", "attention", "publication", "venture_cell"],
            constraints=[
                "Polsia may operate the shell but not final claims or publishing.",
                "Every public artifact must create a substrate decision delta.",
            ],
            assumptions=["Manual artifact transaction precedes public CMS."],
            risk_score=0.45,
            uncertainty=0.45,
            novelty=0.7,
            urgency=0.65,
            expected_impact=0.75,
            reversible=True,
        ),
        options=[
            DecisionOption(
                option_id=selected_option,
                title="Materialize manual artifact transaction",
                description="Use the bundle to create memory, ontology, task, and decision records.",
                selected=True,
            ),
            DecisionOption(
                option_id="defer_until_public_site",
                title="Defer until public site exists",
                description="Wait to materialize substrate records until a public surface is live.",
            ),
        ],
        claims=[
            DecisionClaim(
                text=claim.claim_text,
                supports_option_id=selected_option,
                evidence_refs=claim.evidence_refs,
                confidence=claim.confidence,
            )
            for claim in claim_ledger.claims[:8]
        ],
        evidence=[
            DecisionEvidence(
                kind=EvidenceKind.PRIMARY_SOURCE
                if source.source_type.value in {"primary", "dataset", "public_record"}
                else EvidenceKind.MODEL_OUTPUT
                if source.source_type.value == "model_output"
                else EvidenceKind.USER_CONSTRAINT,
                summary=source.extracted_claims[0] if source.extracted_claims else source.canonical_url,
                source_uri=source.final_url or source.canonical_url,
                confidence=0.75 if source.trust_status.value in {"usable", "strong"} else 0.45,
                verified=source.trust_status.value in {"usable", "strong"},
                provenance_refs=[source.source_id],
            )
            for source in source_pack.sources[:8]
        ],
        challenges=[
            DecisionChallenge(
                summary="A beautiful article without substrate materialization would be only media.",
                addressed=True,
                response="This adapter records memory, ontology, task, and decision outputs.",
            ),
            DecisionChallenge(
                summary="A source pack without a public reader would be inward drift.",
                addressed=True,
                response="The artifact bundle keeps article.md as a required first-class surface.",
            ),
        ],
        metrics=[
            DecisionMetric(
                name="artifact_transaction_complete",
                target="one validated bundle materialized into memory, ontology, task, and decision log",
                measurement_plan="verify returned IDs and file paths after materialize-bundle",
                owner="darshan_venture_cell",
            )
        ],
        reviews=[
            DecisionReview(
                reviewer="codex",
                role="implementation",
                verdict=ReviewVerdict.PASS,
                notes="Adapter keeps publishing and final claim authority out of Polsia scope.",
            )
        ],
        next_actions=[
            "Review generated follow-up task.",
            "Use Polsia handoff only for operating shell tasks.",
        ],
        kill_criteria=[
            "No decision delta after three public artifacts.",
            "Polsia begins owning claims, voice, corrections, or public publishing.",
        ],
        provenance_refs=[str(result.bundle_path)],
        metadata={
            "artifact_id": manifest.artifact_id,
            "bundle_path": str(result.bundle_path),
            "season": manifest.season,
            "cell_id": "DARSHAN",
        },
    )
    DecisionLog(log_path).record(decision)
    return decision
