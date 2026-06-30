"""Formal telos gates -- measured invariants, not keyword bingo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Optional

import numpy as np

from dharma_swarm.models import GateDecision, GateResult, GateTier
from dharma_swarm.telos_formal_math import EPS, effective_rank, shannon_entropy
from dharma_swarm.telos_formal_math import von_neumann_entropy
from dharma_swarm.telos_formal_models import (
    ActionContext,
    BeliefState,
    DataLabel,
    EvaluatorJudgment,
    FormalGateName,
    FormalGateReport,
    FormalGateResult,
    InformationFlow,
    ProvenanceClaim,
)

__all__ = [
    "ActionContext",
    "BeliefState",
    "DataLabel",
    "EvaluatorJudgment",
    "FormalGateName",
    "FormalGateResult",
    "FormalGateReport",
    "FormalTelosGatekeeper",
    "InformationFlow",
    "ProvenanceClaim",
    "anekanta_contextuality_gate",
    "effective_rank",
    "epistemic_humility_gate",
    "evaluate_formal_gates",
    "noninterference_gate",
    "observer_separation_gate",
    "provenance_integrity_gate",
    "requisite_variety_gate",
    "shannon_entropy",
    "von_neumann_entropy",
]


def _skip(gate: FormalGateName, tier: GateTier, why: str) -> FormalGateResult:
    return FormalGateResult(
        gate=gate,
        tier=tier,
        result=GateResult.PASS,
        measure=float("nan"),
        threshold=float("nan"),
        reason=f"skipped: {why}",
    )


def epistemic_humility_gate(
    belief: Optional[BeliefState],
    min_entropy_bits: float = 0.05,
) -> FormalGateResult:
    gate = FormalGateName.EPISTEMIC_HUMILITY
    tier = GateTier.B
    if belief is None:
        return _skip(gate, tier, "no belief state provided")
    entropy = belief.entropy(base=2.0)
    if entropy > min_entropy_bits:
        return FormalGateResult(
            gate=gate,
            tier=tier,
            result=GateResult.PASS,
            measure=entropy,
            threshold=min_entropy_bits,
            reason=f"S(rho)={entropy:.4f} bits > {min_entropy_bits}",
        )
    return FormalGateResult(
        gate=gate,
        tier=tier,
        result=GateResult.FAIL,
        measure=entropy,
        threshold=min_entropy_bits,
        reason=(
            f"belief is effectively certain (S(rho)={entropy:.4f} bits "
            f"<= {min_entropy_bits}); certainty is forbidden"
        ),
    )


def anekanta_contextuality_gate(
    judgments: Sequence[EvaluatorJudgment],
    min_effective_evaluators: float = 2.0,
) -> FormalGateResult:
    gate = FormalGateName.ANEKANTA_CONTEXTUALITY
    tier = GateTier.C
    if len(judgments) < 2:
        return _skip(gate, tier, "fewer than 2 evaluators")
    dim = len(judgments[0].vector)
    if any(len(j.vector) != dim for j in judgments):
        raise ValueError("all judgment vectors must share one dimensionality")
    matrix = np.asarray([j.vector for j in judgments], dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms < EPS] = 1.0
    unit = matrix / norms
    gram = unit @ unit.T
    erank = effective_rank(gram)
    detail = {"n_evaluators": len(judgments), "effective_rank": erank}
    if erank >= min_effective_evaluators - EPS:
        return FormalGateResult(
            gate=gate,
            tier=tier,
            result=GateResult.PASS,
            measure=erank,
            threshold=min_effective_evaluators,
            reason=f"effective rank {erank:.3f} >= {min_effective_evaluators}",
            detail=detail,
        )
    return FormalGateResult(
        gate=gate,
        tier=tier,
        result=GateResult.WARN,
        measure=erank,
        threshold=min_effective_evaluators,
        reason=(
            f"evaluators are near-collinear (effective rank {erank:.3f} < "
            f"{min_effective_evaluators}); not genuine many-sidedness"
        ),
        detail=detail,
    )


def requisite_variety_gate(
    regulator_distribution: Optional[Sequence[float]],
    disturbance_distribution: Optional[Sequence[float]],
) -> FormalGateResult:
    gate = FormalGateName.REQUISITE_VARIETY
    tier = GateTier.C
    if regulator_distribution is None or disturbance_distribution is None:
        return _skip(gate, tier, "regulator/disturbance distributions absent")
    h_reg = shannon_entropy(regulator_distribution)
    h_dist = shannon_entropy(disturbance_distribution)
    gap = h_reg - h_dist
    detail = {"H_regulator": h_reg, "H_disturbance": h_dist}
    if gap >= -EPS:
        return FormalGateResult(
            gate=gate,
            tier=tier,
            result=GateResult.PASS,
            measure=gap,
            threshold=0.0,
            reason=f"H(reg)={h_reg:.3f} >= H(dist)={h_dist:.3f}",
            detail=detail,
        )
    return FormalGateResult(
        gate=gate,
        tier=tier,
        result=GateResult.WARN,
        measure=gap,
        threshold=0.0,
        reason=(
            f"insufficient requisite variety: H(reg)={h_reg:.3f} < "
            f"H(dist)={h_dist:.3f}"
        ),
        detail=detail,
    )


def provenance_integrity_gate(
    claims: Sequence[ProvenanceClaim],
    high_confidence_threshold: float = 0.85,
) -> FormalGateResult:
    gate = FormalGateName.PROVENANCE_INTEGRITY
    tier = GateTier.B
    if not claims:
        return _skip(gate, tier, "no provenance claims provided")
    orphans = [
        c.claim_id
        for c in claims
        if c.confidence >= high_confidence_threshold and not c.evidence_ids
    ]
    detail = {"orphan_claims": orphans, "n_claims": len(claims)}
    if not orphans:
        return FormalGateResult(
            gate=gate,
            tier=tier,
            result=GateResult.PASS,
            measure=0.0,
            threshold=0.0,
            reason="all high-confidence claims carry evidence",
            detail=detail,
        )
    return FormalGateResult(
        gate=gate,
        tier=tier,
        result=GateResult.FAIL,
        measure=float(len(orphans)),
        threshold=0.0,
        reason=(
            f"{len(orphans)} high-confidence claim(s) without evidence: "
            f"{', '.join(orphans)}"
        ),
        detail=detail,
    )


def noninterference_gate(flows: Sequence[InformationFlow]) -> FormalGateResult:
    gate = FormalGateName.NON_INTERFERENCE
    tier = GateTier.A
    if not flows:
        return _skip(gate, tier, "no information flows declared")
    leaks = [
        f
        for f in flows
        if f.source_label == DataLabel.HIGH and f.sink_is_public and not f.declassified
    ]
    detail = {"n_flows": len(flows), "leaks": len(leaks)}
    if not leaks:
        return FormalGateResult(
            gate=gate,
            tier=tier,
            result=GateResult.PASS,
            measure=0.0,
            threshold=0.0,
            reason="no high->public information flow",
            detail=detail,
        )
    return FormalGateResult(
        gate=gate,
        tier=tier,
        result=GateResult.FAIL,
        measure=float(len(leaks)),
        threshold=0.0,
        reason=(
            f"{len(leaks)} undeclassified HIGH->public flow(s): "
            f"non-interference violated"
        ),
        detail=detail,
    )


def observer_separation_gate(
    observer_id: Optional[str],
    observed_id: Optional[str],
    measures_state: bool,
    mutates_state: bool,
) -> FormalGateResult:
    gate = FormalGateName.OBSERVER_SEPARATION
    tier = GateTier.A
    if observer_id is None and observed_id is None and not measures_state:
        return _skip(gate, tier, "no observation declared")
    if observer_id is not None and observer_id == observed_id:
        return FormalGateResult(
            gate=gate,
            tier=tier,
            result=GateResult.FAIL,
            measure=1.0,
            threshold=0.0,
            reason=f"observer == observed ({observer_id})",
        )
    if measures_state and mutates_state:
        return FormalGateResult(
            gate=gate,
            tier=tier,
            result=GateResult.FAIL,
            measure=1.0,
            threshold=0.0,
            reason="single transaction both measures and mutates the same state",
        )
    return FormalGateResult(
        gate=gate,
        tier=tier,
        result=GateResult.PASS,
        measure=0.0,
        threshold=0.0,
        reason="observer separated from observed; measure/mutate disjoint",
    )


def evaluate_formal_gates(context: ActionContext) -> FormalGateReport:
    results = [
        observer_separation_gate(
            context.observer_id,
            context.observed_id,
            context.measures_state,
            context.mutates_state,
        ),
        noninterference_gate(context.information_flows),
        epistemic_humility_gate(context.belief, context.min_entropy_bits),
        provenance_integrity_gate(
            context.provenance_claims, context.high_confidence_threshold
        ),
        anekanta_contextuality_gate(
            context.evaluator_judgments, context.min_effective_evaluators
        ),
        requisite_variety_gate(
            context.regulator_distribution, context.disturbance_distribution
        ),
    ]

    def _failed(tier: GateTier) -> bool:
        return any(r.tier == tier and r.result == GateResult.FAIL for r in results)

    if _failed(GateTier.A) or _failed(GateTier.B):
        decision = GateDecision.BLOCK
    elif any(
        r.tier == GateTier.C and r.result in (GateResult.FAIL, GateResult.WARN)
        for r in results
    ):
        decision = GateDecision.REVIEW
    else:
        decision = GateDecision.ALLOW

    report = FormalGateReport(decision=decision, results=results)
    report.receipt_sha256 = report.compute_receipt()
    return report


class FormalTelosGatekeeper:
    """Compose the legacy keyword gatekeeper with the formal measured gates."""

    def __init__(self, keyword_gatekeeper: Any | None = None) -> None:
        if keyword_gatekeeper is None:
            from dharma_swarm.telos_gates import TelosGatekeeper

            keyword_gatekeeper = TelosGatekeeper()
        self._keyword = keyword_gatekeeper

    def check(
        self,
        context: ActionContext,
        *,
        content: str = "",
        tool_name: str = "",
        run_keyword_prefilter: bool = True,
    ) -> tuple[GateDecision, FormalGateReport, Optional[Mapping[str, Any]]]:
        keyword_payload: Optional[Mapping[str, Any]] = None
        if run_keyword_prefilter:
            keyword_check = self._keyword.check(
                action=context.action, content=content, tool_name=tool_name
            )
            keyword_payload = {
                "decision": keyword_check.decision,
                "gate": keyword_check.gate,
                "reason": keyword_check.reason,
            }
            if keyword_check.decision == GateDecision.BLOCK:
                blocked = evaluate_formal_gates(context)
                return GateDecision.BLOCK, blocked, keyword_payload

        report = evaluate_formal_gates(context)
        return report.decision, report, keyword_payload
