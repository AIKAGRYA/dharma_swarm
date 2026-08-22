from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import dharma_swarm.runtime_state as runtime_state_module
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    SessionState,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity


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
    with pytest.raises(ValueError, match="fenced identity"):
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
