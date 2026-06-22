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

        # --- Source families: independent origins of evidence present in the request.
        source_families: set[str] = set()
        if request.route_receipts:
            source_families.add("route_receipts")
        if request.trace_receipts:
            source_families.add("trace_receipts")
        if request.scorecard is not None:
            source_families.add("scorer_oracle")

        # --- Evaluator family 1: contamination boundary (runs first; can quarantine).
        contamination_findings = list(request.contamination_findings)
        if request.untrusted or contamination_findings:
            findings.append("contamination_boundary:quarantine")
            findings.extend(f"contamination:{c}" for c in contamination_findings)
            return CouncilReceipt(
                profile=ORCHESTRATION_TRACE_VERIFICATION,
                genome_id=request.genome_id,
                verdict="quarantined",
                inputs_hash=inputs_hash,
                evaluator_families=("contamination_boundary",),
                source_families=tuple(sorted(source_families)),
                findings=tuple(findings),
                quarantined=True,
            )

        evaluator_families: set[str] = {"contamination_boundary"}
        findings.append("contamination_boundary:clear")

        # --- Evaluator family 2: trace integrity (receipts present & consistent).
        if request.route_receipts or request.trace_receipts:
            evaluator_families.add("trace_integrity")
            mismatches = [
                r.get("genome_id")
                for r in (request.route_receipts + request.trace_receipts)
                if r.get("genome_id") not in (None, request.genome_id)
            ]
            if mismatches:
                findings.append("trace_integrity:genome_id_mismatch")
                return CouncilReceipt(
                    profile=ORCHESTRATION_TRACE_VERIFICATION,
                    genome_id=request.genome_id,
                    verdict="refuted",
                    inputs_hash=inputs_hash,
                    evaluator_families=tuple(sorted(evaluator_families)),
                    source_families=tuple(sorted(source_families)),
                    findings=tuple(findings),
                    quarantined=False,
                )
            findings.append("trace_integrity:consistent")

        # --- Evaluator family 3: evidence sufficiency (scorer output present).
        # The Council reads the scorer's verdict as evidence; it never recomputes
        # correctness (correctness-authority split, spec §2).
        if request.scorecard is not None:
            evaluator_families.add("evidence_sufficiency")
            findings.append("evidence_sufficiency:scorecard_present")

        # --- Evaluator family 4: promotion claim ("this genome beat controls").
        # Verifies the CLAIM against the scorer numbers — not the answers.
        claim = request.promotion_claim
        if claim is not None:
            evaluator_families.add("promotion_claim")
            cand = _as_float(claim.get("candidate_score"))
            base = _as_float(claim.get("baseline_score"))
            parity = bool(claim.get("budget_parity_logged", False))
            if cand is None or base is None:
                findings.append("promotion_claim:missing_scores")
                return CouncilReceipt(
                    profile=ORCHESTRATION_TRACE_VERIFICATION,
                    genome_id=request.genome_id,
                    verdict="insufficient",
                    inputs_hash=inputs_hash,
                    evaluator_families=tuple(sorted(evaluator_families)),
                    source_families=tuple(sorted(source_families)),
                    findings=tuple(findings),
                    quarantined=False,
                )
            if not parity:
                # Beating best-single by spending more is theater (spec §3).
                findings.append("promotion_claim:budget_parity_not_logged")
                return CouncilReceipt(
                    profile=ORCHESTRATION_TRACE_VERIFICATION,
                    genome_id=request.genome_id,
                    verdict="refuted",
                    inputs_hash=inputs_hash,
                    evaluator_families=tuple(sorted(evaluator_families)),
                    source_families=tuple(sorted(source_families)),
                    findings=tuple(findings),
                    quarantined=False,
                )
            if cand <= base:
                findings.append("promotion_claim:not_supported(candidate<=baseline)")
                return CouncilReceipt(
                    profile=ORCHESTRATION_TRACE_VERIFICATION,
                    genome_id=request.genome_id,
                    verdict="refuted",
                    inputs_hash=inputs_hash,
                    evaluator_families=tuple(sorted(evaluator_families)),
                    source_families=tuple(sorted(source_families)),
                    findings=tuple(findings),
                    quarantined=False,
                )
            findings.append("promotion_claim:supported")

        # --- Final verdict by the decorrelated moat.
        if meets_decorrelation(evaluator_families, source_families):
            verdict: Verdict = "corroborated"
            findings.append("decorrelation:met")
        else:
            verdict = "insufficient"
            findings.append(
                f"decorrelation:not_met(eval={len(evaluator_families)},src={len(source_families)})"
            )

        return CouncilReceipt(
            profile=ORCHESTRATION_TRACE_VERIFICATION,
            genome_id=request.genome_id,
            verdict=verdict,
            inputs_hash=inputs_hash,
            evaluator_families=tuple(sorted(evaluator_families)),
            source_families=tuple(sorted(source_families)),
            findings=tuple(findings),
            quarantined=False,
        )


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
