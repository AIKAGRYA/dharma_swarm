"""Tests for opportunity_dispatcher (PR1 — scope stage only).

Covers:
- kill-switch blocks (flag exists, flag is dir)
- lockfile prevents concurrent invocation
- manifest created via plain JSON helper on first promotion
- subsequent runs idempotent
- dry-run writes nothing
- telos BLOCK → manifest.gate_blocked, skip
- telos REVIEW → promote + WARN log + manifest.review_logged=True
- budget exceeded → skip + manifest.budget_blocked
- task_board.create called with full frontier_row in metadata
- health.json written every run with required fields
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from dharma_swarm import _campaign_manifest, opportunity_dispatcher
from dharma_swarm.models import GateCheckResult, GateDecision


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def tmp_dharma(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect every ~/.dharma path inside both modules to ``tmp_path/dharma``.

    Returns the dharma_home path so tests can place fixtures inside it.
    """
    dharma_home = tmp_path / "dharma"
    meta_dir = dharma_home / "meta"
    meta_dir.mkdir(parents=True)
    witness_dir = dharma_home / "witness"
    witness_dir.mkdir(parents=True)
    campaigns = dharma_home / "campaigns"

    monkeypatch.setattr(opportunity_dispatcher, "DHARMA_HOME", dharma_home)
    monkeypatch.setattr(opportunity_dispatcher, "META_DIR", meta_dir)
    monkeypatch.setattr(opportunity_dispatcher, "PENDING_PATH", meta_dir / "frontier_tasks_pending.jsonl")
    monkeypatch.setattr(opportunity_dispatcher, "PAUSED_FLAG", meta_dir / "dispatcher_paused.flag")
    monkeypatch.setattr(opportunity_dispatcher, "LOCK_PATH", meta_dir / "dispatcher.lock")
    monkeypatch.setattr(opportunity_dispatcher, "HEALTH_PATH", meta_dir / "opportunity_dispatcher.health.json")
    monkeypatch.setattr(opportunity_dispatcher, "WITNESS_DIR", witness_dir)
    monkeypatch.setattr(_campaign_manifest, "CAMPAIGN_ROOT", campaigns)
    return dharma_home


@pytest.fixture
def sample_row() -> dict[str, Any]:
    """One scope-stage row matching the canonical pending JSONL schema."""
    return {
        "frontier_id": "ftask_scope_001",
        "title": "Scope: define the wedge for Demo Campaign",
        "description": "Produce a one-page wedge definition for Demo Campaign...",
        "source": "opportunity:scope",
        "verifier_type": "research_grade",
        "difficulty": "medium",
        "provenance": {
            "opportunity_id": "opp_demo_001",
            "domain": "external_revenue",
            "thesis": "wedge",
            "why_now": "demo why now",
            "final_score": 89.9,
            "telos_alignment": 0.95,
            "stage": "scope",
        },
        "metadata": {"seed_kind": "opportunity_bootstrap", "stage": "scope"},
    }


def _write_pending(tmp_dharma: Path, rows: list[dict[str, Any]]) -> None:
    pending = tmp_dharma / "meta" / "frontier_tasks_pending.jsonl"
    pending.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


@dataclass
class FakeTask:
    id: str = "task_fake_001"


class _FakeTaskBoard:
    """Captures all create() calls for assertion in tests."""
    last_call: dict[str, Any] | None = None
    next_task_id: str = "task_fake_001"

    def __init__(self, db_path=None):
        # Real TaskBoard takes db_path; fake ignores it.
        self._db_path = db_path

    async def init_db(self) -> None:
        # Real TaskBoard creates schema; fake is in-memory.
        return None

    async def create(self, **kwargs):
        type(self).last_call = kwargs
        return FakeTask(id=type(self).next_task_id)


@pytest.fixture
def fake_task_board(monkeypatch: pytest.MonkeyPatch):
    """Patch dharma_swarm.task_board.TaskBoard with a fake that records calls."""
    _FakeTaskBoard.last_call = None
    _FakeTaskBoard.next_task_id = "task_fake_001"
    import dharma_swarm.task_board as tb_mod
    monkeypatch.setattr(tb_mod, "TaskBoard", _FakeTaskBoard)
    return _FakeTaskBoard


@pytest.fixture
def stub_gate_allow(monkeypatch: pytest.MonkeyPatch):
    """Force the telos gate to return ALLOW."""
    def _allow(action: str, content: str = "") -> GateCheckResult:
        return GateCheckResult(decision=GateDecision.ALLOW, reason="test ALLOW")
    monkeypatch.setattr(
        "dharma_swarm.telos_gates.check_action", _allow,
    )


@pytest.fixture
def stub_gate_block(monkeypatch: pytest.MonkeyPatch):
    def _block(action: str, content: str = "") -> GateCheckResult:
        return GateCheckResult(decision=GateDecision.BLOCK, reason="test BLOCK")
    monkeypatch.setattr(
        "dharma_swarm.telos_gates.check_action", _block,
    )


