"""Aggregation rules for Dharma slop governance findings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from dharma_swarm.slop.models import (
    ActionDecision,
    ModuleScore,
    RouterAction,
    SlopFinding,
)

DEFAULT_FAMILY_WEIGHTS: dict[str, float] = {
    "structure": 0.25,
    "dead_code": 0.20,
    "complexity": 0.20,
    "ai_slop": 0.20,
    "provenance": 0.15,
    "security": 0.20,
    "type_safety": 0.15,
    "dependency": 0.15,
    "coverage": 0.15,
    "behavior": 0.15,
    "semantic": 0.15,
    "adversarial": 0.15,
}


def _bounded(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def aggregate_probability(
    family_scores: Mapping[str, float],
    *,
    weights: Mapping[str, float] | None = None,
    agreement_threshold: float = 0.35,
    min_agreement: int = 2,
) -> float:
    """Aggregate detector-family scores without allowing one family to block."""

    if not family_scores:
        return 0.0

    weights = weights or DEFAULT_FAMILY_WEIGHTS
    probability_not_slop = 1.0

    for family, score in family_scores.items():
        weight = _bounded(weights.get(str(family), 0.10))
        probability_not_slop *= 1.0 - (_bounded(score) * weight)

    probability = 1.0 - probability_not_slop
    agreement = sum(1 for score in family_scores.values() if score >= agreement_threshold)

    if agreement < min_agreement:
        return min(probability, 0.49)
    return _bounded(probability)


def score_module(path: str, findings: Sequence[SlopFinding]) -> ModuleScore:
    """Score one module from already-normalized detector findings."""

    family_scores: dict[str, float] = {}
    module_findings = [finding for finding in findings if finding.path == path]

    for finding in module_findings:
        family = finding.detector_family.value
        family_scores[family] = max(
            family_scores.get(family, 0.0),
            finding.confidence,
        )

    return ModuleScore(
        path=path,
        slop_probability=aggregate_probability(family_scores),
        family_scores=family_scores,
        findings=module_findings,
        introduced=any(finding.introduced for finding in module_findings),
    )


def route_probability(probability: float, *, introduced: bool = False) -> ActionDecision:
    """Map a slop probability to the staged action policy."""

    p = _bounded(probability)
    if p < 0.30:
        return ActionDecision(
            action=RouterAction.LOG,
            blocks=False,
            reason="below warning threshold",
        )
    if p < 0.50:
        return ActionDecision(
            action=RouterAction.WARN,
            blocks=False,
            reason="advisory range",
        )
    if p < 0.80:
        return ActionDecision(
            action=RouterAction.BLOCK_REGRESSION,
            blocks=introduced,
            reason="blocks only when introduced versus base",
            requires_human_review=True,
        )
    return ActionDecision(
        action=RouterAction.OPEN_REFACTOR_PR,
        blocks=introduced,
        reason="high-confidence slop requires reviewed refactor branch",
        requires_human_review=True,
    )
