"""Minimal Council substrate + the ``orchestration_trace_verification`` profile.

Adopts the MINIMAL Council interface from #662 (spec §10 step 1) following the
decorrelated-moat pattern — NOT gated on full #662 or the world-ingestion seam.

The Council VERIFIES trace integrity, contamination boundaries, evidence
sufficiency, and the "this genome beat controls" promotion claim. It does NOT
score, plan, dispatch, or judge correctness (spec §2). Every verification is
pure and deterministic so receipts replay exactly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from dharma_swarm.council.invariants import (
    DISPATCH_AUTHORITY,
    Verdict,
    meets_decorrelation,
)

ORCHESTRATION_TRACE_VERIFICATION = "orchestration_trace_verification"


@dataclass(frozen=True)
class TraceVerificationRequest:
    """What the Council is asked to verify about one arena attempt.

    ``scorecard`` is the deterministic scorer's output — the Council reads it as
    EVIDENCE (the correctness authority's verdict), it does not recompute or
    second-guess correctness. ``promotion_claim`` is the "this genome beat
    controls" assertion the Council checks against that evidence.
    """

    genome_id: str
    route_receipts: list[dict[str, Any]] = field(default_factory=list)
    trace_receipts: list[dict[str, Any]] = field(default_factory=list)
    scorecard: Optional[dict[str, Any]] = None
    promotion_claim: Optional[dict[str, Any]] = None
    # Anti-contamination signal from the arena (spec §6 invariant 1).
    untrusted: bool = False
    contamination_findings: tuple[str, ...] = ()

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "profile": ORCHESTRATION_TRACE_VERIFICATION,
            "genome_id": self.genome_id,
            "route_receipts": self.route_receipts,
            "trace_receipts": self.trace_receipts,
            "scorecard": self.scorecard,
            "promotion_claim": self.promotion_claim,
            "untrusted": self.untrusted,
            "contamination_findings": list(self.contamination_findings),
        }

    def inputs_hash(self) -> str:
        payload = json.dumps(self.canonical_payload(), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CouncilReceipt:
    """Replayable Council verdict. NEVER carries dispatch authority in this build."""

    profile: str
    genome_id: str
    verdict: Verdict
    inputs_hash: str
    evaluator_families: tuple[str, ...]
    source_families: tuple[str, ...]
    findings: tuple[str, ...]
    quarantined: bool
    # Hidden-action-authority invariant: always False unless a LATER warrant
    # layer transforms it (spec §2). Not transformable in this keystone.
    dispatch_authority: bool = DISPATCH_AUTHORITY

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "genome_id": self.genome_id,
            "verdict": self.verdict,
            "inputs_hash": self.inputs_hash,
            "evaluator_families": list(self.evaluator_families),
            "source_families": list(self.source_families),
            "findings": list(self.findings),
            "quarantined": self.quarantined,
            "dispatch_authority": self.dispatch_authority,
        }


class Council:
    """One verifier substrate; profiles differ only in schema + thresholds.

    Only the ``orchestration_trace_verification`` profile is implemented in this
    keystone (spec §10 step 1). Other profiles named in §2
    (world_signal_verification, code_patch_verification, ...) are deliberately
    left to later steps — adding them must not weaken these shared invariants.
    """

    def verify_orchestration_trace(
        self, request: TraceVerificationRequest
    ) -> CouncilReceipt:
        """Run the decorrelated evaluator families over an orchestration trace.

        Pure & deterministic: the same request always yields the same verdict and
        the same ``inputs_hash`` (replayability invariant).
        """
        inputs_hash = request.inputs_hash()
        findings: list[str] = []
        evaluator_families: set[str] = set()
        source_families: set[str] = set()

        def receipt(verdict: Verdict, *, quarantined: bool = False) -> CouncilReceipt:
            return CouncilReceipt(
                profile=ORCHESTRATION_TRACE_VERIFICATION,
                genome_id=request.genome_id,
                verdict=verdict,
                inputs_hash=inputs_hash,
                evaluator_families=tuple(sorted(evaluator_families)),
                source_families=tuple(sorted(source_families)),
                findings=tuple(findings),
                quarantined=quarantined,
            )

        # --- Source families: independent origins of evidence present in the request.
        if request.route_receipts:
            source_families.add("route_receipts")
        if request.trace_receipts:
            source_families.add("trace_receipts")
        if request.scorecard is not None:
            source_families.add("scorer_oracle")

        # --- Evaluator family 1: contamination boundary (runs first; can quarantine).
        contamination_findings = list(request.contamination_findings)
        if request.untrusted or contamination_findings:
            evaluator_families.add("contamination_boundary")
            findings.append("contamination_boundary:quarantine")
            findings.extend(f"contamination:{c}" for c in contamination_findings)
            return receipt("quarantined", quarantined=True)

        evaluator_families.add("contamination_boundary")
        findings.append("contamination_boundary:clear")

        # --- Evaluator family 2: trace integrity (receipts present & consistent).
        # Every receipt offered as evidence MUST carry the requested genome_id —
        # a missing or mismatched id means the receipt is not tied to this genome
        # and cannot corroborate it (it must not silently count toward the moat).
        if request.route_receipts or request.trace_receipts:
            evaluator_families.add("trace_integrity")
            bad = [
                r.get("genome_id")
                for r in (request.route_receipts + request.trace_receipts)
                if r.get("genome_id") != request.genome_id
            ]
            if bad:
                findings.append("trace_integrity:genome_id_missing_or_mismatch")
                return receipt("refuted")
            findings.append("trace_integrity:consistent")

        # --- Evaluator family 3: evidence sufficiency (scorer output present).
        # The Council reads the scorer's verdict as evidence; it never recomputes
        # correctness (correctness-authority split, spec §2). The scorecard must be
        # tied to THIS genome to be admissible evidence.
        scorecard = request.scorecard
        if scorecard is not None:
            evaluator_families.add("evidence_sufficiency")
            scorecard_genome = scorecard.get("genome_id")
            if scorecard_genome is not None and scorecard_genome != request.genome_id:
                findings.append("evidence_sufficiency:scorecard_genome_mismatch")
                return receipt("refuted")
            findings.append("evidence_sufficiency:scorecard_present")

        # --- Evaluator family 4: promotion claim ("this genome beat controls").
        # Verifies the CLAIM against the SCORER EVIDENCE — not the claim's own
        # self-asserted numbers. A stale/forged claim cannot be corroborated: the
        # claimed candidate_score must match the scorecard the scorer produced for
        # this genome (spec §2/§6 — the Council never trusts the claimant's word).
        claim = request.promotion_claim
        if claim is not None:
            evaluator_families.add("promotion_claim")
            cand = _as_float(claim.get("candidate_score"))
            base = _as_float(claim.get("baseline_score"))
            parity = bool(claim.get("budget_parity_logged", False))
            if cand is None or base is None:
                findings.append("promotion_claim:missing_scores")
                return receipt("insufficient")
            # The claim must be backed by scorer evidence, not asserted in a vacuum.
            if scorecard is None:
                findings.append("promotion_claim:no_scorer_evidence")
                return receipt("insufficient")
            scorer_score = _as_float(scorecard.get("score"))
            if scorer_score is None or abs(scorer_score - cand) > 1e-9:
                findings.append("promotion_claim:candidate_score_disagrees_with_scorer")
                return receipt("refuted")
            if not parity:
                # Beating best-single by spending more is theater (spec §3).
                findings.append("promotion_claim:budget_parity_not_logged")
                return receipt("refuted")
            if cand <= base:
                findings.append("promotion_claim:not_supported(candidate<=baseline)")
                return receipt("refuted")
            findings.append("promotion_claim:supported")

        # --- Final verdict by the decorrelated moat.
        if meets_decorrelation(evaluator_families, source_families):
            findings.append("decorrelation:met")
            return receipt("corroborated")
        findings.append(
            f"decorrelation:not_met(eval={len(evaluator_families)},src={len(source_families)})"
        )
        return receipt("insufficient")


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "ORCHESTRATION_TRACE_VERIFICATION",
    "Council",
    "CouncilReceipt",
    "TraceVerificationRequest",
]