@pytest.fixture
def stub_gate_review(monkeypatch: pytest.MonkeyPatch):
    def _review(action: str, content: str = "") -> GateCheckResult:
        return GateCheckResult(decision=GateDecision.REVIEW, reason="test REVIEW")
    monkeypatch.setattr(
        "dharma_swarm.telos_gates.check_action", _review,
    )


@pytest.fixture
def stub_budget_ok(monkeypatch: pytest.MonkeyPatch):
    """Budget gate passes (not exceeded)."""
    monkeypatch.setattr(
        opportunity_dispatcher, "_budget_exceeded", lambda: False,
    )


@pytest.fixture
def stub_budget_exceeded(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        opportunity_dispatcher, "_budget_exceeded", lambda: True,
    )


@pytest.fixture
def stub_stigmergy_noop(monkeypatch: pytest.MonkeyPatch):
    """Skip stigmergic mark to keep tests synchronous and isolated."""
    async def _noop(*a, **kw):
        return None
    monkeypatch.setattr(
        opportunity_dispatcher, "_mark_stigmergy", _noop,
    )


# --------------------------------------------------------------------------
# kill-switch
# --------------------------------------------------------------------------


def test_pause_flag_blocks_run(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [sample_row])
    flag = tmp_dharma / "meta" / "dispatcher_paused.flag"
    flag.touch()

    result = asyncio.run(opportunity_dispatcher.run_once(dry_run=False))

    assert result.paused is True
    assert result.promoted == []
    assert fake_task_board.last_call is None  # nothing promoted


def test_pause_flag_as_directory_treated_as_paused(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [sample_row])
    flag = tmp_dharma / "meta" / "dispatcher_paused.flag"
    flag.mkdir()

    result = asyncio.run(opportunity_dispatcher.run_once(dry_run=False))

    assert result.paused is True
    assert fake_task_board.last_call is None


# --------------------------------------------------------------------------
# Locking
# --------------------------------------------------------------------------


def test_lockfile_prevents_concurrent_invocation(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [sample_row])
    # Manually grab the lock to simulate another process holding it.
    lock_path = tmp_dharma / "meta" / "dispatcher.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    import fcntl
    holder = open(lock_path, "w")
    fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        rc = opportunity_dispatcher.main([])
    finally:
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
        holder.close()

    assert rc == 0  # gracefully skipped, not crashed
    # No promotion happened.
    assert fake_task_board.last_call is None


# --------------------------------------------------------------------------
# Manifest creation + idempotency
# --------------------------------------------------------------------------


def test_first_promotion_creates_manifest_and_task(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [sample_row])

    result = asyncio.run(opportunity_dispatcher.run_once(dry_run=False))

    assert result.paused is False
    assert len(result.promoted) == 1
    promoted = result.promoted[0]
    assert promoted["opportunity_id"] == "opp_demo_001"
    assert promoted["stage"] == "scope"

    manifest_p = tmp_dharma / "campaigns" / "opp_demo_001" / "manifest.json"
    assert manifest_p.exists()
    manifest = json.loads(manifest_p.read_text())
    assert manifest["schema_version"] == 1
    assert manifest["opportunity_id"] == "opp_demo_001"
    assert manifest["telos_alignment"] == 0.95
    assert manifest["stages"]["scope"]["status"] == "promoted"
    assert manifest["stages"]["scope"]["task_id"] == "task_fake_001"
    assert manifest["gate_blocked"] is False
    assert manifest["budget_blocked"] is False

    # task_board.create got the full frontier_row in metadata
    call = fake_task_board.last_call
    assert call is not None
    assert call["created_by"] == "opportunity_dispatcher"
    md = call["metadata"]
    assert md["source"] == "frontier_task"
    assert md["task_type"] == "stage_doc"
    assert md["stage"] == "scope"
    assert md["opportunity_id"] == "opp_demo_001"
    assert md["frontier_id"] == "ftask_scope_001"
    assert md["frontier_row"] == sample_row
    assert md["artifact_target"].endswith("/opp_demo_001/scope.md")


def test_second_run_is_idempotent(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [sample_row])

    asyncio.run(opportunity_dispatcher.run_once(dry_run=False))
    fake_task_board.last_call = None  # clear so we can detect a second create
    fake_task_board.next_task_id = "task_should_not_be_used"

    result = asyncio.run(opportunity_dispatcher.run_once(dry_run=False))

    assert len(result.promoted) == 0
    assert any(s["reason"].startswith("already_") for s in result.skipped)
    assert fake_task_board.last_call is None  # no second create


# --------------------------------------------------------------------------
# Dry-run
# --------------------------------------------------------------------------


