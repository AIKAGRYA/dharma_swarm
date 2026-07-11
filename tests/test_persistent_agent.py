"""Tests for PersistentAgent — autonomous wake loop."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dharma_swarm.models import AgentRole, ProviderType
from dharma_swarm.persistent_agent import PersistentAgent, _provider_string


class TestProviderString:
    def test_anthropic(self):
        assert _provider_string(ProviderType.ANTHROPIC) == "anthropic"

    def test_claude_code(self):
        assert _provider_string(ProviderType.CLAUDE_CODE) == "anthropic"

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
    def setup_method(self):
        self.agent = PersistentAgent(
            name="gen_test",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
        )

    def test_hot_paths_priority(self):
        task = self.agent._generate_self_task(
            hot_paths=[("dharma_swarm/swarm.py", 5)],
            salient_marks=[],
        )
        assert "high-activity" in task
        assert "swarm.py" in task
        assert "5 marks" in task

    def test_salient_marks_fallback(self):
        mark = MagicMock()
        mark.observation = "R_V contraction detected in layer 27"
        task = self.agent._generate_self_task(
            hot_paths=[],
            salient_marks=[mark],
        )
        assert "Follow up" in task
        assert "R_V contraction" in task

    def test_default_fallback(self):
        task = self.agent._generate_self_task(
            hot_paths=[],
            salient_marks=[],
        )
        assert "Review system state" in task


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
        assert task == "Check daemon health"


class TestMemoryConsolidationReceipts:
    @pytest.mark.asyncio
    async def test_governed_receipt_is_appended_before_success_is_reported(self, tmp_path):
        from dharma_swarm.memory_kernel import (
            DEFAULT_WRITE_RECEIPT_PATH,
            MemoryKernelWritePolicyOutcome,
            load_write_receipts,
        )

        repo_root = tmp_path / "repo"
        memory_kernel = SimpleNamespace(
            config=SimpleNamespace(census=SimpleNamespace(repo_root=repo_root)),
            iter_episodes=MagicMock(return_value=[SimpleNamespace(id="memory_atom:episode-1")]),
        )
        state_dir = tmp_path / "state"
        agent = PersistentAgent(
            name="receipt_test",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
            state_dir=state_dir,
            memory_kernel=memory_kernel,
        )

        result = await agent._cron_consolidate_memory()

        receipt_path = repo_root / DEFAULT_WRITE_RECEIPT_PATH
        receipts, immutable = load_write_receipts(receipt_path)
        assert immutable is True
        assert len(receipts) == 1
        receipt = receipts[0]
        policy = receipt["policy_decision"]
        request = receipt["request"]
        assert isinstance(policy, dict)
        assert isinstance(request, dict)
        assert policy["outcome"] == MemoryKernelWritePolicyOutcome.ALLOW
        assert request["proposed_operation"] == "append_proposal"
        assert request["target_surface"] == "memory_kernel.write_receipts"
        assert f"receipt={receipt_path}" in result

        reorg_path = state_dir / "holon_reorg" / "receipt_test.jsonl"
        reorg_rows = [json.loads(line) for line in reorg_path.read_text().splitlines()]
        assert reorg_rows[-1]["write_receipt_id"] == receipt["receipt_id"]

    @pytest.mark.asyncio
    async def test_receipt_append_failure_does_not_claim_or_write_local_reorg(self, tmp_path):
        repo_root = tmp_path / "repo"
        memory_kernel = SimpleNamespace(
            config=SimpleNamespace(census=SimpleNamespace(repo_root=repo_root)),
            iter_episodes=MagicMock(return_value=[SimpleNamespace(id="memory_atom:episode-1")]),
        )
        state_dir = tmp_path / "state"
        agent = PersistentAgent(
            name="receipt_failure",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
            state_dir=state_dir,
            memory_kernel=memory_kernel,
        )

        with patch(
            "dharma_swarm.memory_kernel.write_receipts.append_write_receipts",
            side_effect=OSError("ledger unavailable"),
        ):
            with pytest.raises(RuntimeError, match="memory reorg failed"):
                await agent._cron_consolidate_memory()

        assert not (state_dir / "holon_reorg" / "receipt_failure.jsonl").exists()


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


class TestWakeMarksMessageRead:
    """Regression: when the wake loop adopts an inbox message as its task,
    it must mark that message read so subsequent wakes do not re-fetch and
    re-respond to the same message forever (act-then-mark, cf.
    contracts/runtime_adapters.py)."""

    @pytest.mark.asyncio
    async def test_adopted_message_not_refetched(self, tmp_path):
        from dharma_swarm.autonomous_agent import AgentResult
        from dharma_swarm.message_bus import MessageBus
        from dharma_swarm.models import Message

        bus = MessageBus(tmp_path / "messages.db")
        await bus.init_db()
        await bus.send(Message(
            from_agent="peer", to_agent="waker",
            subject="need help", body="investigate the drift",
        ))

        agent = PersistentAgent(
            name="waker",
            role=AgentRole.CONDUCTOR,
            provider_type=ProviderType.ANTHROPIC,
            model="test-model",
            state_dir=tmp_path,
        )

        # Inject the real test bus; neutralise the heavy wake collaborators so
        # the message-selection path runs without a provider or shared state.
        agent._bus = bus
        agent._cron._jobs = {}
        stig = MagicMock()
        stig.hot_paths = AsyncMock(return_value=[])
        stig.high_salience = AsyncMock(return_value=[])
        stig.leave_mark = AsyncMock()
        agent._get_stigmergy = AsyncMock(return_value=stig)
        agent._agent.memory = MagicMock()
        agent._agent.memory.load = AsyncMock()
        agent._agent.memory.remember = AsyncMock()
        agent._agent.memory.save = AsyncMock()
        agent._agent.wake = AsyncMock(
            return_value=AgentResult(summary="handled", turns=1)
        )

        info = await agent.wake()
        assert info["success"] is True
        assert info["task_source"] == "message"

        # The adopted message must be marked read, not left unread for replay.
        assert await bus.receive("waker", status="unread") == []
        assert len(await bus.receive("waker", status="read")) == 1

        # A second wake with an empty inbox falls back to a self-task rather
        # than re-responding to the same message.
        info2 = await agent.wake()
        assert info2["task_source"] == "self"
