from __future__ import annotations

import copy
from pathlib import Path

import pytest

from dharma_swarm.mission_control_attempts import CampaignAttemptReconciler
from dharma_swarm.mission_control_binding import bind_campaign_authority
from dharma_swarm.mission_control_execution import OrchestratorMissionAdapter
from dharma_swarm.mission_control_execution_support import owner_execution_identity
from dharma_swarm.models import TaskStatus
from dharma_swarm.runtime_state import RuntimeStateStore
from tests.test_mission_control_binding import _BindingCase, _case


async def _indeterminate(case: _BindingCase, goal_id: str) -> object:
    task = await case.board.get(case.tasks[goal_id].id)
    assert task is not None
    authority = task.metadata["mission_campaign_authority"]
    generation = authority["attempt_generation"]
    expected = owner_execution_identity(
        case.control.mission_id if hasattr(case.control, "mission_id") else "sadhana-10-test",
        task.id,
        authority["dispatch_key"],
        generation,
    )
    runtime = RuntimeStateStore(case.board._db_path.parent / "runtime.db", include_memory_plane=False)
    adapter = OrchestratorMissionAdapter(None, case.control, case.board, runtime)  # type: ignore[arg-type]
    metadata = adapter._stamp_metadata(
        task,
        mission_id=authority["mission_id"],
        dispatch_key=authority["dispatch_key"],
        attempt_generation=generation,
        expected=expected,
    )
    assigned = await case.board.assign(task.id, authority["claimed_principal"], metadata=metadata)
    assert await case.board.resolve_campaign_pre_effect_failure(
        task.id,
        expected_status=TaskStatus.ASSIGNED,
        expected_agent_id=authority["claimed_principal"],
        expected_metadata=assigned.metadata,
        authenticated_principal=authority["claimed_principal"],
    ) == "indeterminate"
    terminal = await case.board.get(task.id)
    assert terminal is not None
    return terminal


def _reconciler(case: _BindingCase) -> CampaignAttemptReconciler:
    runtime = RuntimeStateStore(case.board._db_path.parent / "runtime.db", include_memory_plane=False)
    return CampaignAttemptReconciler(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        runtime_state=runtime,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        lease_root=case.lease_root,
    )


@pytest.mark.asyncio
async def test_attempt_reconciler_advances_absent_pre_effect_runtime_once(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    terminal = await _indeterminate(case, "goal-01")

    first = await _reconciler(case).reconcile(now=case.now)
    second = await _reconciler(case).reconcile(now=case.now)

    assert first.advanced_task_ids == (terminal.id,)
    assert first.blocked == ()
    assert first.lease_writes == 1
    assert second.advanced_task_ids == ()
    assert second.lease_writes == 0
    current = await case.board.get(terminal.id)
    assert current is not None and current.status is TaskStatus.PENDING
    assert current.metadata["attempt_generation"] == 1
    assert len(current.metadata["campaign_dispatch_attempt_history"]) == 1


@pytest.mark.asyncio
async def test_attempt_reconciler_validates_every_task_before_first_write(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=2)
    await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    first = await _indeterminate(case, "goal-01")
    second = await _indeterminate(case, "goal-02")
    corrupted = copy.deepcopy(second.metadata)
    corrupted["campaign_dispatch_recovery"]["prior_status"] = "running"
    await case.board.update_task(second.id, metadata=corrupted)

    result = await _reconciler(case).reconcile(now=case.now)

    assert result.advanced_task_ids == ()
    assert result.lease_writes == 0
    assert result.blocked and second.id in result.blocked[0]
    unchanged = await case.board.get(first.id)
    assert unchanged is not None and unchanged.status is TaskStatus.CANCELLED
    assert unchanged.metadata["attempt_generation"] == 0