def test_dry_run_writes_nothing(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [sample_row])

    result = asyncio.run(opportunity_dispatcher.run_once(dry_run=True))

    assert len(result.promoted) == 1
    assert result.promoted[0]["task_id"] == "<dry-run>"
    # No manifest written
    manifest_p = tmp_dharma / "campaigns" / "opp_demo_001" / "manifest.json"
    assert not manifest_p.exists()
    # No task_board.create call
    assert fake_task_board.last_call is None


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------


def test_telos_block_records_gate_blocked_and_skips(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_block, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [sample_row])

    result = asyncio.run(opportunity_dispatcher.run_once(dry_run=False))

    assert len(result.promoted) == 0
    assert any(s["reason"] == "gate_block" for s in result.skipped)
    manifest = json.loads((tmp_dharma / "campaigns" / "opp_demo_001" / "manifest.json").read_text())
    assert manifest["gate_blocked"] is True
    assert manifest["stages"]["scope"]["status"] == "blocked"
    assert fake_task_board.last_call is None


def test_telos_review_promotes_with_warn_log(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_review, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [sample_row])

    result = asyncio.run(opportunity_dispatcher.run_once(dry_run=False))

    assert len(result.promoted) == 1
    manifest = json.loads((tmp_dharma / "campaigns" / "opp_demo_001" / "manifest.json").read_text())
    assert manifest["review_logged"] is True
    assert manifest["stages"]["scope"]["status"] == "promoted"
    # WARN log written somewhere under witness/
    review_logs = list((tmp_dharma / "witness").rglob("dispatcher_review_warn.jsonl"))
    assert len(review_logs) == 1
    entry = json.loads(review_logs[0].read_text().splitlines()[0])
    assert entry["opportunity_id"] == "opp_demo_001"
    assert entry["stage"] == "scope"
    assert entry["policy"] == "v3_review_to_allow"


def test_budget_exceeded_skips_and_marks_manifest(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_allow, stub_budget_exceeded, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [sample_row])

    result = asyncio.run(opportunity_dispatcher.run_once(dry_run=False))

    assert len(result.promoted) == 0
    assert any(s["reason"] == "budget_exceeded" for s in result.skipped)
    manifest = json.loads((tmp_dharma / "campaigns" / "opp_demo_001" / "manifest.json").read_text())
    assert manifest["budget_blocked"] is True
    assert manifest["stages"]["scope"]["status"] == "pending"
    assert fake_task_board.last_call is None


# --------------------------------------------------------------------------
# Health.json
# --------------------------------------------------------------------------


def test_health_written_with_required_fields_after_main(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [sample_row])

    rc = opportunity_dispatcher.main([])
    assert rc == 0

    health = json.loads(
        (tmp_dharma / "meta" / "opportunity_dispatcher.health.json").read_text()
    )
    for key in (
        "last_run_at", "last_success_at", "consecutive_failures",
        "run_count", "success_count", "last_run_dispatched",
        "last_run_dry_run", "last_run_paused", "last_run_pending_count",
        "last_run_errors", "schema_version",
    ):
        assert key in health, f"missing health field: {key}"
    assert health["schema_version"] == 1
    assert health["last_run_dispatched"] == 1
    assert health["consecutive_failures"] == 0
    assert health["last_run_paused"] is False


def test_health_written_when_paused(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    _write_pending(tmp_dharma, [sample_row])
    (tmp_dharma / "meta" / "dispatcher_paused.flag").touch()

    rc = opportunity_dispatcher.main([])
    assert rc == 0

    health = json.loads(
        (tmp_dharma / "meta" / "opportunity_dispatcher.health.json").read_text()
    )
    assert health["last_run_paused"] is True
    assert health["last_run_dispatched"] == 0


# --------------------------------------------------------------------------
# JSONL hygiene
# --------------------------------------------------------------------------


def test_malformed_jsonl_lines_are_skipped_not_crashed(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    pending = tmp_dharma / "meta" / "frontier_tasks_pending.jsonl"
    pending.write_text(
        "not-json\n" + json.dumps(sample_row) + "\n\n{also-bad}\n",
        encoding="utf-8",
    )
    result = asyncio.run(opportunity_dispatcher.run_once(dry_run=False))

    assert len(result.promoted) == 1
    assert result.pending_count == 1  # only the parsable row counts


def test_row_without_opportunity_id_is_dropped(
    tmp_dharma: Path, sample_row, fake_task_board,
    stub_gate_allow, stub_budget_ok, stub_stigmergy_noop,
):
    bad = dict(sample_row)
    bad["provenance"] = dict(sample_row["provenance"])
    bad["provenance"].pop("opportunity_id")
    _write_pending(tmp_dharma, [bad])

    result = asyncio.run(opportunity_dispatcher.run_once(dry_run=False))

    assert len(result.promoted) == 0
    assert fake_task_board.last_call is None
