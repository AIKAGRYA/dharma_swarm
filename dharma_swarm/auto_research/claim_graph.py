"""Claim graph extraction for AutoResearch."""

from __future__ import annotations

import re
from typing import Any

from .models import ClaimRecord, ResearchBrief, SourceDocument

_FACTUAL_PATTERN = re.compile(
    r'\d+%|\$\d|\d{4}|billion|million|thousand|increase|decrease|'
    r'outperform|significant|compared|versus|survey|study|report|'
    r'according|found that|showed|demonstrated|launched|raised|funded',
    re.IGNORECASE,
)
_MIN_CLAIM_LENGTH = 30
_MAX_CLAIM_LENGTH = 300


def _iter_claim_texts(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        texts: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                texts.append(text)
        return texts
    return []


def _extract_factual_sentences(content: str, max_claims: int = 10) -> list[str]:
    if not content or len(content) < _MIN_CLAIM_LENGTH:
        return []
    sentences = re.split(r'(?<=[.!?])\s+', content)
    factual: list[str] = []
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < _MIN_CLAIM_LENGTH or len(sent) > _MAX_CLAIM_LENGTH:
            continue
        if _FACTUAL_PATTERN.search(sent):
            factual.append(sent)
            if len(factual) >= max_claims:
                break
    return factual


class ClaimGraphBuilder:
    """Extract supported claims from normalized source metadata and content."""

    def build(
        self,
        brief: ResearchBrief,
        sources: list[SourceDocument],
    ) -> list[ClaimRecord]:
        claims: list[ClaimRecord] = []
        for source in sources:
            source_claims: list[str] = []
            # Priority 1: explicit claims in metadata
            source_claims.extend(_iter_claim_texts(source.metadata.get("claims")))
            # Priority 2: factual sentences from content
            if not source_claims and source.content:
                source_claims = _extract_factual_sentences(source.content)

            for text in source_claims:
                claims.append(
                    ClaimRecord(
                        claim_id=f"{brief.task_id}-claim-{len(claims) + 1}",
                        text=text,
                        support_level="supported",
                        supporting_source_ids=[source.source_id],
                        citations=[f"[{source.source_id}]"],
                        confidence=0.8,
                    )
                )
        return claims
