"""Tests for ShaktiZeitgeistExecutive Phase 1."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.shakti_zeitgeist_executive import (
    DOMAINS,
    SCORING_FACTORS,
    AllocationWeights,
    DomainBalance,
    ExecutiveCycleState,
    ExecutiveSignal,
    ScoredOpportunity,
    ShaktiZeitgeistExecutive,
)


# ---------------------------------------------------------------------------
# Model serialization
# ---------------------------------------------------------------------------


class TestModels:
    def test_executive_signal_roundtrip(self):
        sig = ExecutiveSignal(
            source="zeitgeist",
            category="threat",
            title="Competing R_V paper",
            relevance=0.8,
            urgency=1.0,
            domain="research",
            keywords=["contraction", "self-reference"],
        )
        data = sig.model_dump_json()
        restored = ExecutiveSignal.model_validate_json(data)
        assert restored.source == "zeitgeist"
        assert restored.relevance == 0.8
        assert restored.domain == "research"

    def test_scored_opportunity_has_all_12_factors(self):
        factors = {k: 0.5 for k in SCORING_FACTORS}
        opp = ScoredOpportunity(
            title="Test", domain="research", factor_scores=factors,
        )
        assert set(opp.factor_scores.keys()) == set(SCORING_FACTORS.keys())

    def test_allocation_weights_schema(self):
        w = AllocationWeights(
            per_domain={"research": 0.2, "reliability": 0.15},
            starvation_boosts={"ecosystem_scan": 0.3},
            churn_penalties={"internal_maintenance": 0.1},
        )
        data = json.loads(w.model_dump_json())
        assert "per_domain" in data
        assert "starvation_boosts" in data
        assert "churn_penalties" in data
        assert "timestamp" in data


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScoring:
    def _make_exec(self, tmp_path: Path) -> ShaktiZeitgeistExecutive:
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        (state_dir / "meta").mkdir()
        return ShaktiZeitgeistExecutive(state_dir=state_dir)

    def test_ranking_prefers_world_value_over_internal_churn(self, tmp_path: Path):
        exe = self._make_exec(tmp_path)
        research_sigs = [
            ExecutiveSignal(source="zeitgeist", category="opportunity",
                            title="New MI paper", relevance=0.7, domain="research"),
        ]
        internal_sigs = [
            ExecutiveSignal(source="zeitgeist", category="methodology",
                            title="Refactor swarm.py", relevance=0.7,
                            domain="internal_maintenance"),
        ]
        balances = exe._compute_domain_balance(research_sigs + internal_sigs)
        opps = exe._rank_opportunities(
            research_sigs + internal_sigs, balances, "general", {},
        )
        # Research (world-facing) should score higher than internal maintenance.
        research_opps = [o for o in opps if o.domain == "research"]
        internal_opps = [o for o in opps if o.domain == "internal_maintenance"]
        assert research_opps and internal_opps
        assert research_opps[0].final_score > internal_opps[0].final_score

    def test_starvation_boosts_opportunity_score(self, tmp_path: Path):
        exe = self._make_exec(tmp_path)
        sig = ExecutiveSignal(
            source="zeitgeist", category="opportunity",
            title="Revenue lead", relevance=0.6, domain="revenue_exploration",
        )
        # No other signals → revenue_exploration gets high starvation bonus.
        balances_starved = exe._compute_domain_balance([sig])
        opps_starved = exe._rank_opportunities([sig], balances_starved, "general", {})

        # Add many internal signals → revenue gets relatively more deficit.
        internal_flood = [
            ExecutiveSignal(source="zeitgeist", category="methodology",
                            title=f"Internal task {i}", relevance=0.5,
                            domain="internal_maintenance")
            for i in range(20)
        ]
        balances_flood = exe._compute_domain_balance([sig] + internal_flood)
        opps_flood = exe._rank_opportunities(
            [sig] + internal_flood, balances_flood, "general", {},
        )
        rev_flood = [o for o in opps_flood if o.domain == "revenue_exploration"]
        assert rev_flood
        # domain_balance_bonus should be > 0 because revenue is underrepresented.
        assert rev_flood[0].factor_scores["domain_balance_bonus"] > 0

    def test_repetition_penalty_lowers_score(self, tmp_path: Path):
        exe = self._make_exec(tmp_path)
        exe._recent_domains = ["research", "research", "research"]
        sig = ExecutiveSignal(
            source="zeitgeist", category="opportunity",
            title="Another MI experiment", relevance=0.7, domain="research",
        )
        balances = exe._compute_domain_balance([sig])
        opps = exe._rank_opportunities([sig], balances, "general", {})
        research_opp = [o for o in opps if o.domain == "research"]
        assert research_opp
        assert research_opp[0].factor_scores["repetition_penalty"] > 0

    def test_algedonic_pain_boosts_urgency(self, tmp_path: Path):
        exe = self._make_exec(tmp_path)
        pain_sig = ExecutiveSignal(
            source="algedonic", category="pain",
            title="Failure rate critical", relevance=0.9, urgency=1.0,
            domain="reliability",
        )
        normal_sig = ExecutiveSignal(
            source="zeitgeist", category="opportunity",
            title="New tool release", relevance=0.5, domain="reliability",
        )
        balances = exe._compute_domain_balance([pain_sig, normal_sig])
        opps = exe._rank_opportunities([pain_sig, normal_sig], balances, "general", {})
        rel_opp = [o for o in opps if o.domain == "reliability"]
        assert rel_opp
        assert rel_opp[0].factor_scores["algedonic_urgency"] > 0

    def test_memory_pressure_penalizes_internal_churn(self, tmp_path: Path):
        exe = self._make_exec(tmp_path)
        sig = ExecutiveSignal(
            source="zeitgeist", category="methodology",
            title="Refactor local coordination path", relevance=0.7,
            domain="internal_maintenance",
        )
        balances = exe._compute_domain_balance([sig])

        class _RoleEcology:
            underexpressed_roles: list[str] = []

        class _MemoryPressure:
            repeated_loop_signatures = ["eval_probe_loop:7", "latent_followup_loop:4"]
            unresolved_promises: list[str] = []

        opps = exe._rank_opportunities(
            [sig], balances, "general", {}, _RoleEcology(), _MemoryPressure(),
        )
        internal_opp = [o for o in opps if o.domain == "internal_maintenance"]
        assert internal_opp
        assert internal_opp[0].factor_scores["internal_churn_penalty"] > 0

    def test_underexpressed_roles_boost_strategic_infrastructure(self, tmp_path: Path):
        exe = self._make_exec(tmp_path)
        sig = ExecutiveSignal(
            source="zeitgeist", category="opportunity",
            title="Wire executive role ecology into mission loop", relevance=0.7,
            domain="strategic_infrastructure",
        )
        balances = exe._compute_domain_balance([sig])

        class _RoleEcology:
            underexpressed_roles = ["architect", "validator"]

        class _MemoryPressure:
            repeated_loop_signatures: list[str] = []
            unresolved_promises: list[str] = []

        opps = exe._rank_opportunities(
            [sig], balances, "general", {}, _RoleEcology(), _MemoryPressure(),
        )
        strat_opp = [o for o in opps if o.domain == "strategic_infrastructure"]
        assert strat_opp
        assert strat_opp[0].factor_scores["domain_balance_bonus"] > 0


# ---------------------------------------------------------------------------
# Domain balance
# ---------------------------------------------------------------------------


class TestDomainBalance:
    def test_domain_starvation_detected(self, tmp_path: Path):
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        (state_dir / "meta").mkdir()
        exe = ShaktiZeitgeistExecutive(state_dir=state_dir)

        # Only internal_maintenance signals → other domains starved.
        sigs = [
            ExecutiveSignal(source="zeitgeist", category="methodology",
                            title=f"Internal {i}", relevance=0.5,
                            domain="internal_maintenance")
            for i in range(10)
        ]
        balances = exe._compute_domain_balance(sigs)
        starved = [b for b in balances if b.starvation]
        # At least some domains should be starved (no signals, no timestamps).
        assert len(starved) >= 5

    def test_equal_distribution_no_starvation(self, tmp_path: Path):
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        (state_dir / "meta").mkdir()
        exe = ShaktiZeitgeistExecutive(state_dir=state_dir)

        # One signal per domain.
        sigs = [
            ExecutiveSignal(source="zeitgeist", category="opportunity",
                            title=f"Signal for {d}", relevance=0.5, domain=d)
            for d in DOMAINS
        ]
        balances = exe._compute_domain_balance(sigs)
        starved = [b for b in balances if b.starvation]
        assert len(starved) == 0


# ---------------------------------------------------------------------------
# Full cycle (integration)
# ---------------------------------------------------------------------------


class TestFullCycle:
    @pytest.mark.asyncio
    async def test_cycle_with_empty_state_dir(self, tmp_path: Path):
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        (state_dir / "meta").mkdir()
        exe = ShaktiZeitgeistExecutive(state_dir=state_dir)
        result = await exe.cycle()

        assert isinstance(result, ExecutiveCycleState)
        assert result.signals_ingested == 0
        assert result.opportunities == []
        assert result.duration_ms >= 0
        assert "role_ecology" in result.model_dump()
        assert "memory_pressure" in result.model_dump()

        # All 5 artifacts should exist.
        meta = state_dir / "meta"
        assert (meta / "shakti_executive_state.json").exists()
        assert (meta / "opportunity_board.json").exists()
        assert (meta / "allocation_weights.json").exists()
        assert (meta / "active_campaigns.json").exists()
        assert (meta / "executive_operator_summary.json").exists()
        assert (meta / "executive_briefs").is_dir()
        briefs = list((meta / "executive_briefs").glob("*.md"))
        assert len(briefs) == 1

    @pytest.mark.asyncio
    async def test_cycle_with_seeded_zeitgeist(self, tmp_path: Path):
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        meta = state_dir / "meta"
        meta.mkdir()

        # Seed zeitgeist.jsonl with a few signals.
        signals = [
            {"id": "sig1", "source": "local_scan", "category": "threat",
             "title": "Competing contraction paper found", "relevance_score": 0.9,
             "keywords": ["contraction", "self-reference"], "description": "",
             "timestamp": datetime.now(timezone.utc).isoformat()},
            {"id": "sig2", "source": "local_scan", "category": "opportunity",
             "title": "New carbon offset methodology released", "relevance_score": 0.7,
             "keywords": ["carbon", "offset"], "description": "",
             "timestamp": datetime.now(timezone.utc).isoformat()},
        ]
        with open(meta / "zeitgeist.jsonl", "w") as fh:
            for s in signals:
                fh.write(json.dumps(s) + "\n")

        exe = ShaktiZeitgeistExecutive(state_dir=state_dir)
        result = await exe.cycle()

        assert result.signals_ingested >= 2
        assert "zeitgeist" in result.signals_by_source

    @pytest.mark.asyncio
    async def test_cycle_surfaces_memory_pressure_and_role_ecology(self, tmp_path: Path):
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        meta = state_dir / "meta"
        meta.mkdir()
        (state_dir / "context" / "distilled").mkdir(parents=True)
        (state_dir / "shared").mkdir(parents=True)
        (state_dir / "cron_logs").mkdir(parents=True)
        (state_dir / "stigmergy").mkdir(parents=True)
        (state_dir / "vectors.db").write_bytes(b"x" * 1024)
        (state_dir / "context" / "distilled" / "builder_distilled.md").write_text("builder")
        (state_dir / "shared" / "aaa_synthesize_disagreement_eval_probe_task.md").write_text("a")
        (state_dir / "shared" / "bbb_synthesize_disagreement_eval_probe_task.md").write_text("b")
        (state_dir / "shared" / "ccc_synthesize_disagreement_eval_probe_task.md").write_text("c")
        (state_dir / "cron_logs" / "2026-04-14_00-30_heartbeat.md").write_text(
            "- { promise: \"Run R_V experiment\", status: \"not started\" }\n"
        )
        with open(state_dir / "stigmergy" / "marks.jsonl", "w") as fh:
            fh.write(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "builder",
                "file_path": "gauntlet.py",
            }) + "\n")

        exe = ShaktiZeitgeistExecutive(state_dir=state_dir)
        result = await exe.cycle()

        assert "underexpressed_roles" in result.role_ecology
        assert "unresolved_promises" in result.memory_pressure
        assert "top_priority_domain" in result.operator_summary
        assert any(alert.startswith("promise:") for alert in result.starvation_alerts)

        summary_path = state_dir / "meta" / "executive_operator_summary.json"
        payload = json.loads(summary_path.read_text())
        assert "loop_attention" in payload
        assert "promise_attention" in payload

    @pytest.mark.asyncio
    async def test_artifacts_are_valid_json(self, tmp_path: Path):
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        (state_dir / "meta").mkdir()
        exe = ShaktiZeitgeistExecutive(state_dir=state_dir)
        await exe.cycle()

        meta = state_dir / "meta"
        for name in ["shakti_executive_state.json", "opportunity_board.json",
                      "allocation_weights.json", "active_campaigns.json"]:
            path = meta / name
            data = json.loads(path.read_text())
            assert data is not None

    @pytest.mark.asyncio
    async def test_brief_contains_required_sections(self, tmp_path: Path):
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        (state_dir / "meta").mkdir()
        exe = ShaktiZeitgeistExecutive(state_dir=state_dir)
        await exe.cycle()

        briefs = list((state_dir / "meta" / "executive_briefs").glob("*.md"))
        assert briefs
        text = briefs[0].read_text()
        assert "Executive Brief" in text
        assert "Cycle" in text
        assert "Top Opportunities" in text
        assert "Domain Balance" in text

    @pytest.mark.asyncio
    async def test_cycle_is_idempotent(self, tmp_path: Path):
        state_dir = tmp_path / ".dharma"
        state_dir.mkdir()
        (state_dir / "meta").mkdir()
        exe = ShaktiZeitgeistExecutive(state_dir=state_dir)

        r1 = await exe.cycle()
        r2 = await exe.cycle()

        assert r1.cycle_id != r2.cycle_id

        # State JSON should be overwritten (single object, not array).
        state_data = json.loads(
            (state_dir / "meta" / "shakti_executive_state.json").read_text()
        )
        assert state_data["cycle_id"] == r2.cycle_id

        # History should have 2 lines.
        history_lines = (
            (state_dir / "meta" / "executive_history.jsonl")
            .read_text().strip().split("\n")
        )
        assert len(history_lines) == 2
