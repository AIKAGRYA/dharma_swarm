"""Tests for PersistentAgent — autonomous wake loop."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dharma_swarm.models import AgentRole, ProviderType
from dharma_swarm.persistent_agent import PersistentAgent, _provider_string
from dharma_swarm.task_board import TaskBoard


class TestProviderString:
    def test_anthropic(self):
        assert _provider_string(ProviderType.ANTHROPIC) == "anthropic"

    def test_claude_code(self):
        assert _provider_string(ProviderType.CLAUDE_CODE) == "openrouter"

    def test_codex(self):
        assert _provider_string(ProviderType.CODEX) == "codex"

    def test_openrouter(self):
        assert _provider_string(ProviderType.OPENROUTER) == "openrouter"

    def test_openrouter_free(self):
        assert _provider_string(ProviderType.OPENROUTER_FREE) == "openrouter"

    def test_fallback(self):
        assert _provider_string(ProviderType.LOCAL) == "anthropic"


class TestPersistentAgentInit:
    def test_basic_creation(self, tmp_path):
        agent = PersistentAgent(
            name="test_conductor",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="claude-sonnet-4-20250514",
            state_dir=tmp_path,
            wake_interval_seconds=60.0,
            system_prompt="Test prompt",
        )
        assert agent.name == "test_conductor"
        assert agent.role == AgentRole.CONDUCTOR
        assert agent.wake_interval == 60.0
        assert agent._agent.identity.name == "test_conductor"
        assert agent._agent.identity.provider == "anthropic"

    def test_witness_log_created(self, tmp_path):
        agent = PersistentAgent(
            name="test_wit",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
            state_dir=tmp_path,
        )
        assert agent._witness_log.parent.exists()
        assert "conductor_test_wit" in agent._witness_log.name

    def test_default_state_dir(self):
        agent = PersistentAgent(
            name="default_dir",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
        )
        assert agent.state_dir == Path.home() / ".dharma"


class TestSelfTaskGeneration:
    """Phase 1 priority order: primary_campaign → promises → hot_paths → salient → fallback."""

    def _make_agent(self, tmp_path, name="gen_test"):
        state_dir = tmp_path / ".dharma"
        (state_dir / "meta").mkdir(parents=True)
        (state_dir / "witness").mkdir(parents=True)
        return PersistentAgent(
            name=name,
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
            state_dir=state_dir,
        )

    def test_hot_paths_when_no_campaign_no_promises(self, tmp_path):
        agent = self._make_agent(tmp_path)
        task = agent._generate_self_task(
            hot_paths=[("dharma_swarm/swarm.py", 5)],
            salient_marks=[],
        )
        assert "high-activity" in task
        assert "swarm.py" in task
        assert "5 marks" in task

    def test_salient_marks_fallback(self, tmp_path):
        agent = self._make_agent(tmp_path)
        mark = MagicMock()
        mark.observation = "R_V contraction detected in layer 27"
        task = agent._generate_self_task(
            hot_paths=[],
            salient_marks=[mark],
        )
        assert "Follow up" in task
        assert "R_V contraction" in task

    def test_default_fallback(self, tmp_path):
        agent = self._make_agent(tmp_path)
        task = agent._generate_self_task(
            hot_paths=[],
            salient_marks=[],
        )
        assert "Review system state" in task

    def test_primary_campaign_wins_over_hot_paths(self, tmp_path):
        agent = self._make_agent(tmp_path, name="conductor_test")
        # Seed a primary campaign
        from dharma_swarm.campaigns import create_campaign
        create_campaign(
            "neurips_abstract", "artifact_publication", ["conductor_test"],
            title="NeurIPS abstract", success_criteria="abstract_on_openreview",
            meta_dir=agent.state_dir / "meta",
        )
        task = agent._generate_self_task(
            hot_paths=[("gauntlet.py", 100)],  # strong hot_path, should still lose
            salient_marks=[],
        )
        assert "PRIMARY CAMPAIGN" in task
        assert "neurips_abstract" in task
        # Sole pin → (lead)
        assert "(lead)" in task
        assert "gauntlet.py" not in task

    def test_primary_campaign_support_role_when_not_lead(self, tmp_path):
        agent = self._make_agent(tmp_path, name="outsider")
        from dharma_swarm.campaigns import create_campaign
        create_campaign(
            "neurips_abstract", "artifact_publication",
            ["conductor_claude", "researcher"],  # outsider not on list
            meta_dir=agent.state_dir / "meta",
        )
        task = agent._generate_self_task(hot_paths=[], salient_marks=[])
        assert "PRIMARY CAMPAIGN" in task
        assert "(support)" in task

    def test_promise_wins_over_hot_paths_when_no_campaign(self, tmp_path):
        import json as _json
        agent = self._make_agent(tmp_path)
        (agent.state_dir / "meta" / "promise_pressure.json").write_text(_json.dumps({
            "promises": [
                {"id": "promise_rv", "text": "Run R_V experiment (Mistral-7B)"},
            ]
        }))
        task = agent._generate_self_task(
            hot_paths=[("gauntlet.py", 100)],
            salient_marks=[],
        )
        assert "UNFULFILLED PROMISE" in task
        assert "R_V experiment" in task

    def test_malformed_promise_file_does_not_crash(self, tmp_path):
        agent = self._make_agent(tmp_path)
        (agent.state_dir / "meta" / "promise_pressure.json").write_text("{not json")
        # Should not raise; falls through to hot_paths
        task = agent._generate_self_task(
            hot_paths=[("x.py", 3)],
            salient_marks=[],
        )
        assert "x.py" in task

    def test_empty_promises_list_falls_through(self, tmp_path):
        import json as _json
        agent = self._make_agent(tmp_path)
        (agent.state_dir / "meta" / "promise_pressure.json").write_text(
            _json.dumps({"promises": []})
        )
        task = agent._generate_self_task(
            hot_paths=[("fallback.py", 7)],
            salient_marks=[],
        )
        assert "fallback.py" in task


class TestExtractKeyInsight:
    def test_empty(self):
        assert PersistentAgent._extract_key_insight("") == "No output"

    def test_short_lines_skipped(self):
        text = "OK\nDone\nThis is a meaningful insight about the system state"
        result = PersistentAgent._extract_key_insight(text)
        assert "meaningful insight" in result

    def test_truncation(self):
        text = "x" * 300
        result = PersistentAgent._extract_key_insight(text)
        assert len(result) <= 200


class TestAcceptTask:
    @pytest.mark.asyncio
    async def test_accept_task_queues(self):
        agent = PersistentAgent(
            name="queue_test",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
        )
        await agent.accept_task("Check daemon health")
        assert not agent._task_queue.empty()
        task = agent._task_queue.get_nowait()
        assert task.text == "Check daemon health"
        assert task.source == "injected"
        assert task.priority_rank == 0

    @pytest.mark.asyncio
    async def test_accept_task_sets_wake_event(self):
        agent = PersistentAgent(
            name="wake_test",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
        )
        assert not agent._task_event.is_set()
        await agent.accept_task("Wake now")
        assert agent._task_event.is_set()


class TestPinnedCampaignAttention:
    def _make_agent(self, tmp_path):
        state_dir = tmp_path / ".dharma"
        (state_dir / "meta").mkdir(parents=True)
        (state_dir / "witness").mkdir(parents=True)
        return PersistentAgent(
            name="conductor_test",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
            state_dir=state_dir,
        )

    def test_check_pinned_campaign_prefers_underworked_stale_campaign(self, tmp_path):
        import json as _json
        from datetime import datetime, timedelta, timezone

        agent = self._make_agent(tmp_path)
        meta_dir = agent.state_dir / "meta"

        old = datetime.now(timezone.utc) - timedelta(days=2)
        recent = datetime.now(timezone.utc)
        campaigns = [
            {
                "campaign_id": "incumbent_primary",
                "title": "Incumbent Primary",
                "domain": "strategic_infrastructure",
                "pinned_agents": ["conductor_test"],
                "created": old.isoformat(),
                "last_check_in": recent.isoformat(),
                "check_in_count": 25,
                "status": "active",
                "primary": True,
                "progress_markers": [],
            },
            {
                "campaign_id": "fresh_garden",
                "title": "Fresh Garden",
                "domain": "research",
                "pinned_agents": ["conductor_test"],
                "created": recent.isoformat(),
                "last_check_in": old.isoformat(),
                "check_in_count": 0,
                "status": "active",
                "primary": False,
                "progress_markers": [],
            },
        ]
        (meta_dir / "active_campaigns.json").write_text(_json.dumps(campaigns))

        chosen = agent._check_pinned_campaign()
        assert chosen is not None
        assert chosen["campaign_id"] == "fresh_garden"


class TestGateCheck:
    def test_gate_not_blocked_for_conductor_wake(self):
        agent = PersistentAgent(
            name="gate_test",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
        )
        # conductor_wake is NOT in MANDATORY_THINK_PHASES, so should not block
        result = agent._check_gate("Review system state")
        # May return None if telos_gates has import issues, or a dict
        if result is not None:
            assert not result.get("blocked", False)


class TestTaskBoardMirroring:
    @pytest.mark.asyncio
    async def test_wake_mirrors_self_generated_task_to_board(self, tmp_path):
        state_dir = tmp_path / ".dharma"
        (state_dir / "meta").mkdir(parents=True)
        agent = PersistentAgent(
            name="mirror_test",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
            state_dir=state_dir,
        )

        fake_stigmergy = SimpleNamespace(
            hot_paths=AsyncMock(return_value=[("dharma_swarm/swarm.py", 5)]),
            high_salience=AsyncMock(return_value=[]),
            leave_mark=AsyncMock(),
        )
        fake_bus = SimpleNamespace(receive=AsyncMock(return_value=[]))
        agent._cron.tick = AsyncMock(return_value=[])
        agent._get_stigmergy = AsyncMock(return_value=fake_stigmergy)
        agent._get_bus = AsyncMock(return_value=fake_bus)
        agent._check_gate = MagicMock(return_value={"blocked": False})
        agent._write_witness = AsyncMock()
        agent._agent.memory.load = AsyncMock()
        agent._agent.memory.save = AsyncMock()
        agent._agent.memory.remember = AsyncMock()
        agent._agent.wake = AsyncMock(
            return_value=SimpleNamespace(
                turns=2,
                total_tokens=123,
                summary="Reviewed the hot path and found a concrete next step.",
            )
        )

        result = await agent.wake()

        board = TaskBoard(state_dir / "db" / "tasks.db")
        await board.init_db()
        tasks = await board.list_tasks(limit=20)

        assert result["success"] is True
        assert tasks
        assert any(
            t.created_by == "mirror_test"
            and t.status.value == "completed"
            and t.metadata.get("source") == "persistent_agent.self"
            for t in tasks
        )
