"""Tests for the RevenueIntelligenceIngestor."""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.revenue.intel_parser import (
    ClaimType,
    CompetitorProfile,
    IntelDocument,
    IntelSource,
    RevenuePattern,
    build_competitor_profiles,
    identify_revenue_patterns,
    parse_claims,
)
from dharma_swarm.revenue.intelligence import RevenueIntelligenceIngestor


SAMPLE_INTEL = """
ServiceNow Autonomous Workforce handles 90%+ employee IT requests and is
99% faster in early results. Role-scoped AI specialists for IT, CRM, HR,
finance, legal, security. Agents resolve cases, update systems, escalate,
and leave audit trails.

Microsoft Agent 365 is a control plane for agents: registry, lifecycle,
audit logging, access control, security, governance. Governance itself is
becoming a product category.

Bittensor (TAO) is a decentralized AI marketplace with ~$2-3B market cap
and ~80 active subnets. Each subnet incentivizes a specific AI capability.
Subnet-1 alone pays out millions/year to model providers.

Virtuals Protocol on Base chain has AI agents with their own ERC-20 tokens,
wallets, and treasuries. Luna ($30-100M), AIXBT ($300M+ at peak).

The first income wedge should be an Agentic Code Governance Sprint:
audit repos for AI slop, dead code, provenance gaps, unsafe agents.
Install packet provenance, CI gates, evals, and audit ledger.
"""


@pytest.fixture()
def ingestor(tmp_path: Path) -> RevenueIntelligenceIngestor:
    return RevenueIntelligenceIngestor(storage_dir=tmp_path / "intel")


class TestParsing:
    def test_parse_claims_extracts_players(self) -> None:
        doc = IntelDocument(
            title="Test",
            content=SAMPLE_INTEL,
            source=IntelSource.MANUAL,
        )
        claims = parse_claims(doc)
        entities = {c.entity for c in claims}
        assert "ServiceNow" in entities
        assert "Microsoft" in entities

    def test_parse_claims_extracts_money(self) -> None:
        doc = IntelDocument(
            title="Test",
            content=SAMPLE_INTEL,
            source=IntelSource.MANUAL,
        )
        claims = parse_claims(doc)
        money_claims = [c for c in claims if c.numbers.get("financial_figures")]
        assert len(money_claims) > 0

    def test_parse_claims_identifies_types(self) -> None:
        doc = IntelDocument(
            title="Test",
            content=SAMPLE_INTEL,
            source=IntelSource.MANUAL,
        )
        claims = parse_claims(doc)
        types = {c.claim_type for c in claims}
        assert len(types) > 1


class TestCompetitorProfiles:
    def test_build_profiles(self) -> None:
        doc = IntelDocument(
            title="Test", content=SAMPLE_INTEL, source=IntelSource.MANUAL,
        )
        claims = parse_claims(doc)
        profiles = build_competitor_profiles(claims)
        names = {p.name for p in profiles}
        assert "ServiceNow" in names or "Microsoft" in names
        assert all(p.relevance_score > 0 for p in profiles)


class TestRevenuePatterns:
    def test_identify_patterns(self) -> None:
        doc = IntelDocument(
            title="Test", content=SAMPLE_INTEL, source=IntelSource.MANUAL,
        )
        claims = parse_claims(doc)
        patterns = identify_revenue_patterns(claims)
        assert len(patterns) > 0
        names = {p.name for p in patterns}
        assert any("Governance" in n or "Slop" in n for n in names)


class TestIngestor:
    def test_ingest_text(self, ingestor: RevenueIntelligenceIngestor) -> None:
        result = ingestor.ingest_text(SAMPLE_INTEL, title="Test Intel")
        assert result.claims_extracted > 0
        assert result.document_id != ""

    def test_ingest_file(self, ingestor: RevenueIntelligenceIngestor, tmp_path: Path) -> None:
        intel_file = tmp_path / "test_intel.md"
        intel_file.write_text(SAMPLE_INTEL)
        result = ingestor.ingest_file(intel_file)
        assert result.claims_extracted > 0

    def test_summary(self, ingestor: RevenueIntelligenceIngestor) -> None:
        ingestor.ingest_text(SAMPLE_INTEL, title="Test")
        summary = ingestor.summary()
        assert summary["documents_ingested"] == 1
        assert summary["total_claims"] > 0
        assert len(summary["revenue_patterns"]) > 0

    def test_route_to_spine(self, ingestor: RevenueIntelligenceIngestor, tmp_path: Path) -> None:
        from dharma_swarm.revenue.spine import EconomicSpine
        spine = EconomicSpine(storage_dir=tmp_path / "spine")
        ingestor.ingest_text(SAMPLE_INTEL, title="Test")
        created = ingestor.route_to_spine(spine)
        assert created > 0
        targets = spine.list_targets()
        assert len(targets) > 0

    def test_persistence(self, tmp_path: Path) -> None:
        storage = tmp_path / "intel"
        ing1 = RevenueIntelligenceIngestor(storage_dir=storage)
        ing1.ingest_text(SAMPLE_INTEL, title="Test")
        count1 = len(ing1.get_claims())

        ing2 = RevenueIntelligenceIngestor(storage_dir=storage)
        count2 = len(ing2.get_claims())
        assert count2 == count1

    def test_get_claims_filtered(self, ingestor: RevenueIntelligenceIngestor) -> None:
        ingestor.ingest_text(SAMPLE_INTEL, title="Test")
        all_claims = ingestor.get_claims()
        high_claims = ingestor.get_claims(min_relevance=0.5)
        assert len(high_claims) <= len(all_claims)
