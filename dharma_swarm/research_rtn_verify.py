"""VERIFY node for the Research RTN — cross-reference claims across sources."""

from __future__ import annotations

from dataclasses import dataclass, field

from dharma_swarm.auto_research.models import ClaimRecord, SourceDocument


@dataclass
class VerificationResult:
    verified_claims: list[ClaimRecord] = field(default_factory=list)
    contradicted_claims: list[ClaimRecord] = field(default_factory=list)
    unsupported_claims: list[ClaimRecord] = field(default_factory=list)
    contradiction_pairs: list[tuple[str, str]] = field(default_factory=list)
    verification_score: float = 0.0


def _source_texts(sources: list[SourceDocument]) -> dict[str, str]:
    return {
        s.source_id: f"{s.title} {s.content}".lower()
        for s in sources
    }


def _claim_supported_by(claim_text: str, source_text: str) -> bool:
    words = [w for w in claim_text.lower().split() if len(w) > 3]
    if not words:
        return False
    matched = sum(1 for w in words if w in source_text)
    return (matched / len(words)) >= 0.3


def _claims_contradict(a: str, b: str) -> bool:
    negation_pairs = [
        ("increase", "decrease"),
        ("improve", "worsen"),
        ("support", "contradict"),
        ("confirm", "deny"),
        ("positive", "negative"),
        ("success", "failure"),
        ("effective", "ineffective"),
        ("significant", "insignificant"),
    ]
    a_low, b_low = a.lower(), b.lower()
    for pos, neg in negation_pairs:
        if (pos in a_low and neg in b_low) or (neg in a_low and pos in b_low):
            return True
    return False


def verify_claims(
    claims: list[ClaimRecord],
    sources: list[SourceDocument],
) -> VerificationResult:
    if not claims:
        return VerificationResult(verification_score=1.0)

    source_texts = _source_texts(sources)
    verified: list[ClaimRecord] = []
    contradicted: list[ClaimRecord] = []
    unsupported: list[ClaimRecord] = []
    contradiction_pairs: list[tuple[str, str]] = []

    for claim in claims:
        support_count = 0
        new_supporting: list[str] = list(claim.supporting_source_ids)
        new_contradicting: list[str] = list(claim.contradicting_source_ids)

        for sid, text in source_texts.items():
            if sid in claim.supporting_source_ids:
                support_count += 1
                continue
            if _claim_supported_by(claim.text, text):
                support_count += 1
                if sid not in new_supporting:
                    new_supporting.append(sid)

        updated = claim.model_copy(update={
            "supporting_source_ids": new_supporting,
            "contradicting_source_ids": new_contradicting,
        })

        if support_count >= 2:
            updated = updated.model_copy(update={
                "support_level": "verified",
                "confidence": min(1.0, claim.confidence + 0.1),
            })
            verified.append(updated)
        elif support_count == 1:
            verified.append(updated)
        else:
            updated = updated.model_copy(update={
                "support_level": "unsupported",
                "confidence": max(0.0, claim.confidence - 0.2),
            })
            unsupported.append(updated)

    for i, a in enumerate(claims):
        for b in claims[i + 1:]:
            if _claims_contradict(a.text, b.text):
                contradiction_pairs.append((a.claim_id, b.claim_id))
                if a not in contradicted:
                    contradicted.append(a.model_copy(update={"support_level": "contradicted"}))
                if b not in contradicted:
                    contradicted.append(b.model_copy(update={"support_level": "contradicted"}))

    total = len(claims)
    verified_count = len(verified)
    score = verified_count / total if total > 0 else 1.0

    return VerificationResult(
        verified_claims=verified,
        contradicted_claims=contradicted,
        unsupported_claims=unsupported,
        contradiction_pairs=contradiction_pairs,
        verification_score=score,
    )
