"""Tests for dharma_swarm.economic_agent — Shakti economic engine.

Validates:
- TaskStatus and TaskSource enums
- EconomicTask model construction and defaults
- LedgerEntry model construction
- EconomicStatus model construction and defaults
- EconomicLedger: record, load, status round-trip
- InboxPoller: poll from JSON files, move to processed
- TelosAcceptanceResult model
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.economic_agent import (
    EconomicLedger,
    EconomicStatus,
    EconomicTask,
    InboxPoller,
    LedgerEntry,
    TaskSource,
    TaskStatus,
    TelosAcceptanceResult,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestEnums:
    def test_task_status_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.ACCEPTED == "accepted"
        assert TaskStatus.REJECTED == "rejected"
        assert TaskStatus.EXECUTING == "executing"
        assert TaskStatus.DELIVERED == "delivered"
        assert TaskStatus.FAILED == "failed"

    def test_task_source_values(self):
        assert TaskSource.LOCAL_INBOX == "local_inbox"
        assert TaskSource.GITHUB_ISSUE == "github_issue"
        assert TaskSource.MARKETPLACE == "marketplace"
        assert TaskSource.MANUAL == "manual"


# ---------------------------------------------------------------------------
# EconomicTask
# ---------------------------------------------------------------------------


class TestEconomicTask:
    def test_defaults(self):
        task = EconomicTask(title="Test", description="A test task")
        assert task.status == TaskStatus.PENDING
        assert task.domain == "code"
        assert task.budget_usd == 0.0
        assert task.source == TaskSource.LOCAL_INBOX
        assert task.deliverables == []
        assert task.rating is None

    def test_full_construction(self):
        task = EconomicTask(
            title="SEO Audit",
            description="Audit client website for SEO issues",
            domain="research",
            budget_usd=150.0,
            source=TaskSource.MARKETPLACE,
            source_ref="https://hyrve.com/job/123",
        )
        assert task.title == "SEO Audit"
        assert task.budget_usd == 150.0
        assert task.source == TaskSource.MARKETPLACE

    def test_auto_id(self):
        t1 = EconomicTask(title="A", description="d")
        t2 = EconomicTask(title="B", description="d")
        assert t1.id != t2.id


# ---------------------------------------------------------------------------
# LedgerEntry
# ---------------------------------------------------------------------------


class TestLedgerEntry:
    def test_defaults(self):
        entry = LedgerEntry(
            task_id="t1", task_title="Task 1", domain="code", source="local_inbox"
        )
        assert entry.cost_tokens == 0
        assert entry.profit_usd == 0.0
        assert entry.rating is None

    def test_with_economics(self):
        entry = LedgerEntry(
            task_id="t1", task_title="Task 1", domain="code", source="manual",
            cost_tokens=5000, cost_usd=0.05, revenue_usd=50.0,
            profit_usd=49.95, rating=4.5,
        )
        assert entry.profit_usd == 49.95
        assert entry.rating == 4.5


# ---------------------------------------------------------------------------
# EconomicStatus
# ---------------------------------------------------------------------------


class TestEconomicStatus:
    def test_defaults(self):
        status = EconomicStatus()
        assert status.total_tasks == 0
        assert status.self_sustaining is False
        assert status.domains == {}


# ---------------------------------------------------------------------------
# EconomicLedger
# ---------------------------------------------------------------------------


class TestEconomicLedger:
    def test_record_and_load(self, tmp_path):
        path = tmp_path / "ledger.jsonl"
        ledger = EconomicLedger(path=path)
        entry = LedgerEntry(
            task_id="t1", task_title="Code Review", domain="code",
            source="manual", revenue_usd=25.0, cost_usd=0.10,
        )
        ledger.record(entry)
        assert path.exists()

        ledger2 = EconomicLedger(path=path)
        entries = ledger2.load()
        assert len(entries) == 1
        assert entries[0].task_title == "Code Review"
        assert entries[0].revenue_usd == 25.0

    def test_multiple_records(self, tmp_path):
        path = tmp_path / "ledger.jsonl"
        ledger = EconomicLedger(path=path)
        for i in range(5):
            ledger.record(LedgerEntry(
                task_id=f"t{i}", task_title=f"Task {i}",
                domain="code", source="manual",
                revenue_usd=10.0 * i, cost_usd=0.01 * i,
            ))
        entries = EconomicLedger(path=path).load()
        assert len(entries) == 5

    def test_status_aggregation(self, tmp_path):
        path = tmp_path / "ledger.jsonl"
        ledger = EconomicLedger(path=path)
        ledger.record(LedgerEntry(
            task_id="t1", task_title="A", domain="code", source="manual",
            revenue_usd=100.0, cost_usd=5.0, rating=4.0,
        ))
        ledger.record(LedgerEntry(
            task_id="t2", task_title="B", domain="research", source="manual",
            revenue_usd=50.0, cost_usd=2.0, rating=5.0,
        ))

        status = ledger.status()
        assert status.total_tasks == 2
        assert status.total_revenue == 150.0
        assert status.total_cost == 7.0
        assert status.total_profit == 143.0
        assert status.avg_rating == 4.5
        assert status.self_sustaining is True
        assert status.domains["code"] == 1
        assert status.domains["research"] == 1

    def test_empty_status(self, tmp_path):
        path = tmp_path / "empty_ledger.jsonl"
        ledger = EconomicLedger(path=path)
        status = ledger.status()
        assert status.total_tasks == 0
        assert status.self_sustaining is False


# ---------------------------------------------------------------------------
# InboxPoller
# ---------------------------------------------------------------------------


class TestInboxPoller:
    @pytest.mark.asyncio
    async def test_polls_json_files(self, tmp_path):
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        task_data = {"title": "Build API", "description": "Create REST API", "budget_usd": 200}
        (inbox / "task1.json").write_text(json.dumps(task_data))

        poller = InboxPoller(inbox_dir=inbox)
        tasks = await poller.poll()
        assert len(tasks) == 1
        assert tasks[0].title == "Build API"
        assert tasks[0].budget_usd == 200.0

        # File should be moved to processed
        assert not (inbox / "task1.json").exists()
        assert (inbox / "processed" / "task1.json").exists()

    @pytest.mark.asyncio
    async def test_empty_inbox(self, tmp_path):
        inbox = tmp_path / "inbox"
        poller = InboxPoller(inbox_dir=inbox)
        tasks = await poller.poll()
        assert tasks == []

    @pytest.mark.asyncio
    async def test_invalid_json_skipped(self, tmp_path):
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        (inbox / "bad.json").write_text("not valid json{{{")
        (inbox / "good.json").write_text(json.dumps({
            "title": "Good Task", "description": "Works fine"
        }))

        poller = InboxPoller(inbox_dir=inbox)
        tasks = await poller.poll()
        assert len(tasks) == 1
        assert tasks[0].title == "Good Task"


# ---------------------------------------------------------------------------
# TelosAcceptanceResult
# ---------------------------------------------------------------------------


class TestTelosAcceptanceResult:
    def test_defaults(self):
        result = TelosAcceptanceResult(accepted=True, reason="Aligned")
        assert result.gate_passed is False
        assert result.gnani_passed is False
        assert result.competence_ok is False
        assert result.economics_ok is False

    def test_full_acceptance(self):
        result = TelosAcceptanceResult(
            accepted=True, reason="All gates passed",
            gate_passed=True, gnani_passed=True,
            competence_ok=True, economics_ok=True,
        )
        assert result.accepted is True
        assert result.gate_passed is True
