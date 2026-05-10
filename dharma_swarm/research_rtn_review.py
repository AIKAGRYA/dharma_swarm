"""REVIEW node for the Research RTN — gap analysis and feedback to PLAN."""

from __future__ import annotations

from dataclasses import dataclass, field

from dharma_swarm.auto_research.models import ResearchBrief, ResearchReport
from dharma_swarm.auto_grade.models import RewardSignal
from dharma_swarm.research_rtn_verify import VerificationResult


@dataclass
class ReviewResult:
    gaps: list[str] = field(default_factory=list)
    follow_up_briefs: list[ResearchBrief] = field(default_factory=list)
    strength_summary: str = ""
    weakness_summary: str = ""
    should_recurse: bool = False
    review_score: float = 0.0


def _detect_gaps(
    report: ResearchReport,
    verification: VerificationResult,
    reward: RewardSignal,
) -> list[str]:
    gaps: list[str] = []

    if verification.unsupported_claims:
        count = len(verification.unsupported_claims)
        gaps.append(f"{count} unsupported claim(s) need additional sources")

    if verification.contradiction_pairs:
        count = len(verification.contradiction_pairs)
        gaps.append(f"{count} contradiction pair(s) need resolution")

    if len(report.source_ids) < 3:
        gaps.append("Fewer than 3 sources — breadth insufficient")

    card = reward.grade_card
    if card.freshness < 0.5:
        gaps.append("Low freshness score — need more recent sources")
    if card.source_diversity < 0.5:
        gaps.append("Low source diversity — broaden search domains")
    if card.novelty < 0.3:
        gaps.append("Low novelty — findings are mostly common knowledge")
    if card.actionability < 0.4:
        gaps.append("Low actionability — need more concrete findings")

    for gate in reward.grade_card.gate_failures:
        gaps.append(f"Hard gate failed: {gate}")

    return gaps


def _generate_follow_ups(
    original_brief: ResearchBrief,
    gaps: list[str],
    verification: VerificationResult,
) -> list[ResearchBrief]:
    follow_ups: list[ResearchBrief] = []
    track = original_brief.metadata.get("track", "unknown")
    base_id = original_brief.task_id

    if verification.unsupported_claims:
        texts = [c.text[:80] for c in verification.unsupported_claims[:3]]
        follow_ups.append(ResearchBrief(
            task_id=f"{base_id}-verify-unsupported",
            topic=original_brief.topic,
            question=f"Find supporting evidence for: {'; '.join(texts)}",
            audience=original_brief.audience,
            requires_recency=original_brief.requires_recency,
            source_budget=8,
            time_budget_seconds=180,
            metadata={"track": track, "parent_task": base_id, "review_type": "unsupported"},
        ))

    if verification.contradiction_pairs:
        follow_ups.append(ResearchBrief(
            task_id=f"{base_id}-resolve-contradictions",
            topic=original_brief.topic,
            question=f"Resolve contradictions in {original_brief.topic}: which claims are correct and why?",
            audience=original_brief.audience,
            requires_recency=True,
            source_budget=10,
            time_budget_seconds=240,
            metadata={"track": track, "parent_task": base_id, "review_type": "contradiction"},
        ))

    if any("breadth" in g or "diversity" in g for g in gaps):
        follow_ups.append(ResearchBrief(
            task_id=f"{base_id}-broaden",
            topic=original_brief.topic,
            question=f"Broader survey: {original_brief.question} (different domains and methodologies)",
            audience=original_brief.audience,
            requires_recency=original_brief.requires_recency,
            source_budget=15,
            time_budget_seconds=300,
            metadata={"track": track, "parent_task": base_id, "review_type": "breadth"},
        ))

    return follow_ups


def review_report(
    report: ResearchReport,
    verification: VerificationResult,
    reward: RewardSignal,
    original_brief: ResearchBrief,
    *,
    recurse_threshold: float = 0.6,
) -> ReviewResult:
    gaps = _detect_gaps(report, verification, reward)
    follow_ups = _generate_follow_ups(original_brief, gaps, verification)

    strengths: list[str] = []
    weaknesses: list[str] = []
    card = reward.grade_card

    if card.groundedness >= 0.85:
        strengths.append("strong grounding")
    else:
        weaknesses.append("weak grounding")

    if card.citation_precision >= 0.9:
        strengths.append("precise citations")
    else:
        weaknesses.append("citation issues")

    if verification.verification_score >= 0.8:
        strengths.append("well-verified claims")
    else:
        weaknesses.append("unverified claims")

    if card.final_score >= 0.7:
        strengths.append(f"good overall score ({card.final_score:.2f})")

    score = card.final_score
    should_recurse = score < recurse_threshold and len(follow_ups) > 0

    return ReviewResult(
        gaps=gaps,
        follow_up_briefs=follow_ups,
        strength_summary=", ".join(strengths) if strengths else "none identified",
        weakness_summary=", ".join(weaknesses) if weaknesses else "none identified",
        should_recurse=should_recurse,
        review_score=score,
    )
