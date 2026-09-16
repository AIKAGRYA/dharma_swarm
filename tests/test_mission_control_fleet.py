from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import sys

import pytest

from dharma_swarm.mission_control_fleet import (
    FleetDraftRunner, SCHEMA, command, validate_config, validate_draft,
)
from dharma_swarm.models import TaskStatus


def config():
    return {
        "workers": {name: {"argv": [name], "side_effects": "none"}
                    for name in ("worker-a", "worker-b")},
        "goals": [{"id": "continuity", "title": "Continuity",
                   "objective": "Find the next evidence-supported reliability repair.",
                   "workers": ["worker-a", "worker-b"], "interval_seconds": 3600,
                   "retry_seconds": 60, "timeout_seconds": 10, "max_attempts": 2,
                   "sources": [{"id": "observed", "argv": ["source"]}]}],
    }


def response(request):
    return json.dumps({
        "schema": SCHEMA, "task_id": request["task_id"], "attempt_id": request["attempt_id"],
        "findings": [{"source_id": "observed", "quote": "Queue age is 90 seconds.",
                      "assessment": "This observation warrants checking the stalled worker."}],
        "next_step": "Inspect the worker lease before allowing a replacement attempt.",
        "uncertainty": "Queue age alone does not prove worker failure.",
        "change_since_previous": "This is the first observation supplied for this goal.",
    })


class Executor:
    def __init__(self, fail=0):
        self.fail = fail
        self.workers = []

    async def __call__(self, argv, stdin, timeout):
        if argv == ["source"]:
            return "Queue age is 90 seconds. Check the worker lease."
        self.workers.append(argv[0])
        if self.fail:
            self.fail -= 1
            raise RuntimeError("sensitive credentials must never enter status")
        return "provider banner\n" + response(json.loads(stdin)) + "\nsession info"


@pytest.mark.asyncio
async def test_restart_deduplicates_and_retains_artifact_and_owner_receipt(tmp_path):
    executor = Executor()
    runner = FleetDraftRunner(tmp_path, config(), executor)
    await runner.initialize()
    first = await runner.tick()
    assert first["outcomes"]["continuity"] == "accepted:draft_requires_review"
    restarted = FleetDraftRunner(tmp_path, config(), executor)
    await restarted.initialize()
    assert (await restarted.tick())["outcomes"]["continuity"] == "waiting:interval"
    assert executor.workers == ["worker-a"]
    snapshot = await restarted.control.get_snapshot("continuity")
    assert len(snapshot.tasks) == len(snapshot.attempts) == 1
    assert snapshot.tasks[0].status == TaskStatus.COMPLETED
    terminal = next(r for r in snapshot.receipts if r.receipt_type == "mission_attempt_terminal")
    assert terminal.payload["metadata"]["review_required"] is True
    artifact = next((tmp_path / "artifacts").glob("*.json"))
    assert json.loads(artifact.read_text())["acceptance"] == "identity_and_literal_citations_only"


@pytest.mark.asyncio
async def test_failure_rotates_worker_after_backoff_without_new_task(tmp_path):
    executor = Executor(fail=1)
    runner = FleetDraftRunner(tmp_path, config(), executor)
    await runner.initialize()
    assert (await runner.tick())["outcomes"]["continuity"] == "retry_pending:RuntimeError"
    assert "sensitive" not in (tmp_path / "status.json").read_text()
    assert (await runner.tick())["outcomes"]["continuity"] == "waiting:retry_backoff"
    future = datetime.now(timezone.utc) + timedelta(seconds=65)
    assert (await runner.tick(now=future))["outcomes"]["continuity"] == "accepted:draft_requires_review"
    snapshot = await runner.control.get_snapshot("continuity")
    assert len(snapshot.tasks) == 1
    assert len(snapshot.attempts) == 2
    assert executor.workers == ["worker-a", "worker-b"]


@pytest.mark.asyncio
async def test_exhausted_cycle_cools_down_then_opens_one_fresh_task(tmp_path):
    executor = Executor(fail=2)
    runner = FleetDraftRunner(tmp_path, config(), executor)
    await runner.initialize()
    base = datetime.now(timezone.utc)
    await runner.tick(now=base)
    await runner.tick(now=base + timedelta(seconds=65))
    runner = FleetDraftRunner(tmp_path, config(), executor)
    await runner.initialize()
    assert (await runner.tick(now=base + timedelta(seconds=600)))["outcomes"]["continuity"] == "waiting:cycle_cooldown"
    assert len(executor.workers) == 2
    later = base + timedelta(days=3)
    assert (await runner.tick(now=later))["outcomes"]["continuity"] == "accepted:draft_requires_review"
    assert (await runner.tick())["outcomes"]["continuity"] == "waiting:interval"
    tasks = await runner.control.list_tasks("continuity")
    assert sorted(t.status for t in tasks) == sorted([TaskStatus.FAILED, TaskStatus.COMPLETED])
    assert len(executor.workers) == 3


