from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import dharma_swarm.runtime_state as runtime_state_module
from dharma_swarm.message_bus import MessageBus
from dharma_swarm.models import Message
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    SessionState,
    TaskClaim,
)
from dharma_swarm.spine.adapters import identity_metadata
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_reserved_campaign_session_prefix_requires_typed_mutation(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    reserved = SessionState(
        session_id="mission_campaign:untyped",
        operator_id="operator",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    receipt = RuntimeReceipt(
        receipt_id="untyped-campaign-receipt",
        receipt_type="ordinary",
        status="active",
        correlation_id=reserved.session_id,
        created_at=reserved.updated_at,
    )

    with pytest.raises(ValueError, match="reserved campaign session"):
        await runtime.upsert_session(reserved)
    with pytest.raises(ValueError, match="campaign schema"):
        await runtime.insert_session_if_absent(reserved, atomic_receipt=receipt)
    with pytest.raises(ValueError, match="reserved campaign session"):
        await runtime.compare_and_swap_session(
            reserved,
            replace(reserved, updated_at=NOW + timedelta(microseconds=1)),
        )


@pytest.mark.asyncio
async def test_typed_campaign_session_cannot_squat_another_mission_id(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    session = SessionState(
        session_id="mission_campaign:mission-alpha",
        operator_id="operator",
        status="active",
        metadata={
            "schema_version": "dharma.mission_control.campaign.v1",
            "mission_id": "mission-beta",
            "generation": 1,
            "last_cycle_sequence": 0,
            "last_cycle_receipt_id": "",
            "stop_requested": False,
        },
        created_at=NOW,
        updated_at=NOW,
    )
    receipt = RuntimeReceipt(
        receipt_id=runtime_state_module._stable_bound_id(
            "mission_campaign_control", "mission-beta", "start", "1"
        ),
        receipt_type="mission_campaign_control",
        status="start",
        correlation_id=session.session_id,
        agent_id=session.operator_id,
        payload={
            "schema_version": "dharma.mission_control.campaign.v1",
            "mission_id": "mission-beta",
            "generation": 1,
            "action": "start",
        },
        created_at=NOW,
    )

    with pytest.raises(ValueError, match="bind initial session"):
        await runtime.insert_session_if_absent(session, atomic_receipt=receipt)


def _claim(**overrides: object) -> TaskClaim:
    values: dict[str, object] = {
        "claim_id": "claim-alpha",
        "task_id": "task-alpha",
        "agent_id": "agent-alpha",
        "status": "running",
        "session_id": "session-alpha",
        "claimed_at": NOW - timedelta(minutes=2),
        "acked_at": NOW - timedelta(minutes=1),
        "heartbeat_at": NOW - timedelta(seconds=30),
        "stale_after": NOW + timedelta(minutes=1),
        "retry_count": 2,
        "metadata": {"fence": "generation-two"},
    }
    values.update(overrides)
    return TaskClaim(**values)  # type: ignore[arg-type]


def _identity(run_id: str, *, metadata: dict[str, object] | None = None):
    return ExecutionIdentity.new(
        trace_id=f"trace-{run_id}",
        correlation_id=f"correlation-{run_id}",
        task_id=f"task-{run_id}",
        run_id=run_id,
        claim_id=f"claim-{run_id}",
        idempotency_key=f"idempotency-{run_id}",
        agent_id="a2a-handler",
        session_id="a2a-session",
        external_a2a_task_id="external-a2a-alpha",
        metadata=metadata,
    )


@pytest.mark.asyncio
async def test_terminal_runtime_rows_reject_stale_open_replay(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    running_claim = await runtime.record_task_claim(_claim())
    terminal_claim = await runtime.record_task_claim(
        replace(running_claim, status="completed", heartbeat_at=NOW)
    )
    assert await runtime.record_task_claim(
        replace(
            terminal_claim,
            heartbeat_at=NOW + timedelta(seconds=1),
            metadata={**terminal_claim.metadata, "stale_replay": True},
        )
    ) == terminal_claim
    with pytest.raises(ValueError, match="terminal claim"):
        await runtime.record_task_claim(replace(terminal_claim, status="running"))
    with pytest.raises(ValueError, match="terminal claim"):
        await runtime.record_task_claim(replace(terminal_claim, status="failed"))

    running_run = await runtime.record_delegation_run(
        DelegationRun(
            run_id="run-terminal-fence",
            task_id=running_claim.task_id,
            assigned_to=running_claim.agent_id,
            claim_id=running_claim.claim_id,
            session_id=running_claim.session_id,
            status="running",
            started_at=NOW - timedelta(minutes=1),
            metadata={"projection_snapshot": "prepared"},
        )
    )
    terminal_run = await runtime.record_delegation_run(
        replace(running_run, status="completed", completed_at=NOW)
    )
    assert await runtime.record_delegation_run(
        replace(
            terminal_run,
            completed_at=NOW + timedelta(seconds=1),
            metadata={"stale_replay": True},
        )
    ) == terminal_run
    with pytest.raises(ValueError, match="terminal run"):
        await runtime.record_delegation_run(
            replace(terminal_run, status="running", completed_at=None, metadata={})
        )
    with pytest.raises(ValueError, match="terminal run"):
        await runtime.record_delegation_run(
            replace(terminal_run, status="failed", failure_code="foreign")
        )

    assert await runtime.get_task_claim(terminal_claim.claim_id) == terminal_claim
    assert await runtime.get_delegation_run(terminal_run.run_id) == terminal_run


def test_sync_terminal_runtime_rows_are_first_writer_wins(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("sync-terminal")
    evidence = {"last_sequence": 1, "last_delta_id": "delta-sync-terminal"}
    running_claim = runtime.create_task_claim_sync(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            session_id=identity.session_id,
            status="running",
            claimed_at=NOW - timedelta(minutes=1),
            metadata={
                **identity.to_metadata(),
                "mission_control_evidence": evidence,
            },
        )
    )
    terminal_claim = runtime.create_task_claim_sync(
        replace(running_claim, status="completed", heartbeat_at=NOW)
    )
    assert runtime.create_task_claim_sync(
        replace(terminal_claim, metadata={**terminal_claim.metadata, "foreign": True})
    ) == terminal_claim
    with pytest.raises(ValueError, match="reserved evidence metadata conflict"):
        runtime.create_task_claim_sync(
            replace(
                terminal_claim,
                metadata={
                    **terminal_claim.metadata,
                    "mission_control_evidence": {
                        **evidence,
                        "last_sequence": 0,
                    },
                },
            )
        )
    with pytest.raises(ValueError, match="terminal claim"):
        runtime.create_task_claim_sync(replace(terminal_claim, status="running"))
    with pytest.raises(ValueError, match="terminal claim"):
        runtime.create_task_claim_sync(replace(terminal_claim, status="failed"))

    running_run = runtime.create_delegation_run_sync(
        DelegationRun(
            run_id=identity.run_id,
            task_id=identity.task_id,
            assigned_to=identity.agent_id,
            claim_id=identity.claim_id,
            session_id=identity.session_id,
            status="running",
            started_at=NOW - timedelta(minutes=1),
            metadata=identity.to_metadata(),
        )
    )
    terminal_run = runtime.create_delegation_run_sync(
        replace(running_run, status="completed", completed_at=NOW)
    )
    assert runtime.create_delegation_run_sync(
        replace(
            terminal_run,
            completed_at=NOW + timedelta(seconds=1),
            failure_code="ignored-replay",
        )
    ) == terminal_run
    with pytest.raises(ValueError, match="terminal run"):
        runtime.create_delegation_run_sync(
            replace(terminal_run, status="running", completed_at=None)
        )
    with pytest.raises(ValueError, match="terminal run"):
        runtime.create_delegation_run_sync(
            replace(terminal_run, status="failed", failure_code="foreign")
        )

    assert runtime.get_task_claim_sync(identity.claim_id) == terminal_claim
    assert runtime.get_delegation_run_sync(identity.run_id) == terminal_run


def test_sync_heartbeat_cannot_regress_future_timestamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("sync-heartbeat-monotonic")
    claim = runtime.create_task_claim_sync(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            session_id=identity.session_id,
            status="running",
            heartbeat_at=NOW + timedelta(seconds=1),
            metadata=identity.to_metadata(),
        )
    )
    monkeypatch.setattr(runtime_state_module, "_utc_now", lambda: NOW)

    with pytest.raises(ValueError, match="advance monotonically"):
        runtime.heartbeat_claim_sync(claim.claim_id)
    assert runtime.get_task_claim_sync(claim.claim_id) == claim


@pytest.mark.asyncio
async def test_terminal_public_mutators_require_exact_replay(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("terminal-public-mutators")
    running_claim = runtime.create_task_claim_sync(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            session_id=identity.session_id,
            status="running",
            metadata=identity.to_metadata(),
        )
    )
    terminal_claim = runtime.close_claim_sync(
        running_claim.claim_id,
        status="completed",
    )
    assert terminal_claim is not None
    assert runtime.close_claim_sync(
        running_claim.claim_id,
        status="completed",
    ) == terminal_claim
    with pytest.raises(ValueError, match="must be exact"):
        runtime.close_claim_sync(
            running_claim.claim_id,
            status="completed",
            metadata={"foreign": True},
        )
    with pytest.raises(ValueError, match="must be exact"):
        runtime.close_claim_sync(running_claim.claim_id, status="failed")
    with pytest.raises(ValueError, match="terminal claim"):
        runtime.heartbeat_claim_sync(running_claim.claim_id)
    with pytest.raises(ValueError, match="terminal claim"):
        await runtime.acknowledge_task_claim(running_claim.claim_id)

    running_run = runtime.create_delegation_run_sync(
        DelegationRun(
            run_id=identity.run_id,
            task_id=identity.task_id,
            assigned_to=identity.agent_id,
            claim_id=identity.claim_id,
            session_id=identity.session_id,
            status="running",
            metadata=identity.to_metadata(),
        )
    )
    terminal_run = runtime.close_delegation_run_sync(
        running_run.run_id,
        status="completed",
    )
    assert terminal_run is not None
    assert runtime.close_delegation_run_sync(
        running_run.run_id,
        status="completed",
    ) == terminal_run
    with pytest.raises(ValueError, match="must be exact"):
        runtime.close_delegation_run_sync(
            running_run.run_id,
            status="completed",
            metadata={"foreign": True},
        )
    with pytest.raises(ValueError, match="must be exact"):
        runtime.close_delegation_run_sync(
            running_run.run_id,
            status="failed",
            failure_code="foreign",
        )
    assert await runtime.compare_and_swap_delegation_run_exact(
        terminal_run,
        terminal_run,
    )
    with pytest.raises(ValueError, match="terminal delegation run"):
        await runtime.compare_and_swap_delegation_run_exact(
            terminal_run,
            replace(
                terminal_run,
                status="failed",
                completed_at=NOW,
                failure_code="foreign",
            ),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["claim", "run"])
async def test_async_terminal_legacy_owner_cannot_mint_durable_identity(
    tmp_path: Path,
    surface: str,
) -> None:
    runtime = RuntimeStateStore(
        tmp_path / f"runtime-async-terminal-legacy-{surface}.db",
        include_memory_plane=False,
    )
    identity = _identity(f"async-terminal-legacy-{surface}")
    if surface == "claim":
        existing = await runtime.record_task_claim(
            TaskClaim(
                claim_id=identity.claim_id,
                task_id=identity.task_id,
                agent_id=identity.agent_id,
                session_id=identity.session_id,
                status="completed",
            )
        )
        with pytest.raises(ValueError, match="cannot acquire"):
            await runtime.record_task_claim(
                replace(existing, metadata=identity.to_metadata())
            )
        assert await runtime.get_task_claim(existing.claim_id) == existing
    else:
        existing = await runtime.record_delegation_run(
            DelegationRun(
                run_id=identity.run_id,
                task_id=identity.task_id,
                assigned_to=identity.agent_id,
                claim_id=identity.claim_id,
                session_id=identity.session_id,
                status="completed",
                completed_at=NOW,
            )
        )
        with pytest.raises(ValueError, match="cannot acquire"):
            await runtime.record_delegation_run(
                replace(existing, metadata=identity.to_metadata())
            )
        assert await runtime.get_delegation_run(existing.run_id) == existing
    assert await runtime.get_execution_identity(identity.run_id) is None


@pytest.mark.parametrize("surface", ["claim", "run"])
def test_sync_terminal_legacy_owner_cannot_mint_durable_identity(
    tmp_path: Path,
    surface: str,
) -> None:
    runtime = RuntimeStateStore(
        tmp_path / f"runtime-sync-terminal-legacy-{surface}.db",
        include_memory_plane=False,
    )
    identity = _identity(f"sync-terminal-legacy-{surface}")
    if surface == "claim":
        existing = runtime.create_task_claim_sync(
            TaskClaim(
                claim_id=identity.claim_id,
                task_id=identity.task_id,
                agent_id=identity.agent_id,
                session_id=identity.session_id,
                status="completed",
            ),
            legacy_no_identity_allowed=True,
        )
        with pytest.raises(ValueError, match="cannot acquire"):
            runtime.create_task_claim_sync(
                replace(existing, metadata=identity.to_metadata())
            )
        assert runtime.get_task_claim_sync(existing.claim_id) == existing
    else:
        existing = runtime.create_delegation_run_sync(
            DelegationRun(
                run_id=identity.run_id,
                task_id=identity.task_id,
                assigned_to=identity.agent_id,
                claim_id=identity.claim_id,
                session_id=identity.session_id,
                status="completed",
                completed_at=NOW,
            ),
            legacy_no_identity_allowed=True,
        )
        with pytest.raises(ValueError, match="cannot acquire"):
            runtime.create_delegation_run_sync(
                replace(existing, metadata=identity.to_metadata())
            )
        assert runtime.get_delegation_run_sync(existing.run_id) == existing
    assert runtime.get_execution_identity_sync(identity.run_id) is None


def test_sync_terminal_replay_rejects_foreign_coordinates_before_identity_write(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    canonical = _identity("terminal-coordinate-owner")
    terminal_claim = runtime.create_task_claim_sync(
        TaskClaim(
            claim_id=canonical.claim_id,
            task_id=canonical.task_id,
            agent_id=canonical.agent_id,
            session_id=canonical.session_id,
            status="completed",
            metadata=canonical.to_metadata(),
        )
    )
    foreign_claim_identity = ExecutionIdentity.new(
        trace_id="trace-foreign-claim",
        correlation_id="correlation-foreign-claim",
        task_id="task-foreign-claim",
        run_id="run-foreign-claim",
        claim_id=canonical.claim_id,
        idempotency_key="idempotency-foreign-claim",
        agent_id="agent-foreign-claim",
        session_id="session-foreign-claim",
    )
    with pytest.raises(ValueError, match="immutable task_id"):
        runtime.create_task_claim_sync(
            TaskClaim(
                claim_id=canonical.claim_id,
                task_id=foreign_claim_identity.task_id,
                agent_id=foreign_claim_identity.agent_id,
                session_id=foreign_claim_identity.session_id,
                status="completed",
                metadata=foreign_claim_identity.to_metadata(),
            )
        )
    assert runtime.get_execution_identity_sync(foreign_claim_identity.run_id) is None
    assert runtime.get_task_claim_sync(canonical.claim_id) == terminal_claim

    terminal_run = runtime.create_delegation_run_sync(
        DelegationRun(
            run_id=canonical.run_id,
            task_id=canonical.task_id,
            assigned_to=canonical.agent_id,
            claim_id=canonical.claim_id,
            session_id=canonical.session_id,
            status="completed",
            completed_at=NOW,
            metadata=canonical.to_metadata(),
        )
    )
    with sqlite3.connect(runtime.db_path) as db:
        db.execute(
            "DELETE FROM execution_identities WHERE run_id = ?",
            (canonical.run_id,),
        )
        db.commit()
    foreign_run_identity = ExecutionIdentity.new(
        trace_id="trace-foreign-run",
        correlation_id="correlation-foreign-run",
        task_id="task-foreign-run",
        run_id=canonical.run_id,
        claim_id="claim-foreign-run",
        idempotency_key="idempotency-foreign-run",
        agent_id="agent-foreign-run",
        session_id="session-foreign-run",
    )
    with pytest.raises(ValueError, match="immutable task_id"):
        runtime.create_delegation_run_sync(
            DelegationRun(
                run_id=canonical.run_id,
                task_id=foreign_run_identity.task_id,
                assigned_to=foreign_run_identity.agent_id,
                claim_id=foreign_run_identity.claim_id,
                session_id=foreign_run_identity.session_id,
                status="completed",
                completed_at=NOW,
                metadata=foreign_run_identity.to_metadata(),
            )
        )
    assert runtime.get_execution_identity_sync(canonical.run_id) is None
    assert runtime.get_delegation_run_sync(canonical.run_id) == terminal_run


@pytest.mark.parametrize("surface", ["claim", "run"])
def test_sync_owner_row_rejects_preexisting_foreign_run_identity_atomically(
    tmp_path: Path,
    surface: str,
) -> None:
    runtime = RuntimeStateStore(
        tmp_path / f"runtime-{surface}.db",
        include_memory_plane=False,
    )
    owner = _identity(f"shared-{surface}")
    runtime.record_execution_identity_sync(owner, source="canonical-owner")
    candidate = ExecutionIdentity.new(
        trace_id=f"trace-foreign-{surface}",
        correlation_id=f"correlation-foreign-{surface}",
        task_id=f"task-foreign-{surface}",
        run_id=owner.run_id,
        claim_id=f"claim-foreign-{surface}",
        idempotency_key=f"idempotency-foreign-{surface}",
        agent_id=f"agent-foreign-{surface}",
        session_id=f"session-foreign-{surface}",
    )

    with pytest.raises(ValueError, match="execution identity conflict"):
        if surface == "claim":
            runtime.create_task_claim_sync(
                TaskClaim(
                    claim_id=candidate.claim_id,
                    task_id=candidate.task_id,
                    agent_id=candidate.agent_id,
                    session_id=candidate.session_id,
                    status="running",
                    metadata=candidate.to_metadata(),
                )
            )
        else:
            runtime.create_delegation_run_sync(
                DelegationRun(
                    run_id=candidate.run_id,
                    task_id=candidate.task_id,
                    assigned_to=candidate.agent_id,
                    claim_id=candidate.claim_id,
                    session_id=candidate.session_id,
                    status="running",
                    metadata=candidate.to_metadata(),
                )
            )

    assert runtime.get_execution_identity_sync(owner.run_id) == owner
    assert runtime.get_task_claim_sync(candidate.claim_id) is None
    assert runtime.get_delegation_run_sync(candidate.run_id) is None


@pytest.mark.parametrize("surface", ["claim", "run"])
def test_sync_owner_row_preserves_richer_durable_identity(
    tmp_path: Path,
    surface: str,
) -> None:
    runtime = RuntimeStateStore(
        tmp_path / f"runtime-sync-rich-{surface}.db",
        include_memory_plane=False,
    )
    durable = replace(
        _identity(f"sync-rich-{surface}"),
        parent_run_id="parent-canonical",
        metadata={"capability": "cap-a", "additive": "x"},
    )
    runtime.record_execution_identity_sync(durable, source="canonical-owner")
    sparse = replace(durable, parent_run_id="", metadata={})

    if surface == "claim":
        candidate = TaskClaim(
            claim_id=sparse.claim_id,
            task_id=sparse.task_id,
            agent_id=sparse.agent_id,
            session_id=sparse.session_id,
            status="running",
            metadata=sparse.to_metadata(),
        )
        owner = runtime.create_task_claim_sync(candidate)
        assert runtime.create_task_claim_sync(candidate) == owner
    else:
        candidate = DelegationRun(
            run_id=sparse.run_id,
            task_id=sparse.task_id,
            assigned_to=sparse.agent_id,
            claim_id=sparse.claim_id,
            session_id=sparse.session_id,
            status="running",
            metadata=sparse.to_metadata(),
        )
        owner = runtime.create_delegation_run_sync(candidate)
        assert runtime.create_delegation_run_sync(candidate) == owner
        assert owner.parent_run_id == durable.parent_run_id

    assert ExecutionIdentity.from_metadata(owner.metadata, require=True) == durable
    assert runtime.get_execution_identity_sync(durable.run_id) == durable


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["claim", "run"])
async def test_async_owner_row_preserves_richer_durable_identity(
    tmp_path: Path,
    surface: str,
) -> None:
    runtime = RuntimeStateStore(
        tmp_path / f"runtime-async-rich-{surface}.db",
        include_memory_plane=False,
    )
    durable = replace(
        _identity(f"async-rich-{surface}"),
        parent_run_id="parent-canonical",
        metadata={"capability": "cap-a", "additive": "x"},
    )
    await runtime.record_execution_identity(durable, source="canonical-owner")
    sparse = replace(durable, parent_run_id="", metadata={})

    if surface == "claim":
        candidate = TaskClaim(
            claim_id=sparse.claim_id,
            task_id=sparse.task_id,
            agent_id=sparse.agent_id,
            session_id=sparse.session_id,
            status="running",
            metadata=sparse.to_metadata(),
        )
        owner = await runtime.record_task_claim(candidate)
        assert await runtime.record_task_claim(candidate) == owner
    else:
        candidate = DelegationRun(
            run_id=sparse.run_id,
            task_id=sparse.task_id,
            assigned_to=sparse.agent_id,
            claim_id=sparse.claim_id,
            session_id=sparse.session_id,
            status="running",
            metadata=sparse.to_metadata(),
        )
        owner = await runtime.record_delegation_run(candidate)
        assert await runtime.record_delegation_run(candidate) == owner
        assert owner.parent_run_id == durable.parent_run_id

    assert ExecutionIdentity.from_metadata(owner.metadata, require=True) == durable
    assert await runtime.get_execution_identity(durable.run_id) == durable


def test_sync_run_rejects_parent_lineage_fork(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = ExecutionIdentity.new(
        trace_id="trace-parent-lineage",
        correlation_id="correlation-parent-lineage",
        task_id="task-parent-lineage",
        run_id="run-parent-lineage",
        claim_id="claim-parent-lineage",
        idempotency_key="idempotency-parent-lineage",
        agent_id="agent-parent-lineage",
        session_id="session-parent-lineage",
        parent_run_id="parent-canonical",
    )
    with pytest.raises(MissingExecutionIdentity, match="parent_run_id"):
        runtime.create_delegation_run_sync(
            DelegationRun(
                run_id=identity.run_id,
                task_id=identity.task_id,
                assigned_to=identity.agent_id,
                claim_id=identity.claim_id,
                session_id=identity.session_id,
                parent_run_id="parent-foreign",
                status="running",
                metadata=identity.to_metadata(),
            )
        )
    assert runtime.get_delegation_run_sync(identity.run_id) is None
    assert runtime.get_execution_identity_sync(identity.run_id) is None


@pytest.mark.parametrize(
    "alias",
    [
        "causation_id",
        "external_a2a_task_id",
        "message_id",
        "event_id",
        "artifact_id",
        "proposal_id",
    ],
)
def test_runtime_owner_rejects_flat_identity_alias_contradiction(
    tmp_path: Path,
    alias: str,
) -> None:
    runtime = RuntimeStateStore(
        tmp_path / f"runtime-alias-{alias}.db",
        include_memory_plane=False,
    )
    identity = _identity(f"alias-{alias}")
    metadata = identity.to_metadata()
    metadata[alias] = "foreign-coordinate"

    with pytest.raises(ValueError, match="aliases conflict"):
        runtime.create_task_claim_sync(
            TaskClaim(
                claim_id=identity.claim_id,
                task_id=identity.task_id,
                agent_id=identity.agent_id,
                session_id=identity.session_id,
                status="running",
                metadata=metadata,
            )
        )
    assert runtime.get_task_claim_sync(identity.claim_id) is None
    assert runtime.get_execution_identity_sync(identity.run_id) is None


@pytest.mark.asyncio
async def test_open_claim_identity_cannot_be_rebound(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    original_identity = _identity("open-claim-owner")
    original = await runtime.record_task_claim(
        TaskClaim(
            claim_id=original_identity.claim_id,
            task_id=original_identity.task_id,
            agent_id=original_identity.agent_id,
            session_id=original_identity.session_id,
            status="running",
            metadata=original_identity.to_metadata(),
        )
    )
    foreign_identity = ExecutionIdentity.new(
        trace_id="trace-open-foreign",
        correlation_id="correlation-open-foreign",
        task_id=original_identity.task_id,
        run_id="run-open-foreign",
        claim_id=original_identity.claim_id,
        idempotency_key="idempotency-open-foreign",
        agent_id=original_identity.agent_id,
        session_id=original_identity.session_id,
    )
    with pytest.raises(ValueError, match="cannot be rebound|aliases conflict"):
        await runtime.record_task_claim(
            replace(original, metadata=foreign_identity.to_metadata())
        )
    assert await runtime.get_task_claim(original.claim_id) == original


@pytest.mark.asyncio
@pytest.mark.parametrize("api", ["acknowledge", "heartbeat", "cas"])
async def test_claim_mutators_preserve_exact_execution_identity(
    tmp_path: Path,
    api: str,
) -> None:
    runtime = RuntimeStateStore(
        tmp_path / f"runtime-claim-mutator-{api}.db",
        include_memory_plane=False,
    )
    identity = _identity(f"claim-mutator-{api}")
    original = await runtime.record_task_claim(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            session_id=identity.session_id,
            status="running",
            claimed_at=NOW - timedelta(minutes=1),
            heartbeat_at=NOW - timedelta(seconds=1),
            stale_after=NOW + timedelta(minutes=1),
            metadata=identity.to_metadata(),
        )
    )
    foreign = identity.with_updates(run_id=f"foreign-{identity.run_id}")

    with pytest.raises(ValueError, match="cannot be rebound|aliases conflict"):
        if api == "acknowledge":
            await runtime.acknowledge_task_claim(
                original.claim_id,
                metadata=foreign.to_metadata(),
            )
        elif api == "heartbeat":
            await runtime.heartbeat_task_claim(
                original.claim_id,
                heartbeat_at=NOW,
                metadata=foreign.to_metadata(),
            )
        else:
            await runtime.compare_and_swap_task_claim(
                original,
                replace(
                    original,
                    heartbeat_at=NOW,
                    stale_after=NOW + timedelta(minutes=2),
                    metadata=foreign.to_metadata(),
                ),
                require_unexpired_at=NOW,
            )
    assert await runtime.get_task_claim(original.claim_id) == original

    if api == "acknowledge":
        preserved = await runtime.acknowledge_task_claim(
            original.claim_id,
            metadata={},
        )
    elif api == "heartbeat":
        preserved = await runtime.heartbeat_task_claim(
            original.claim_id,
            heartbeat_at=NOW,
            metadata={},
        )
    else:
        preserved = await runtime.compare_and_swap_task_claim(
            original,
            replace(
                original,
                heartbeat_at=NOW,
                stale_after=NOW + timedelta(minutes=2),
                metadata={},
            ),
            require_unexpired_at=NOW,
        )
        assert preserved is not None
    assert ExecutionIdentity.from_metadata(
        preserved.metadata,
        require=True,
    ) == identity


@pytest.mark.asyncio
async def test_typed_stale_recovery_is_absorbing(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    mission_metadata = {"schema_version": "dharma.mission_control.v1"}
    claim = await runtime.record_task_claim(_claim(metadata=mission_metadata))
    recovered_claim = await runtime.record_task_claim(
        replace(claim, status="stale_recovered", recovered_at=NOW)
    )
    with pytest.raises(ValueError, match="terminal claim"):
        await runtime.record_task_claim(replace(recovered_claim, status="running"))

    run = await runtime.record_delegation_run(
        DelegationRun(
            run_id="run-stale-recovered-absorbing",
            task_id=claim.task_id,
            assigned_to=claim.agent_id,
            claim_id=claim.claim_id,
            session_id=claim.session_id,
            status="running",
            metadata=mission_metadata,
        )
    )
    recovered_run = await runtime.record_delegation_run(
        replace(
            run,
            status="stale_recovered",
            completed_at=NOW,
            failure_code="stale_lease_recovered",
        )
    )
    with pytest.raises(ValueError, match="terminal run"):
        await runtime.record_delegation_run(
            replace(
                recovered_run,
                status="running",
                completed_at=None,
                failure_code="",
                metadata={},
            )
        )


@pytest.mark.asyncio
async def test_generic_receipt_writers_cannot_replace_immutable_carriers(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(
        tmp_path / "runtime.db",
        include_memory_plane=False,
    )
    immutable = RuntimeReceipt(
        receipt_id="campaign-control-alpha",
        receipt_type="mission_campaign_control",
        status="completed",
        correlation_id="mission_campaign:alpha",
        payload={"mission_id": "alpha", "generation": 1, "sequence": 1},
        created_at=NOW,
    )
    await runtime.insert_runtime_receipt_exact(immutable)

    assert await runtime.record_runtime_receipt(immutable) == immutable
    conflicting = replace(
        immutable,
        receipt_type="ordinary-replacement",
        payload={**immutable.payload, "forged": True},
    )
    with pytest.raises(ValueError, match="immutable runtime receipt"):
        await runtime.record_runtime_receipt(conflicting)
    with pytest.raises(ValueError, match="immutable runtime receipt"):
        runtime.record_runtime_receipt_sync(conflicting)

    assert await runtime.get_runtime_receipt(immutable.receipt_id) == immutable


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "receipt_type",
    [
        "mission_attempt_terminal",
        "mission_attempt_recovery",
        "mission_verifier_result",
    ],
)
async def test_authority_receipts_are_immutable_to_generic_writers(
    tmp_path: Path,
    receipt_type: str,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    receipt = RuntimeReceipt(
        receipt_id=f"authority-{receipt_type}",
        receipt_type=receipt_type,
        status="completed",
        run_id="run-authority-receipt",
        task_id="task-authority-receipt",
        payload={"proof": receipt_type},
        created_at=NOW,
    )
    await runtime.record_runtime_receipt(receipt)
    forged = replace(
        receipt,
        receipt_type="ordinary",
        payload={"proof": "forged"},
    )
    with pytest.raises(ValueError, match="immutable runtime receipt"):
        await runtime.record_runtime_receipt(forged)
    with pytest.raises(ValueError, match="immutable runtime receipt"):
        runtime.record_runtime_receipt_sync(forged)
    assert await runtime.get_runtime_receipt(receipt.receipt_id) == receipt


@pytest.mark.asyncio
async def test_claim_cas_requires_exact_live_generation(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(
        tmp_path / "runtime.db",
        include_memory_plane=False,
    )
    expected = await runtime.record_task_claim(_claim())
    replacement = replace(
        expected,
        heartbeat_at=NOW + timedelta(seconds=1),
        stale_after=NOW + timedelta(minutes=2),
        metadata={**expected.metadata, "evidence_sequence": 1},
    )

    renewed = await runtime.compare_and_swap_task_claim(
        expected,
        replacement,
        require_unexpired_at=NOW,
    )

    assert renewed == replacement
    assert await runtime.compare_and_swap_task_claim(
        expected,
        replace(
            replacement,
            heartbeat_at=NOW + timedelta(seconds=2),
            stale_after=NOW + timedelta(minutes=3),
        ),
        require_unexpired_at=NOW,
    ) is None
    with pytest.raises(ValueError, match="fenced identity|immutable task_id"):
        await runtime.compare_and_swap_task_claim(
            renewed,
            replace(renewed, task_id="foreign-task"),
            require_unexpired_at=NOW,
        )


@pytest.mark.asyncio
async def test_claim_cas_rejects_expired_and_terminal_claims(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(
        tmp_path / "runtime.db",
        include_memory_plane=False,
    )
    expired = await runtime.record_task_claim(
        _claim(
            claim_id="claim-expired",
            stale_after=NOW - timedelta(seconds=1),
        )
    )
    expired_replacement = replace(
        expired,
        heartbeat_at=NOW + timedelta(seconds=1),
        stale_after=NOW + timedelta(minutes=1),
    )
    assert await runtime.compare_and_swap_task_claim(
        expired,
        expired_replacement,
        require_unexpired_at=NOW,
    ) is None


@pytest.mark.asyncio
async def test_generic_claim_writers_preserve_cas_owned_evidence(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    original = await runtime.record_task_claim(
        _claim(metadata={"mission_id": "mission-alpha"})
    )
    identity = ExecutionIdentity.new(
        trace_id="trace-owner",
        correlation_id="correlation-owner",
        task_id=original.task_id,
        run_id="run-owner",
        claim_id=original.claim_id,
        idempotency_key="owner-idempotency",
        agent_id=original.agent_id,
        session_id=original.session_id,
    )
    await runtime.record_execution_identity(identity, source="test-owner")
    await runtime.record_delegation_run(
        DelegationRun(
            run_id=identity.run_id,
            task_id=identity.task_id,
            assigned_to=identity.agent_id,
            claim_id=identity.claim_id,
            session_id=identity.session_id,
            status="running",
        )
    )
    evidence = {
        "last_sequence": 1,
        "last_delta_id": "delta-alpha",
        "last_observed_at": NOW.isoformat(),
        "artifact_ids": [],
        "receipt_ids": ["work-receipt"],
        "consumed_artifact_ids": [],
        "consumed_receipt_ids": ["work-receipt"],
    }
    replacement = replace(
        original,
        heartbeat_at=NOW,
        stale_after=NOW + timedelta(minutes=2),
        metadata={**original.metadata, "mission_control_evidence": evidence},
    )
    payload = {
        "mission_id": "mission-alpha",
        "task_id": original.task_id,
        "run_id": identity.run_id,
        "claim_id": original.claim_id,
        "agent_id": original.agent_id,
        "delta_id": "delta-alpha",
        "sequence": 1,
        "observed_at": NOW.isoformat(),
        "summary": "Fresh durable evidence.",
        "artifact_ids": [],
        "receipt_ids": ["work-receipt"],
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode()
    payload["evidence_digest"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    receipt = RuntimeReceipt(
        receipt_id=(
            "evidence_delta_receipt_"
            + hashlib.sha256(b"delta-alpha").hexdigest()[:24]
        ),
        receipt_type="mission_evidence_delta",
        status="recorded",
        run_id=identity.run_id,
        task_id=identity.task_id,
        trace_id=identity.trace_id,
        correlation_id=identity.correlation_id,
        causation_id=identity.causation_id,
        parent_run_id=identity.parent_run_id,
        agent_id=identity.agent_id,
        idempotency_key=identity.idempotency_key,
        side_effect_key="mission_evidence:delta-alpha",
        payload=payload,
        created_at=NOW,
    )
    renewed = await runtime.compare_and_swap_task_claim(
        original,
        replacement,
        require_unexpired_at=NOW - timedelta(seconds=1),
        require_open_run_id=identity.run_id,
        atomic_receipt=receipt,
    )
    assert renewed is not None

    terminal = await runtime.record_task_claim(
        replace(
            original,
            status="completed",
            heartbeat_at=NOW - timedelta(seconds=10),
            stale_after=NOW,
            metadata={"mission_id": "mission-alpha", "owner_result": "done"},
        )
    )
    assert terminal.status == "completed"
    assert terminal.heartbeat_at == NOW
    assert terminal.stale_after == NOW
    assert terminal.metadata["mission_control_evidence"] == evidence

    with pytest.raises(ValueError, match="reserved evidence metadata conflict"):
        await runtime.record_task_claim(
            replace(
                terminal,
                metadata={
                    **terminal.metadata,
                    "mission_control_evidence": {**evidence, "last_sequence": 0},
                },
            )
        )

    terminal = await runtime.record_task_claim(
        _claim(
            claim_id="claim-terminal",
            status="completed",
        )
    )
    with pytest.raises(ValueError, match="terminal claim"):
        await runtime.compare_and_swap_task_claim(
            terminal,
            replace(
                terminal,
                heartbeat_at=NOW + timedelta(seconds=1),
                stale_after=NOW + timedelta(minutes=2),
            ),
            require_unexpired_at=NOW,
        )

    open_claim = await runtime.record_task_claim(
        _claim(claim_id="claim-terminal-run", task_id="task-terminal-run")
    )
    await runtime.record_delegation_run(
        DelegationRun(
            run_id="terminal-run",
            task_id=open_claim.task_id,
            assigned_to=open_claim.agent_id,
            claim_id=open_claim.claim_id,
            status="completed",
        )
    )
    assert await runtime.compare_and_swap_task_claim(
        open_claim,
        replace(
            open_claim,
            heartbeat_at=NOW + timedelta(seconds=1),
            stale_after=NOW + timedelta(minutes=2),
        ),
        require_unexpired_at=NOW,
        require_open_run_id="terminal-run",
    ) is None


@pytest.mark.asyncio
async def test_external_a2a_identity_list_is_bounded_and_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = RuntimeStateStore(
        tmp_path / "runtime.db",
        include_memory_plane=False,
    )
    monkeypatch.setattr(runtime_state_module, "_utc_now", lambda: NOW)
    await runtime.record_execution_identity(_identity("run-a"), source="test")
    await runtime.record_execution_identity(_identity("run-b"), source="test")

    matches = await runtime.list_execution_identities_by_external_a2a_task(
        "external-a2a-alpha",
        limit=2,
    )

    assert [identity.run_id for identity in matches] == ["run-b", "run-a"]
    assert [
        identity.run_id
        for identity in await runtime.list_execution_identities_by_external_a2a_task(
            "external-a2a-alpha",
            limit=1,
        )
    ] == ["run-b"]
    for invalid in (0, 101, True):
        with pytest.raises(ValueError, match="1 to 100"):
            await runtime.list_execution_identities_by_external_a2a_task(
                "external-a2a-alpha",
                limit=invalid,
            )


@pytest.mark.asyncio
async def test_execution_identity_preserves_immutable_authority_metadata(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(
        tmp_path / "runtime.db",
        include_memory_plane=False,
    )
    authority = {
        "schema_version": "dharma.dispatch-authority.v1",
        "mission_id": "mission-alpha",
        "authority_ref": "leases/execution-lease.json",
        "authority_digest": "sha256:authority-alpha",
        "authenticated_principal": "principal-alpha",
        "subject": "dharma.task.execute",
        "capability": "evidence_compile",
    }
    original = _identity("run-authorized", metadata=authority)
    await runtime.record_execution_identity(original, source="dispatcher")
    handler_copy = replace(original, metadata={})

    loaded = await runtime.record_execution_identity(
        handler_copy,
        source="a2a-handler",
        metadata={"handler_status": "running"},
    )

    assert loaded.metadata == {**authority, "handler_status": "running"}
    with pytest.raises(ValueError, match="immutable metadata conflict"):
        await runtime.record_execution_identity(
            handler_copy,
            source="a2a-handler",
            metadata={"authority_digest": "sha256:forged-authority"},
        )
    preserved = await runtime.get_execution_identity(original.run_id)
    assert preserved is not None
    assert preserved.metadata["authority_digest"] == authority["authority_digest"]
    with pytest.raises(ValueError, match="authenticated_principal"):
        await runtime.record_execution_identity(
            handler_copy,
            source="a2a-handler",
            metadata={"authenticated_principal": "principal-forged"},
        )


@pytest.mark.asyncio
async def test_terminal_idempotency_evidence_is_first_writer_wins(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("idempotency-terminal")
    side_effect_key = "invoke_agent:task-idempotency-terminal:a2a-handler"
    terminal_metadata = {
        "operation_hash": "operation-alpha",
        "result_json": json.dumps("result-alpha"),
        "receipt": {
            "receipt_id": "receipt-alpha",
            "status": "ok",
            "task_id": identity.task_id,
            "trace_id": identity.trace_id,
            "attributes": {
                "run_id": identity.run_id,
                "idempotency_key": identity.idempotency_key,
                "side_effect_key": side_effect_key,
            },
        },
    }
    assert await runtime.try_begin_idempotent_side_effect(
        identity,
        side_effect_key,
        metadata={"operation_hash": "operation-alpha"},
    )
    terminal = await runtime.complete_idempotent_side_effect(
        identity,
        side_effect_key,
        status="completed",
        result_receipt_id="receipt-alpha",
        metadata=terminal_metadata,
    )

    assert await runtime.complete_idempotent_side_effect(
        identity,
        side_effect_key,
        status="completed",
        result_receipt_id="receipt-alpha",
        metadata=terminal_metadata,
    ) == terminal
    assert await runtime.try_reclaim_idempotent_side_effect_with_token(
        identity.with_updates(run_id="recovery-run"),
        side_effect_key,
        expected_status="completed",
        expected_updated_at=terminal.updated_at,
    ) is None
    with pytest.raises(ValueError, match="immutable"):
        await runtime.complete_idempotent_side_effect(
            identity,
            side_effect_key,
            status="completed",
            result_receipt_id="receipt-forged",
            metadata={"evidence": "forged"},
        )
    assert await runtime.get_idempotency_record(
        identity.idempotency_key, side_effect_key
    ) == terminal


@pytest.mark.asyncio
async def test_reclaim_observes_terminal_completion_after_writer_lock(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("idempotency-lock-order")
    side_effect_key = "invoke_agent:task-idempotency-lock-order:a2a-handler"
    assert await runtime.try_begin_idempotent_side_effect(identity, side_effect_key)
    started = await runtime.get_idempotency_record(
        identity.idempotency_key, side_effect_key
    )
    assert started is not None
    terminal_at = started.updated_at + timedelta(microseconds=1)
    terminal_metadata = {
        "operation_hash": "operation-lock-order",
        "result_json": json.dumps("result-lock-order"),
        "receipt": {
            "receipt_id": "receipt-lock-order",
            "status": "ok",
            "task_id": identity.task_id,
            "trace_id": identity.trace_id,
            "attributes": {
                "run_id": identity.run_id,
                "idempotency_key": identity.idempotency_key,
                "side_effect_key": side_effect_key,
            },
        },
    }
    writer = sqlite3.connect(runtime.db_path)
    try:
        writer.execute("BEGIN IMMEDIATE")
        cursor = writer.execute(
            "UPDATE idempotency_records SET status = 'completed',"
            " result_receipt_id = ?, metadata_json = ?, updated_at = ?"
            " WHERE idempotency_key = ? AND side_effect_key = ? AND run_id = ?"
            " AND task_id = ? AND trace_id = ? AND correlation_id = ?"
            " AND status = ? AND result_receipt_id = ? AND metadata_json = ?"
            " AND created_at = ? AND updated_at = ?",
            (
                "receipt-lock-order",
                json.dumps(terminal_metadata, sort_keys=True),
                terminal_at.isoformat(),
                started.idempotency_key,
                started.side_effect_key,
                started.run_id,
                started.task_id,
                started.trace_id,
                started.correlation_id,
                started.status,
                started.result_receipt_id,
                json.dumps(started.metadata, sort_keys=True),
                started.created_at.isoformat(),
                started.updated_at.isoformat(),
            ),
        )
        assert cursor.rowcount == 1
        reclaim = asyncio.create_task(
            runtime.try_reclaim_idempotent_side_effect_with_token(
                identity.with_updates(run_id="recovery-run-lock-order"),
                side_effect_key,
                expected_status="completed",
            )
        )
        await asyncio.sleep(0.05)
        assert not reclaim.done()
        writer.commit()
        assert await reclaim is None
    finally:
        writer.rollback()
        writer.close()

    terminal = await runtime.get_idempotency_record(
        identity.idempotency_key, side_effect_key
    )
    assert terminal is not None
    assert terminal.status == "completed"
    assert terminal.result_receipt_id == "receipt-lock-order"


@pytest.mark.asyncio
async def test_idempotency_completion_rejects_foreign_identity(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("idempotency-owner")
    side_effect_key = "invoke_agent:task-idempotency-owner:a2a-handler"
    assert await runtime.try_begin_idempotent_side_effect(identity, side_effect_key)
    foreign = identity.with_updates(run_id="run-foreign")

    with pytest.raises(ValueError, match="identity conflicts"):
        await runtime.complete_idempotent_side_effect(
            foreign,
            side_effect_key,
            result_receipt_id="receipt-forged",
        )

    record = await runtime.get_idempotency_record(
        identity.idempotency_key, side_effect_key
    )
    assert record is not None
    assert record.status == "started"
    assert record.run_id == identity.run_id


@pytest.mark.asyncio
async def test_idempotency_completion_preserves_intent_hash_and_receipt_id(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("idempotency-completion-authority")
    side_effect_key = "invoke_agent:task-idempotency-completion-authority:a2a-handler"
    assert await runtime.try_begin_idempotent_side_effect(
        identity,
        side_effect_key,
        metadata={"operation_hash": "operation-alpha"},
    )
    started = await runtime.get_idempotency_record(
        identity.idempotency_key,
        side_effect_key,
    )
    assert started is not None

    with pytest.raises(ValueError, match="operation_hash conflicts"):
        await runtime.complete_idempotent_side_effect(
            identity,
            side_effect_key,
            result_receipt_id="receipt-alpha",
            metadata={"operation_hash": "operation-forged"},
        )
    assert await runtime.get_idempotency_record(
        identity.idempotency_key,
        side_effect_key,
    ) == started

    with pytest.raises(ValueError, match="result_receipt_id conflicts"):
        await runtime.complete_idempotent_side_effect(
            identity,
            side_effect_key,
            result_receipt_id="receipt-alpha",
            metadata={"result_receipt_id": "receipt-forged"},
        )
    assert await runtime.get_idempotency_record(
        identity.idempotency_key,
        side_effect_key,
    ) == started


def test_sync_idempotency_completion_preserves_intent_hash_and_receipt_id(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("sync-idempotency-completion-authority")
    side_effect_key = (
        "invoke_agent:task-sync-idempotency-completion-authority:a2a-handler"
    )
    assert runtime.try_begin_idempotent_side_effect_sync(
        identity,
        side_effect_key,
        metadata={"operation_hash": "operation-alpha"},
    )
    started = runtime.get_idempotency_record_sync(
        identity.idempotency_key,
        side_effect_key,
    )
    assert started is not None

    with pytest.raises(ValueError, match="operation_hash conflicts"):
        runtime.complete_idempotent_side_effect_sync(
            identity,
            side_effect_key,
            result_receipt_id="receipt-alpha",
            metadata={"operation_hash": ""},
        )
    assert runtime.get_idempotency_record_sync(
        identity.idempotency_key,
        side_effect_key,
    ) == started

    with pytest.raises(ValueError, match="result_receipt_id conflicts"):
        runtime.complete_idempotent_side_effect_sync(
            identity,
            side_effect_key,
            result_receipt_id="receipt-alpha",
            metadata={"result_receipt_id": "receipt-forged"},
        )
    assert runtime.get_idempotency_record_sync(
        identity.idempotency_key,
        side_effect_key,
    ) == started


@pytest.mark.asyncio
async def test_idempotency_owner_closes_duplicate_completion_and_replay(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    owner = _identity("idempotency-full-owner")
    owner = replace(owner, causation_id="cause-owner", parent_run_id="parent-owner")
    side_effect_key = "invoke_agent:task-idempotency-full-owner:a2a-handler"
    assert await runtime.try_begin_idempotent_side_effect(owner, side_effect_key)
    started = await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    )
    assert started is not None
    foreign = replace(
        owner,
        claim_id="claim-foreign",
        agent_id="agent-foreign",
        session_id="session-foreign",
        causation_id="cause-foreign",
        parent_run_id="parent-foreign",
        external_a2a_task_id="external-foreign",
    )

    with pytest.raises(ValueError, match="duplicate identity conflicts"):
        await runtime.try_begin_idempotent_side_effect(
            foreign,
            side_effect_key,
            stale_after_seconds=0,
        )
    assert await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    ) == started
    with pytest.raises(ValueError, match="completion identity conflicts"):
        await runtime.complete_idempotent_side_effect(
            foreign,
            side_effect_key,
            result_receipt_id="receipt-foreign",
        )
    assert await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    ) == started

    terminal = await runtime.complete_idempotent_side_effect(
        owner,
        side_effect_key,
        result_receipt_id="receipt-owner",
    )
    with pytest.raises(ValueError, match="completion identity conflicts"):
        await runtime.complete_idempotent_side_effect(
            foreign,
            side_effect_key,
            result_receipt_id="receipt-owner",
        )
    assert await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    ) == terminal
    receipts = await runtime.list_runtime_receipts(
        run_id=owner.run_id,
        receipt_type="side_effect_complete",
    )
    assert len(receipts) == 1
    assert receipts[0].agent_id == owner.agent_id
    assert receipts[0].causation_id == owner.causation_id
    assert receipts[0].parent_run_id == owner.parent_run_id


def test_sync_idempotency_owner_closes_completion_and_replay(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    owner = replace(
        _identity("sync-idempotency-full-owner"),
        causation_id="cause-owner",
        parent_run_id="parent-owner",
    )
    side_effect_key = "invoke_agent:task-sync-idempotency-full-owner:a2a-handler"
    assert runtime.try_begin_idempotent_side_effect_sync(owner, side_effect_key)
    started = runtime.get_idempotency_record_sync(
        owner.idempotency_key,
        side_effect_key,
    )
    assert started is not None
    foreign = replace(
        owner,
        claim_id="claim-foreign",
        agent_id="agent-foreign",
        session_id="session-foreign",
        causation_id="cause-foreign",
        parent_run_id="parent-foreign",
    )

    with pytest.raises(ValueError, match="completion identity conflicts"):
        runtime.complete_idempotent_side_effect_sync(
            foreign,
            side_effect_key,
            result_receipt_id="receipt-foreign",
        )
    assert runtime.get_idempotency_record_sync(
        owner.idempotency_key,
        side_effect_key,
    ) == started
    terminal = runtime.complete_idempotent_side_effect_sync(
        owner,
        side_effect_key,
        result_receipt_id="receipt-owner",
    )
    with pytest.raises(ValueError, match="completion identity conflicts"):
        runtime.complete_idempotent_side_effect_sync(
            foreign,
            side_effect_key,
            result_receipt_id="receipt-owner",
        )
    assert runtime.get_idempotency_record_sync(
        owner.idempotency_key,
        side_effect_key,
    ) == terminal


@pytest.mark.asyncio
async def test_idempotency_reclaim_rejects_same_run_foreign_owner(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    owner = _identity("idempotency-reclaim-owner")
    side_effect_key = "invoke_agent:task-idempotency-reclaim-owner:a2a-handler"
    assert await runtime.try_begin_idempotent_side_effect(owner, side_effect_key)
    assert not await runtime.try_begin_idempotent_side_effect(
        owner,
        side_effect_key,
        stale_after_seconds=0,
    )
    stale = await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    )
    assert stale is not None and stale.status == "stale"
    foreign = replace(
        owner,
        claim_id="claim-foreign",
        agent_id="agent-foreign",
        session_id="session-foreign",
    )

    with pytest.raises(ValueError, match="reclaim identity conflicts"):
        await runtime.try_reclaim_idempotent_side_effect_with_token(
            foreign,
            side_effect_key,
            expected_status="stale",
            expected_updated_at=stale.updated_at,
        )
    assert await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    ) == stale


@pytest.mark.asyncio
async def test_run_can_bind_multiple_message_effect_idempotency_keys(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    bus = MessageBus(
        tmp_path / "messages.db",
        runtime_state=runtime,
        require_identity=True,
    )
    await bus.init_db()
    root = _identity("multi-message-effects")
    first_identity = replace(root, idempotency_key="message-effect-one")
    second_identity = replace(root, idempotency_key="message-effect-two")
    first = Message(
        from_agent="agent-a",
        to_agent="agent-b",
        body="first",
        metadata=identity_metadata(first_identity, surface="message_bus"),
    )
    second = Message(
        from_agent="agent-a",
        to_agent="agent-b",
        body="second",
        metadata=identity_metadata(second_identity, surface="message_bus"),
    )

    assert await bus.send(first) == first.id
    assert await bus.send(second) == second.id
    records = [
        await runtime.get_idempotency_record(
            effect_identity.idempotency_key,
            f"message_bus.send:{effect_identity.idempotency_key}",
        )
        for effect_identity in (first_identity, second_identity)
    ]
    assert all(record is not None and record.status == "completed" for record in records)
    canonical = await runtime.get_execution_identity(root.run_id)
    assert canonical is not None
    assert canonical.idempotency_key == first_identity.idempotency_key


def test_sync_run_can_bind_multiple_effect_idempotency_keys(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    root = _identity("sync-multi-effects")
    effects = (
        replace(root, idempotency_key="sync-effect-one", message_id="message-one"),
        replace(root, idempotency_key="sync-effect-two", message_id="message-two"),
    )

    for effect in effects:
        side_effect_key = f"tool.invoke:{effect.idempotency_key}"
        assert runtime.try_begin_idempotent_side_effect_sync(effect, side_effect_key)
        rebound = runtime.record_execution_identity_sync(
            effect,
            source="sync-effect",
        )
        assert rebound.run_id == root.run_id
        runtime.complete_idempotent_side_effect_sync(
            effect,
            side_effect_key,
            result_receipt_id=f"receipt-{effect.idempotency_key}",
        )
        record = runtime.get_idempotency_record_sync(
            effect.idempotency_key,
            side_effect_key,
        )
        assert record is not None and record.status == "completed"


@pytest.mark.asyncio
async def test_idempotency_owner_accepts_durable_sparse_lineage_enrichment(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    sparse = replace(
        _identity("idempotency-lineage-enrichment"),
        causation_id="",
        parent_run_id="",
        external_a2a_task_id="",
    )
    side_effect_key = "invoke_agent:task-idempotency-lineage-enrichment:a2a-handler"
    assert await runtime.try_begin_idempotent_side_effect(sparse, side_effect_key)
    enriched = replace(
        sparse,
        causation_id="cause-enriched",
        parent_run_id="parent-enriched",
        external_a2a_task_id="external-enriched",
    )
    assert await runtime.record_execution_identity(
        enriched,
        source="lineage-enrichment",
    ) == enriched

    completed = await runtime.complete_idempotent_side_effect(
        enriched,
        side_effect_key,
        result_receipt_id="receipt-enriched",
    )
    assert completed.status == "completed"
    receipt = (
        await runtime.list_runtime_receipts(
            run_id=enriched.run_id,
            receipt_type="side_effect_complete",
        )
    )[0]
    assert receipt.causation_id == enriched.causation_id
    assert receipt.parent_run_id == enriched.parent_run_id


@pytest.mark.asyncio
async def test_idempotency_begin_rejects_foreign_immutable_authority_metadata(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    owner = _identity(
        "idempotency-authority-metadata",
        metadata={
            "mission_id": "mission-owner",
            "authority_digest": "sha256:owner",
            "authenticated_principal": "principal-owner",
        },
    )
    await runtime.record_execution_identity(owner, source="authority-owner")
    foreign = replace(
        owner,
        idempotency_key="effect-foreign-authority",
        metadata={
            "mission_id": "mission-foreign",
            "authority_digest": "sha256:foreign",
            "authenticated_principal": "principal-foreign",
        },
    )
    side_effect_key = "effect:foreign-authority"

    with pytest.raises(ValueError, match="immutable metadata conflict"):
        await runtime.try_begin_idempotent_side_effect(
            foreign,
            side_effect_key,
        )
    assert await runtime.get_idempotency_record(
        foreign.idempotency_key,
        side_effect_key,
    ) is None


def test_sync_idempotency_begin_rejects_foreign_immutable_authority_metadata(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    owner = _identity(
        "sync-idempotency-authority-metadata",
        metadata={
            "mission_id": "mission-owner",
            "authority_digest": "sha256:owner",
            "authenticated_principal": "principal-owner",
        },
    )
    runtime.record_execution_identity_sync(owner, source="authority-owner")
    foreign = replace(
        owner,
        idempotency_key="sync-effect-foreign-authority",
        metadata={
            "mission_id": "mission-foreign",
            "authority_digest": "sha256:foreign",
            "authenticated_principal": "principal-foreign",
        },
    )
    side_effect_key = "sync-effect:foreign-authority"

    with pytest.raises(ValueError, match="immutable metadata conflict"):
        runtime.try_begin_idempotent_side_effect_sync(
            foreign,
            side_effect_key,
        )
    assert runtime.get_idempotency_record_sync(
        foreign.idempotency_key,
        side_effect_key,
    ) is None


@pytest.mark.asyncio
async def test_idempotency_replay_paths_reject_foreign_authority_metadata(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    authority = {
        "mission_id": "mission-owner",
        "authority_digest": "sha256:owner",
        "authenticated_principal": "principal-owner",
    }
    owner = _identity("idempotency-authority-replay", metadata=authority)
    side_effect_key = "effect:authority-replay"
    assert await runtime.try_begin_idempotent_side_effect(owner, side_effect_key)
    started = await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    )
    assert started is not None
    foreign = replace(
        owner,
        metadata={
            "mission_id": "mission-foreign",
            "authority_digest": "sha256:foreign",
            "authenticated_principal": "principal-foreign",
        },
    )

    with pytest.raises(ValueError, match="duplicate identity conflicts"):
        await runtime.try_begin_idempotent_side_effect(
            foreign,
            side_effect_key,
            stale_after_seconds=0,
        )
    assert await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    ) == started

    with pytest.raises(ValueError, match="completion identity conflicts"):
        await runtime.complete_idempotent_side_effect(
            foreign,
            side_effect_key,
            result_receipt_id="receipt-owner",
        )
    with pytest.raises(ValueError, match="side-effect completion identity conflicts"):
        await runtime.record_side_effect_complete(
            foreign,
            side_effect_key,
            result_receipt_id="receipt-owner",
        )
    assert not await runtime.list_runtime_receipts(
        run_id=owner.run_id,
        receipt_type="side_effect_complete",
    )
    assert await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    ) == started

    sparse = replace(owner, metadata={})
    assert not await runtime.try_begin_idempotent_side_effect(sparse, side_effect_key)
    terminal = await runtime.complete_idempotent_side_effect(
        sparse,
        side_effect_key,
        result_receipt_id="receipt-owner",
    )
    assert terminal.status == "completed"
    durable = await runtime.get_execution_identity(owner.run_id)
    assert durable is not None and durable.metadata == authority

    with pytest.raises(ValueError, match="completion identity conflicts"):
        await runtime.complete_idempotent_side_effect(
            foreign,
            side_effect_key,
            result_receipt_id="receipt-owner",
        )
    assert await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    ) == terminal
    assert len(
        await runtime.list_runtime_receipts(
            run_id=owner.run_id,
            receipt_type="side_effect_complete",
        )
    ) == 1


def test_sync_idempotency_replay_paths_reject_foreign_authority_metadata(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    authority = {
        "mission_id": "mission-owner",
        "authority_digest": "sha256:owner",
        "authenticated_principal": "principal-owner",
    }
    owner = _identity("sync-idempotency-authority-replay", metadata=authority)
    side_effect_key = "sync-effect:authority-replay"
    assert runtime.try_begin_idempotent_side_effect_sync(owner, side_effect_key)
    started = runtime.get_idempotency_record_sync(
        owner.idempotency_key,
        side_effect_key,
    )
    assert started is not None
    foreign = replace(
        owner,
        metadata={
            "mission_id": "mission-foreign",
            "authority_digest": "sha256:foreign",
            "authenticated_principal": "principal-foreign",
        },
    )

    with pytest.raises(ValueError, match="duplicate identity conflicts"):
        runtime.try_begin_idempotent_side_effect_sync(
            foreign,
            side_effect_key,
            stale_after_seconds=0,
        )
    assert runtime.get_idempotency_record_sync(
        owner.idempotency_key,
        side_effect_key,
    ) == started

    with pytest.raises(ValueError, match="completion identity conflicts"):
        runtime.complete_idempotent_side_effect_sync(
            foreign,
            side_effect_key,
            result_receipt_id="receipt-owner",
        )
    with pytest.raises(ValueError, match="side-effect completion identity conflicts"):
        runtime.record_side_effect_complete_sync(
            foreign,
            side_effect_key,
            result_receipt_id="receipt-owner",
        )
    with sqlite3.connect(runtime.db_path) as db:
        assert not db.execute(
            "SELECT 1 FROM runtime_receipts"
            " WHERE run_id = ? AND receipt_type = 'side_effect_complete'",
            (owner.run_id,),
        ).fetchall()
    assert runtime.get_idempotency_record_sync(
        owner.idempotency_key,
        side_effect_key,
    ) == started

    sparse = replace(owner, metadata={})
    assert not runtime.try_begin_idempotent_side_effect_sync(sparse, side_effect_key)
    terminal = runtime.complete_idempotent_side_effect_sync(
        sparse,
        side_effect_key,
        result_receipt_id="receipt-owner",
    )
    assert terminal.status == "completed"
    durable = runtime.get_execution_identity_sync(owner.run_id)
    assert durable is not None and durable.metadata == authority

    with pytest.raises(ValueError, match="completion identity conflicts"):
        runtime.complete_idempotent_side_effect_sync(
            foreign,
            side_effect_key,
            result_receipt_id="receipt-owner",
        )
    assert runtime.get_idempotency_record_sync(
        owner.idempotency_key,
        side_effect_key,
    ) == terminal
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT count(*) FROM runtime_receipts"
            " WHERE run_id = ? AND receipt_type = 'side_effect_complete'",
            (owner.run_id,),
        ).fetchone() == (1,)


@pytest.mark.asyncio
async def test_same_run_reclaim_rejects_foreign_authority_metadata(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    authority = {
        "mission_id": "mission-owner",
        "authority_digest": "sha256:owner",
        "authenticated_principal": "principal-owner",
    }
    owner = _identity("idempotency-authority-reclaim", metadata=authority)
    side_effect_key = "effect:authority-reclaim"
    assert await runtime.try_begin_idempotent_side_effect(owner, side_effect_key)
    assert not await runtime.try_begin_idempotent_side_effect(
        owner,
        side_effect_key,
        stale_after_seconds=0,
    )
    stale = await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    )
    assert stale is not None and stale.status == "stale"
    foreign = replace(
        owner,
        metadata={
            "mission_id": "mission-foreign",
            "authority_digest": "sha256:foreign",
            "authenticated_principal": "principal-foreign",
        },
    )

    with pytest.raises(ValueError, match="reclaim identity conflicts"):
        await runtime.try_reclaim_idempotent_side_effect_with_token(
            foreign,
            side_effect_key,
            expected_status="stale",
            expected_updated_at=stale.updated_at,
        )
    assert await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    ) == stale

    token = await runtime.try_reclaim_idempotent_side_effect_with_token(
        replace(owner, metadata={}),
        side_effect_key,
        expected_status="stale",
        expected_updated_at=stale.updated_at,
    )
    assert token is not None
    durable = await runtime.get_execution_identity(owner.run_id)
    assert durable is not None and durable.metadata == authority


@pytest.mark.asyncio
async def test_new_run_reclaim_inherits_and_cannot_replace_authority_metadata(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    authority = {
        "mission_id": "mission-owner",
        "authority_digest": "sha256:owner",
        "authenticated_principal": "principal-owner",
    }
    owner = _identity("idempotency-authority-new-run", metadata=authority)
    side_effect_key = "effect:authority-new-run"
    assert await runtime.try_begin_idempotent_side_effect(owner, side_effect_key)
    assert not await runtime.try_begin_idempotent_side_effect(
        owner,
        side_effect_key,
        stale_after_seconds=0,
    )
    stale = await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    )
    assert stale is not None and stale.status == "stale"
    foreign = replace(
        owner,
        trace_id="trace-foreign-retry",
        correlation_id="correlation-foreign-retry",
        run_id="run-foreign-retry",
        claim_id="claim-foreign-retry",
        agent_id="agent-foreign-retry",
        session_id="session-foreign-retry",
        parent_run_id=owner.run_id,
        metadata={
            "mission_id": "mission-foreign",
            "authority_digest": "sha256:foreign",
            "authenticated_principal": "principal-foreign",
        },
    )

    with pytest.raises(ValueError, match="reclaim authority conflicts"):
        await runtime.try_reclaim_idempotent_side_effect_with_token(
            foreign,
            side_effect_key,
            expected_status="stale",
            expected_updated_at=stale.updated_at,
        )
    assert await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    ) == stale
    assert await runtime.get_execution_identity(foreign.run_id) is None

    retry = replace(
        foreign,
        trace_id="trace-authorized-retry",
        correlation_id="correlation-authorized-retry",
        run_id="run-authorized-retry",
        claim_id="claim-authorized-retry",
        agent_id="agent-authorized-retry",
        session_id="session-authorized-retry",
        metadata={},
    )
    token = await runtime.try_reclaim_idempotent_side_effect_with_token(
        retry,
        side_effect_key,
        expected_status="stale",
        expected_updated_at=stale.updated_at,
    )
    assert token is not None
    record = await runtime.get_idempotency_record(
        owner.idempotency_key,
        side_effect_key,
    )
    assert record is not None
    assert record.status == "started"
    assert record.run_id == retry.run_id
    durable = await runtime.get_execution_identity(retry.run_id)
    assert durable is not None
    assert durable.metadata == authority


@pytest.mark.asyncio
async def test_side_effect_completion_payload_cannot_override_receipt_id(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("side-effect-completion-receipt-authority")

    with pytest.raises(ValueError, match="result_receipt_id conflicts"):
        await runtime.record_side_effect_complete(
            identity,
            "invoke_agent:task-side-effect-completion-receipt-authority:a2a-handler",
            result_receipt_id="receipt-alpha",
            payload={"result_receipt_id": "receipt-forged"},
        )
    assert not await runtime.list_runtime_receipts(run_id=identity.run_id)


def test_sync_side_effect_completion_payload_cannot_override_receipt_id(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("sync-side-effect-completion-receipt-authority")
    runtime.init_db_sync()

    with pytest.raises(ValueError, match="result_receipt_id conflicts"):
        runtime.record_side_effect_complete_sync(
            identity,
            "invoke_agent:task-sync-side-effect-completion-receipt-authority:a2a-handler",
            result_receipt_id="receipt-alpha",
            payload={"result_receipt_id": "receipt-forged"},
        )
    with sqlite3.connect(runtime.db_path) as db:
        assert not db.execute(
            "SELECT 1 FROM runtime_receipts WHERE run_id = ?",
            (identity.run_id,),
        ).fetchall()


@pytest.mark.asyncio
async def test_idempotency_duplicate_rejects_foreign_owner_before_stale_takeover(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("idempotency-duplicate-owner")
    side_effect_key = "invoke_agent:task-idempotency-duplicate-owner:a2a-handler"
    assert await runtime.try_begin_idempotent_side_effect(
        identity,
        side_effect_key,
        metadata={"operation_hash": "operation-alpha"},
    )
    started = await runtime.get_idempotency_record(
        identity.idempotency_key,
        side_effect_key,
    )
    assert started is not None

    with pytest.raises(ValueError, match="duplicate identity conflicts"):
        await runtime.try_begin_idempotent_side_effect(
            identity.with_updates(run_id="run-foreign-duplicate"),
            side_effect_key,
            metadata={"operation_hash": "operation-alpha"},
            stale_after_seconds=0,
        )

    assert await runtime.get_idempotency_record(
        identity.idempotency_key,
        side_effect_key,
    ) == started


def test_sync_idempotency_duplicate_rejects_foreign_owner_before_stale_takeover(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("sync-idempotency-duplicate-owner")
    side_effect_key = "invoke_agent:task-sync-idempotency-duplicate-owner:a2a-handler"
    assert runtime.try_begin_idempotent_side_effect_sync(
        identity,
        side_effect_key,
        metadata={"operation_hash": "operation-alpha"},
    )
    started = runtime.get_idempotency_record_sync(
        identity.idempotency_key,
        side_effect_key,
    )
    assert started is not None

    with pytest.raises(ValueError, match="duplicate identity conflicts"):
        runtime.try_begin_idempotent_side_effect_sync(
            identity.with_updates(run_id="run-foreign-sync-duplicate"),
            side_effect_key,
            metadata={"operation_hash": "operation-alpha"},
            stale_after_seconds=0,
        )

    assert runtime.get_idempotency_record_sync(
        identity.idempotency_key,
        side_effect_key,
    ) == started


@pytest.mark.asyncio
async def test_idempotency_completion_rejects_started_status_without_mutation(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("idempotency-nonterminal-completion")
    side_effect_key = "invoke_agent:task-idempotency-nonterminal-completion:a2a-handler"
    assert await runtime.try_begin_idempotent_side_effect(identity, side_effect_key)
    started = await runtime.get_idempotency_record(
        identity.idempotency_key,
        side_effect_key,
    )
    assert started is not None

    with pytest.raises(ValueError, match="terminal status"):
        await runtime.complete_idempotent_side_effect(
            identity,
            side_effect_key,
            status="started",
            result_receipt_id="receipt-forged",
            metadata={"evidence": "forged"},
        )

    assert await runtime.get_idempotency_record(
        identity.idempotency_key,
        side_effect_key,
    ) == started


def test_sync_idempotency_completion_rejects_started_status_without_mutation(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("sync-idempotency-nonterminal-completion")
    side_effect_key = (
        "invoke_agent:task-sync-idempotency-nonterminal-completion:a2a-handler"
    )
    assert runtime.try_begin_idempotent_side_effect_sync(identity, side_effect_key)
    started = runtime.get_idempotency_record_sync(
        identity.idempotency_key,
        side_effect_key,
    )
    assert started is not None

    with pytest.raises(ValueError, match="terminal status"):
        runtime.complete_idempotent_side_effect_sync(
            identity,
            side_effect_key,
            status="started",
            result_receipt_id="receipt-forged",
            metadata={"evidence": "forged"},
        )

    assert runtime.get_idempotency_record_sync(
        identity.idempotency_key,
        side_effect_key,
    ) == started


@pytest.mark.asyncio
async def test_exact_terminal_replay_heals_missing_completion_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("idempotency-crash-heal")
    side_effect_key = "invoke_agent:task-idempotency-crash-heal:a2a-handler"
    assert await runtime.try_begin_idempotent_side_effect(
        identity,
        side_effect_key,
        metadata={"operation_hash": "operation-alpha"},
    )
    started = await runtime.get_idempotency_record(
        identity.idempotency_key,
        side_effect_key,
    )
    assert started is not None
    original = runtime.record_side_effect_complete

    async def crash_after_terminal_commit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated post-commit crash")

    monkeypatch.setattr(
        runtime,
        "record_side_effect_complete",
        crash_after_terminal_commit,
    )
    with pytest.raises(RuntimeError, match="post-commit crash"):
        await runtime.complete_idempotent_side_effect(
            identity,
            side_effect_key,
            result_receipt_id="receipt-alpha",
            metadata={"evidence": "alpha"},
            expected_updated_at=started.updated_at,
        )
    terminal = await runtime.get_idempotency_record(
        identity.idempotency_key,
        side_effect_key,
    )
    assert terminal is not None and terminal.status == "completed"
    assert not await runtime.list_runtime_receipts(
        run_id=identity.run_id,
        receipt_type="side_effect_complete",
    )

    monkeypatch.setattr(runtime, "record_side_effect_complete", original)
    assert await runtime.complete_idempotent_side_effect(
        identity,
        side_effect_key,
        result_receipt_id="receipt-alpha",
        metadata={"evidence": "alpha"},
        expected_updated_at=started.updated_at,
    ) == terminal
    receipts = await runtime.list_runtime_receipts(
        run_id=identity.run_id,
        receipt_type="side_effect_complete",
    )
    assert len(receipts) == 1
    assert await runtime.complete_idempotent_side_effect(
        identity,
        side_effect_key,
        result_receipt_id="receipt-alpha",
        metadata={"evidence": "alpha"},
    ) == terminal
    assert await runtime.list_runtime_receipts(
        run_id=identity.run_id,
        receipt_type="side_effect_complete",
    ) == receipts


def test_sync_exact_terminal_replay_heals_missing_completion_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("sync-idempotency-crash-heal")
    side_effect_key = "invoke_agent:task-sync-idempotency-crash-heal:a2a-handler"
    assert runtime.try_begin_idempotent_side_effect_sync(
        identity,
        side_effect_key,
        metadata={"operation_hash": "operation-alpha"},
    )
    started = runtime.get_idempotency_record_sync(
        identity.idempotency_key,
        side_effect_key,
    )
    assert started is not None
    original = runtime.record_side_effect_complete_sync

    def crash_after_terminal_commit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated post-commit crash")

    monkeypatch.setattr(
        runtime,
        "record_side_effect_complete_sync",
        crash_after_terminal_commit,
    )
    with pytest.raises(RuntimeError, match="post-commit crash"):
        runtime.complete_idempotent_side_effect_sync(
            identity,
            side_effect_key,
            result_receipt_id="receipt-alpha",
            metadata={"evidence": "alpha"},
            expected_updated_at=started.updated_at,
        )
    terminal = runtime.get_idempotency_record_sync(
        identity.idempotency_key,
        side_effect_key,
    )
    assert terminal is not None and terminal.status == "completed"

    def completion_receipts() -> list[tuple[object, ...]]:
        with sqlite3.connect(runtime.db_path) as db:
            return db.execute(
                "SELECT receipt_id, status, payload_json FROM runtime_receipts"
                " WHERE run_id = ? AND receipt_type = 'side_effect_complete'"
                " ORDER BY receipt_id",
                (identity.run_id,),
            ).fetchall()

    assert not completion_receipts()

    monkeypatch.setattr(runtime, "record_side_effect_complete_sync", original)
    assert runtime.complete_idempotent_side_effect_sync(
        identity,
        side_effect_key,
        result_receipt_id="receipt-alpha",
        metadata={"evidence": "alpha"},
        expected_updated_at=started.updated_at,
    ) == terminal
    receipts = completion_receipts()
    assert len(receipts) == 1
    assert runtime.complete_idempotent_side_effect_sync(
        identity,
        side_effect_key,
        result_receipt_id="receipt-alpha",
        metadata={"evidence": "alpha"},
    ) == terminal
    assert completion_receipts() == receipts


def test_sync_terminal_idempotency_evidence_is_first_writer_wins(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity("sync-idempotency-terminal")
    side_effect_key = "invoke_agent:task-sync-idempotency-terminal:a2a-handler"
    assert runtime.try_begin_idempotent_side_effect_sync(identity, side_effect_key)
    terminal = runtime.complete_idempotent_side_effect_sync(
        identity,
        side_effect_key,
        result_receipt_id="receipt-alpha",
        metadata={"evidence": "alpha"},
    )
    assert runtime.complete_idempotent_side_effect_sync(
        identity,
        side_effect_key,
        result_receipt_id="receipt-alpha",
        metadata={"evidence": "alpha"},
    ) == terminal
    with pytest.raises(ValueError, match="immutable"):
        runtime.complete_idempotent_side_effect_sync(
            identity,
            side_effect_key,
            result_receipt_id="receipt-forged",
        )
