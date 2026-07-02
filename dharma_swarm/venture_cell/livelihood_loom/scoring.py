"""Candidate scoring for Livelihood Loom enrichment."""

from __future__ import annotations

from dataclasses import dataclass

from dharma_swarm.venture_cell.livelihood_loom.ontology import EnablerCompany, RiskClass

LIVELIHOOD_RELEVANT_SECTORS = {
    "finance",
    "finance_rails",
    "commerce",
    "market_access",
    "agriculture",
    "recycling",
    "care",
    "craft",
    "food",
    "logistics",
    "digital_work",
    "platform_work",
    "identity",
    "trust_rails",
    "training",
    "local_services",
}


@dataclass(frozen=True)
class LivelihoodFitScore:
    company_id: str
    score: float
    reasons: tuple[str, ...]
    blocked: bool = False


def score_enabler(company: EnablerCompany) -> LivelihoodFitScore:
    score = 0.0
    reasons: list[str] = []
    if company.source_refs:
        score += 0.2
        reasons.append("has_source_refs")
    if company.enablement_levers:
        score += 0.25
        reasons.append("has_enablement_levers")
    if company.sector in LIVELIHOOD_RELEVANT_SECTORS:
        score += 0.25
        reasons.append("livelihood_relevant_sector")
    if company.risk_class == RiskClass.LOW:
        score += 0.2
        reasons.append("low_initial_risk")
    if company.geography and company.geography != "unknown":
        score += 0.1
        reasons.append("geography_known")
    blocked = company.risk_class == RiskClass.VULNERABLE_PERSON_RISK
    if blocked:
        reasons.append("requires_human_safety_review")
    return LivelihoodFitScore(
        company_id=company.company_id,
        score=round(min(score, 1.0), 3),
        reasons=tuple(reasons),
        blocked=blocked,
    )