@pytest.mark.asyncio
async def test_operator_cancelled_goal_is_never_resumed(tmp_path):
    executor = Executor(fail=10)
    runner = FleetDraftRunner(tmp_path, config(), executor)
    await runner.initialize()
    task = await runner.control.create_task("continuity", title="Operator-stopped task")
    await runner.board.cancel(task.task_id)
    for days in (0, 3, 30):
        outcome = await runner.tick(now=datetime.now(timezone.utc) + timedelta(days=days))
        assert outcome["outcomes"]["continuity"] == "blocked:cancelled_by_operator"
    assert len(await runner.control.list_tasks("continuity")) == 1
    assert not executor.workers


@pytest.mark.asyncio
async def test_crashed_attempt_is_fenced_after_lease_expiry_and_replaced(tmp_path):
    executor = Executor()
    runner = FleetDraftRunner(tmp_path, config(), executor)
    await runner.initialize()
    task = await runner.control.create_task(
        "continuity", title="Crashed task",
        metadata={"sources": {"observed": "Queue age is 90 seconds."},
                  "previous_result": "", "evidence_at": "then"})
    crashed = await runner.control.start_attempt("continuity", task.task_id, "worker-a",
                                                 attempt_key="crashed", lease_seconds=60)
    await runner.control.heartbeat_lease("continuity", task.task_id, "worker-a",
                                         attempt_id=crashed.attempt_id, lease_seconds=60)
    restarted = FleetDraftRunner(tmp_path, config(), executor)
    await restarted.initialize()
    assert (await restarted.tick())["outcomes"]["continuity"] == "waiting:active_lease"
    claim = (await restarted.runtime.list_task_claims(task_id=task.task_id))[0]
    await restarted.runtime.record_task_claim(
        replace(claim, stale_after=datetime.now(timezone.utc) - timedelta(seconds=1)))
    future = datetime.now(timezone.utc) + timedelta(seconds=120)
    assert (await restarted.tick(now=future))["outcomes"]["continuity"] == "accepted:draft_requires_review"
    assert executor.workers == ["worker-b"]
    stale = await restarted.runtime.get_delegation_run(crashed.attempt_id)
    assert stale.status == "stale_recovered"
    with pytest.raises(Exception):
        await restarted.control.finish_attempt(
            "continuity", task.task_id, "worker-a", attempt_id=crashed.attempt_id,
            status="succeeded", result="late")
    snapshot = await restarted.control.get_snapshot("continuity")
    assert len(snapshot.tasks) == 1 and snapshot.tasks[0].status == TaskStatus.COMPLETED
    terminal = [r for r in snapshot.receipts if r.receipt_type == "mission_attempt_terminal"]
    assert len(terminal) == 1


@pytest.mark.asyncio
async def test_live_lease_prevents_reexecution(tmp_path):
    executor = Executor()
    runner = FleetDraftRunner(tmp_path, config(), executor)
    await runner.initialize()
    task = await runner.control.create_task("continuity", title="Existing task")
    await runner.control.start_attempt("continuity", task.task_id, "worker-a", lease_seconds=60)
    assert (await runner.tick())["outcomes"]["continuity"] == "waiting:active_lease"
    assert not executor.workers


@pytest.mark.asyncio
async def test_source_failure_does_not_create_unfounded_task(tmp_path):
    async def unavailable(*args):
        raise TimeoutError("source unavailable")
    runner = FleetDraftRunner(tmp_path, config(), unavailable)
    await runner.initialize()
    assert (await runner.tick())["outcomes"]["continuity"] == "error:TimeoutError"
    assert not await runner.control.list_tasks("continuity")


def test_invented_citation_and_stale_attempt_are_rejected():
    request = {"task_id": "task", "attempt_id": "attempt"}
    good = response(request)
    with pytest.raises(ValueError, match="quotation absent"):
        validate_draft(good, "task", "attempt", {"observed": "Different evidence"})
    with pytest.raises(ValueError, match="another attempt"):
        validate_draft(good, "task", "new-attempt", {"observed": "Queue age is 90 seconds."})


def test_unsafe_worker_and_unbounded_schedule_rejected():
    cfg = config()
    cfg["workers"]["worker-a"]["side_effects"] = "outreach"
    with pytest.raises(ValueError, match="effect-free"):
        validate_config(cfg)
    cfg = config()
    cfg["goals"][0]["interval_seconds"] = 1
    with pytest.raises(ValueError, match="interval"):
        validate_config(cfg)


@pytest.mark.asyncio
async def test_command_preserves_arbitrary_input_and_bounds_output_and_time():
    payload = "literal $(touch should-not-exist) `command`\n"
    assert await command([sys.executable, "-c", "import sys; print(sys.stdin.read(), end='')"], payload, 5) == payload
    with pytest.raises(ValueError, match="output limit"):
        await command([sys.executable, "-c", "print('x'*70000)"], "", 5)
    with pytest.raises(TimeoutError):
        await command([sys.executable, "-c", "import time; time.sleep(10)"], "", 0.1)
