"""Revenue intelligence parser — models and claim extraction.

Enums, Pydantic models, and deterministic parser functions for extracting
structured claims from raw competitive intelligence text.  The heavier
``RevenueIntelligenceIngestor`` class lives in ``intelligence.py``.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_INTEL_DIR = Path.home() / ".dharma" / "revenue_intel"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_INTEL_COUNTER = 0


def _intel_id(prefix: str) -> str:
    global _INTEL_COUNTER
    _INTEL_COUNTER += 1
    return f"{prefix}-{int(time.time() * 1000) % 1_000_000_000}-{_INTEL_COUNTER}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ClaimType(str, Enum):
    COMPETITOR = "competitor"
    MARKET_SIZE = "market_size"
    PRICING = "pricing"
    PATTERN = "pattern"
    GAP = "gap"
    TECHNOLOGY = "technology"
    REVENUE_MODEL = "revenue_model"
    REGULATION = "regulation"
    ECOSYSTEM = "ecosystem"
    COMPUTE_MARKET = "compute_market"
    CRYPTO_ECONOMY = "crypto_economy"


class ActionabilityLevel(str, Enum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    STRATEGIC = "strategic"


class IntelSource(str, Enum):
    MANUAL = "manual"
    WEB_SCRAPE = "web_scrape"
    API = "api"
    RESEARCH_ENGINE = "research_engine"
    OPERATOR_INPUT = "operator_input"
    STIGMERGY = "stigmergy"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class IntelClaim(BaseModel):
    """A single structured claim extracted from raw intelligence."""

    id: str = Field(default_factory=lambda: _intel_id("clm"))
    claim_type: ClaimType
    entity: str
    statement: str
    evidence: str = ""
    numbers: dict[str, Any] = Field(default_factory=dict)
    actionability: ActionabilityLevel = ActionabilityLevel.MEDIUM_TERM
    revenue_relevance: float = 0.0
    confidence: float = 0.5
    source_id: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now_iso)


class IntelDocument(BaseModel):
    """A raw intelligence document to be parsed."""

    id: str = Field(default_factory=lambda: _intel_id("doc"))
    title: str
    content: str
    source: IntelSource = IntelSource.MANUAL
    source_url: str = ""
    ingested_at: str = Field(default_factory=_utc_now_iso)
    claims_extracted: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompetitorProfile(BaseModel):
    """Structured profile of a competitor or ecosystem player."""

    id: str = Field(default_factory=lambda: _intel_id("cmp"))
    name: str
    category: str = ""
    description: str = ""
    market_cap_usd: float = 0.0
    revenue_model: str = ""
    key_features: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    dharma_swarm_advantage: str = ""
    relevance_score: float = 0.0
    source_claims: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=_utc_now_iso)


class RevenuePattern(BaseModel):
    """A revenue-generating pattern identified from market intelligence."""

    id: str = Field(default_factory=lambda: _intel_id("pat"))
    name: str
    description: str
    examples: list[str] = Field(default_factory=list)
    estimated_tam_usd: float = 0.0
    implementation_complexity: str = "medium"
    time_to_revenue_days: int = 30
    requires: list[str] = Field(default_factory=list)
    dharma_swarm_fit: float = 0.0
    source_claims: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now_iso)


class IngestResult(BaseModel):
    """Result of ingesting a single document."""

    document_id: str
    claims_extracted: int = 0
    competitors_identified: int = 0
    patterns_identified: int = 0
    top_claims: list[IntelClaim] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


_MONEY_RE = re.compile(
    r"\$[\d,.]+[KMBTkmbt]?|\d+[\d,.]*\s*(?:billion|million|thousand|[KMBTkmbt])\b",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?%")
_PLAYER_MARKERS = [
    "ServiceNow", "Microsoft", "OpenAI", "AWS", "Amazon", "Anthropic",
    "Google", "Cursor", "Devin", "Harvey", "Legora", "RunPod", "Lambda",
    "CoreWeave", "Akash", "Vast", "Bittensor", "Virtuals", "TruthTerminal",
    "ai16z", "MakerDAO", "Aave", "Compound", "Sakana", "Prime Intellect",
    "Gensyn", "Sahara", "Coinbase",
]


def _extract_money_values(text: str) -> list[dict[str, Any]]:
    """Extract dollar amounts and financial figures from text."""
    values: list[dict[str, Any]] = []
    for match in _MONEY_RE.finditer(text):
        raw = match.group()
        context_start = max(0, match.start() - 80)
        context_end = min(len(text), match.end() + 80)
        values.append({
            "raw": raw,
            "context": text[context_start:context_end].strip(),
            "position": match.start(),
        })
    return values


def _extract_percentages(text: str) -> list[dict[str, str]]:
    """Extract percentage figures from text."""
    results: list[dict[str, str]] = []
    for match in _PERCENT_RE.finditer(text):
        context_start = max(0, match.start() - 60)
        context_end = min(len(text), match.end() + 60)
        results.append({
            "raw": match.group(),
            "context": text[context_start:context_end].strip(),
        })
    return results


def _identify_players(text: str) -> list[str]:
    """Identify known market players mentioned in text."""
    found: list[str] = []
    text_lower = text.lower()
    for player in _PLAYER_MARKERS:
        if player.lower() in text_lower:
            found.append(player)
    return found


def _segment_by_paragraphs(text: str) -> list[str]:
    """Split text into meaningful segments for claim extraction."""
    paragraphs = re.split(r"\n\s*\n|\n(?=\d+\.\s)", text)
    return [p.strip() for p in paragraphs if len(p.strip()) > 30]


def parse_claims(doc: IntelDocument) -> list[IntelClaim]:
    """Extract structured claims from a raw intelligence document."""
    claims: list[IntelClaim] = []
    segments = _segment_by_paragraphs(doc.content)

    for segment in segments:
        players = _identify_players(segment)
        money_values = _extract_money_values(segment)
        percentages = _extract_percentages(segment)

        for player in players:
            numbers: dict[str, Any] = {}
            if money_values:
                numbers["financial_figures"] = [v["raw"] for v in money_values[:3]]
            if percentages:
                numbers["percentages"] = [p["raw"] for p in percentages[:3]]

            claim_type = ClaimType.COMPETITOR
            if any(kw in segment.lower() for kw in ["revenue", "price", "cost", "pay", "earn"]):
                claim_type = ClaimType.REVENUE_MODEL
            elif any(kw in segment.lower() for kw in ["gpu", "compute", "training"]):
                claim_type = ClaimType.COMPUTE_MARKET
            elif any(kw in segment.lower() for kw in ["token", "crypto", "chain", "dao", "defi"]):
                claim_type = ClaimType.CRYPTO_ECONOMY
            elif any(kw in segment.lower() for kw in ["pattern", "lesson", "key"]):
                claim_type = ClaimType.PATTERN

            relevance = 0.3
            if money_values:
                relevance += 0.2
            if percentages:
                relevance += 0.1
            if any(kw in segment.lower() for kw in [
                "dharma_swarm", "governance", "gate", "provenance", "audit"
            ]):
                relevance += 0.3

            actionability = ActionabilityLevel.MEDIUM_TERM
            if any(kw in segment.lower() for kw in ["immediately", "now", "first", "today"]):
                actionability = ActionabilityLevel.IMMEDIATE
            elif any(kw in segment.lower() for kw in ["should", "next", "build", "create"]):
                actionability = ActionabilityLevel.SHORT_TERM

            first_sentence = segment.split(".")[0].strip()
            if len(first_sentence) > 200:
                first_sentence = first_sentence[:200] + "..."

            claim = IntelClaim(
                claim_type=claim_type,
                entity=player,
                statement=first_sentence,
                evidence=segment[:500],
                numbers=numbers,
                actionability=actionability,
                revenue_relevance=min(relevance, 1.0),
                confidence=0.7 if money_values else 0.5,
                source_id=doc.id,
                tags=[player.lower().replace(" ", "_")],
            )
            claims.append(claim)

        if not players and (money_values or percentages):
            gap_keywords = ["missing", "lack", "gap", "no ", "without", "don't have"]
            is_gap = any(kw in segment.lower() for kw in gap_keywords)

            claim = IntelClaim(
                claim_type=ClaimType.GAP if is_gap else ClaimType.MARKET_SIZE,
                entity="market",
                statement=segment.split(".")[0].strip()[:200],
                evidence=segment[:500],
                numbers={
                    "financial_figures": [v["raw"] for v in money_values[:3]],
                    "percentages": [p["raw"] for p in percentages[:3]],
                },
                actionability=ActionabilityLevel.SHORT_TERM if is_gap else ActionabilityLevel.MEDIUM_TERM,
                revenue_relevance=0.6 if is_gap else 0.4,
                confidence=0.6,
                source_id=doc.id,
                tags=["market_intel"],
            )
            claims.append(claim)

    return claims


def build_competitor_profiles(claims: list[IntelClaim]) -> list[CompetitorProfile]:
    """Aggregate claims into competitor profiles."""
    by_entity: dict[str, list[IntelClaim]] = {}
    for claim in claims:
        if claim.claim_type in (ClaimType.COMPETITOR, ClaimType.REVENUE_MODEL,
                                 ClaimType.TECHNOLOGY, ClaimType.CRYPTO_ECONOMY):
            by_entity.setdefault(claim.entity, []).append(claim)

    profiles: list[CompetitorProfile] = []
    for entity, entity_claims in by_entity.items():
        if entity == "market":
            continue
        features = [c.statement for c in entity_claims[:5]]
        categories = [c.claim_type.value for c in entity_claims]
        primary_category = max(set(categories), key=categories.count)

        avg_relevance = sum(c.revenue_relevance for c in entity_claims) / len(entity_claims)

        profile = CompetitorProfile(
            name=entity,
            category=primary_category,
            description=entity_claims[0].evidence[:200] if entity_claims else "",
            key_features=features,
            relevance_score=avg_relevance,
            source_claims=[c.id for c in entity_claims],
        )
        profiles.append(profile)

    return sorted(profiles, key=lambda p: p.relevance_score, reverse=True)


def identify_revenue_patterns(claims: list[IntelClaim]) -> list[RevenuePattern]:
    """Identify actionable revenue patterns from claims."""
    patterns: list[RevenuePattern] = []

    pattern_keywords = {
        "governance_as_product": ["governance", "control plane", "audit", "registry", "lifecycle"],
        "agent_eval_service": ["eval", "measure", "quality", "benchmark", "score"],
        "vertical_specialization": ["legal", "finance", "coding", "vertical", "specific"],
        "compute_marketplace": ["gpu", "compute", "runtime", "hosting", "cloud"],
        "token_economics": ["token", "treasury", "wallet", "staking", "emission"],
        "slop_detection": ["slop", "dead code", "provenance", "unsafe", "gap"],
    }

    pattern_claims: dict[str, list[IntelClaim]] = {k: [] for k in pattern_keywords}
    for claim in claims:
        text = (claim.statement + " " + claim.evidence).lower()
        for pattern_name, keywords in pattern_keywords.items():
            if any(kw in text for kw in keywords):
                pattern_claims[pattern_name].append(claim)

    pattern_configs = {
        "governance_as_product": {
            "name": "Governance-as-a-Product",
            "description": "Sell agent governance infrastructure as a product category",
            "time_to_revenue_days": 30,
            "complexity": "medium",
        },
        "agent_eval_service": {
            "name": "Agent Eval Service",
            "description": "Paid evaluation and benchmarking of AI agent quality",
            "time_to_revenue_days": 14,
            "complexity": "low",
        },
        "vertical_specialization": {
            "name": "Vertical AI Governance",
            "description": "Specialized governance for legal, finance, or coding AI",
            "time_to_revenue_days": 60,
            "complexity": "high",
        },
        "compute_marketplace": {
            "name": "Compute Treasury",
            "description": "Budget-aware compute routing with ROI tracking per run",
            "time_to_revenue_days": 90,
            "complexity": "high",
        },
        "token_economics": {
            "name": "Token-Gated Agent Economy",
            "description": "Agents with telos-gated treasuries and on-chain economics",
            "time_to_revenue_days": 120,
            "complexity": "high",
        },
        "slop_detection": {
            "name": "AI Slop Detection & Repair",
            "description": "Automated detection and governed repair of AI-generated code debt",
            "time_to_revenue_days": 7,
            "complexity": "low",
        },
    }

    for pattern_name, related_claims in pattern_claims.items():
        if not related_claims:
            continue
        config = pattern_configs[pattern_name]
        avg_relevance = sum(c.revenue_relevance for c in related_claims) / len(related_claims)

        pattern = RevenuePattern(
            name=config["name"],
            description=config["description"],
            examples=[c.entity for c in related_claims[:5]],
            implementation_complexity=config["complexity"],
            time_to_revenue_days=config["time_to_revenue_days"],
            dharma_swarm_fit=avg_relevance,
            source_claims=[c.id for c in related_claims],
        )
        patterns.append(pattern)

    return sorted(patterns, key=lambda p: (p.dharma_swarm_fit, -p.time_to_revenue_days), reverse=True)
