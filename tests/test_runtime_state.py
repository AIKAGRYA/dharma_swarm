from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from dharma_swarm.runtime_state import (
    ContextBundleRecord,
    MemoryFact,
    RUNTIME_RECEIPT_TYPES,
    RuntimeStateStore,
    SessionState,
    SessionEventRecord,
    TopologyStateRecord,
    build_session_event_from_ledger_record,
)
from dharma_swarm.spine.identity import ExecutionIdentity


@pytest.mark.asyncio
async def test_runtime_state_initializes_wal_and_core_tables(tmp_path) -> None:
    db_path = tmp_path / "runtime.db"
    store = RuntimeStateStore(db_path)
    await store.init_db()

    await store.upsert_session(
        SessionState(
            session_id="sess-1",
            operator_id="operator",
            status="active",
            current_task_id="task-1",
        )
    )
    fact = await store.record_memory_fact(
        MemoryFact(
            fact_id="fact-1",
            fact_kind="workspace_rule",
            truth_state="promoted",
            text="Use isolated workspaces with explicit publish/promotion.",
            confidence=0.95,
            session_id="sess-1",
            task_id="task-1",
        )
    )
    bundle = await store.record_context_bundle(
        ContextBundleRecord(
            bundle_id="ctx-1",
            session_id="sess-1",
            task_id="task-1",
            token_budget=1000,
            rendered_text="# Context",
            sections=[{"name": "Task State", "content": "task-1"}],
            source_refs=["memory://fact-1"],
            checksum="abc123",
        )
    )

    assert fact.fact_id == "fact-1"
    assert bundle.bundle_id == "ctx-1"
    assert (await store.get_session("sess-1")) is not None
    loaded_bundle = store.get_context_bundle_sync("ctx-1")
    assert loaded_bundle is not None
    assert loaded_bundle.rendered_text == "# Context"

    with sqlite3.connect(db_path) as db:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        journal_mode = str(db.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    assert journal_mode == "wal"
    assert {
        "sessions",
        "task_claims",
        "delegation_runs",
        "context_bundles",
        "topology_states",
    } <= tables
    assert "event_log" in tables


@pytest.mark.asyncio
async def test_topology_state_survives_store_restart(tmp_path) -> None:
    db_path = tmp_path / "runtime.db"
    store = RuntimeStateStore(db_path, include_memory_plane=False)
    await store.record_topology_state(
        TopologyStateRecord(
            run_id="run-topology",
            session_id="sess-topology",
            task_id="task-topology",
            topology="swarm",
            active_agent="agent-2",
            current_node="agent-2",
            checkpoint_id="task-topology:swarm:checkpoint",
            child_run_ids=["run-child-1"],
            allowed_handoffs={"agent-1": ["agent-2"]},
            handoff_receipts=[
                {
                    "status": "accepted",
                    "from_agent": "agent-1",
                    "to_agent": "agent-2",
                }
            ],
            state={"mode": "swarm", "status": "claimed"},
        )
    )

    restarted = RuntimeStateStore(db_path, include_memory_plane=False)
    loaded = await restarted.get_topology_state("run-topology")
    latest = await restarted.get_latest_topology_state_for_task("task-topology")

    assert loaded is not None
    assert loaded.active_agent == "agent-2"
    assert loaded.allowed_handoffs == {"agent-1": ["agent-2"]}
    assert loaded.handoff_receipts[0]["status"] == "accepted"
    assert loaded.child_run_ids == ["run-child-1"]
    assert latest is not None
    assert latest.run_id == "run-topology"


@pytest.mark.asyncio
async def test_runtime_state_updates_memory_fact_truth(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    await store.init_db()

    created = await store.record_memory_fact(
        MemoryFact(
            fact_id="fact-promote",
            fact_kind="lesson",
            truth_state="candidate",
            text="Operator-visible delivery ack prevents silent drop-off.",
            confidence=0.7,
            session_id="sess-2",
            task_id="task-2",
        )
    )
    updated = await store.update_memory_fact_truth(
        created.fact_id,
        truth_state="promoted",
        confidence=0.9,
        metadata={"promoted_by": "operator"},
    )
    facts = await store.list_memory_facts(
        session_id="sess-2",
        truth_state="promoted",
        limit=5,
    )

    assert updated.truth_state == "promoted"
    assert updated.confidence == 0.9
    assert updated.metadata["promoted_by"] == "operator"
    assert facts[0].fact_id == created.fact_id
    assert facts[0].updated_at >= datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_runtime_state_records_and_searches_session_events(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    await store.record_session_event(
        SessionEventRecord(
            event_id="sevt-1",
            session_id="sess-search",
            ledger_kind="progress",
            event_name="task_failed",
            task_id="task-9",
            agent_id="worker-loop",
            summary="provider timeout on fallback lane",
            event_text="task_failed task-9 worker-loop provider timeout on fallback lane",
            payload={"failure_signature": "provider_timeout"},
        )
    )

    hits = store.search_session_events_sync("provider timeout", session_id="sess-search")
    sessions = store.list_sessions_sync(limit=5)

    assert len(hits) == 1
    assert hits[0].event_name == "task_failed"
    assert hits[0].task_id == "task-9"
    assert sessions[0].session_id == "sess-search"


def test_session_event_and_episode_outbox_rollback_atomically(
    tmp_path,
    monkeypatch,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    event = SessionEventRecord(
        event_id="sevt-atomic",
        session_id="sess-atomic",
        ledger_kind="task",
        event_name="dispatch_assigned",
    )

    def fail_enqueue(*_args, **_kwargs):
        raise OSError("injected outbox failure")

    monkeypatch.setattr(
        RuntimeStateStore,
        "_enqueue_episode_outbox_sync_db",
        staticmethod(fail_enqueue),
    )
    with pytest.raises(OSError, match="outbox"):
        store.record_session_event_with_episode_outbox_sync(
            event,
            delivery_key="session-event:sevt-atomic:observation",
            episode_id="ep-atomic",
            attempt_id="at-atomic",
            event_type="observation_recorded",
            payload={"session_event_id": event.event_id},
        )

    with sqlite3.connect(store.db_path) as db:
        session_event_count = db.execute(
            "SELECT COUNT(*) FROM session_events WHERE event_id = ?",
            (event.event_id,),
        ).fetchone()[0]
        outbox_count = db.execute(
            "SELECT COUNT(*) FROM episode_event_outbox"
        ).fetchone()[0]
    assert session_event_count == 0
    assert outbox_count == 0


def test_episode_outbox_is_durable_idempotent_and_acknowledged(tmp_path) -> None:
    db_path = tmp_path / "runtime.db"
    store = RuntimeStateStore(db_path)
    first = store.enqueue_episode_event_sync(
        delivery_key="attempt:at-durable:started",
        episode_id="ep-durable",
        attempt_id="at-durable",
        event_type="attempt_started",
        payload={"session_id": "sess-durable"},
    )
    duplicate = store.enqueue_episode_event_sync(
        delivery_key="attempt:at-durable:started",
        episode_id="ep-durable",
        attempt_id="at-durable",
        event_type="attempt_started",
        payload={"session_id": "sess-durable"},
    )

    restarted = RuntimeStateStore(db_path)
    pending = restarted.list_pending_episode_events_sync(episode_id="ep-durable")
    acked = restarted.ack_episode_event_sync(
        first.delivery_key,
        episode_event_id="ev-durable",
    )

    assert duplicate.outbox_id == first.outbox_id
    assert first.schema_version == "episode_outbox_record.v1"
    assert [item.delivery_key for item in pending] == [first.delivery_key]
    assert acked.acked_at is not None
    assert acked.episode_event_id == "ev-durable"
    assert restarted.list_pending_episode_events_sync(episode_id="ep-durable") == []
    assert (
        restarted.enqueue_episode_event_sync(
            delivery_key="attempt:at-durable:started",
            episode_id="ep-durable",
            attempt_id="at-durable",
            event_type="attempt_started",
            payload={"session_id": "sess-durable"},
        ).acked_at
        is not None
    )
    with pytest.raises(ValueError, match="different content"):
        restarted.enqueue_episode_event_sync(
            delivery_key="attempt:at-durable:started",
            episode_id="ep-durable",
            attempt_id="at-other",
            event_type="attempt_started",
            payload={"session_id": "sess-durable"},
        )


def test_runtime_state_indexes_historic_ledgers(tmp_path) -> None:
    ledger_base = tmp_path / "ledgers"
    session_dir = ledger_base / "sess-old"
    session_dir.mkdir(parents=True)
    task_record = {
        "ts_utc": "2026-03-13T08:38:16+00:00",
        "session_id": "sess-old",
        "event": "dispatch_assigned",
        "task_id": "task-1",
        "agent_id": "a1",
        "reason": "architectural pass",
    }
    progress_record = {
        "ts_utc": "2026-03-13T08:39:16+00:00",
        "session_id": "sess-old",
        "event": "task_failed",
        "task_id": "task-1",
        "failure_signature": "provider_timeout",
    }
    (session_dir / "task_ledger.jsonl").write_text(json.dumps(task_record) + "\n", encoding="utf-8")
    (session_dir / "progress_ledger.jsonl").write_text(json.dumps(progress_record) + "\n", encoding="utf-8")

    store = RuntimeStateStore(tmp_path / "runtime.db")
    sessions_scanned, events_scanned = store.index_ledgers_sync(ledger_base=ledger_base)
    hits = store.search_session_events_sync("provider timeout", session_id="sess-old")
    rebuilt = build_session_event_from_ledger_record(
        session_id="sess-old",
        ledger_kind="progress",
        record=progress_record,
    )

    assert sessions_scanned == 1
    assert events_scanned == 2
    assert len(hits) == 1
    assert hits[0].event_id == rebuilt.event_id


@pytest.mark.asyncio
async def test_runtime_state_idempotency_writes_side_effect_receipts(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = ExecutionIdentity.new(
        task_id="task-receipt",
        run_id="run-receipt",
        trace_id="trace-receipt",
        correlation_id="corr-receipt",
        claim_id="claim-receipt",
        idempotency_key="idem-receipt",
        agent_id="agent-receipt",
    )
    side_effect_key = "message_bus.emit_event:test:event-1"

    should_execute = await store.try_begin_idempotent_side_effect(
        identity,
        side_effect_key,
        metadata={"surface": "message_bus"},
    )
    await store.complete_idempotent_side_effect(
        identity,
        side_effect_key,
        result_receipt_id="event-1",
        metadata={"surface": "message_bus"},
    )
    duplicate = await store.try_begin_idempotent_side_effect(
        identity,
        side_effect_key,
        metadata={"surface": "message_bus"},
    )

    receipts = await store.list_runtime_receipts(run_id=identity.run_id, limit=20)
    by_type = [receipt.receipt_type for receipt in receipts]
    consumed_statuses = [
        receipt.status
        for receipt in receipts
        if receipt.receipt_type == "idempotency_consumed"
    ]

    assert should_execute is True
    assert duplicate is False
    assert by_type.count("side_effect_intent") == 1
    assert by_type.count("side_effect_complete") == 1
    assert consumed_statuses == ["accepted", "duplicate"]
    assert all(receipt.trace_id == identity.trace_id for receipt in receipts)


@pytest.mark.asyncio
async def test_runtime_state_receipt_helpers_cover_saturation_types(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = ExecutionIdentity.new(
        task_id="task-saturation",
        run_id="run-saturation",
        trace_id="trace-saturation",
        correlation_id="corr-saturation",
        claim_id="claim-saturation",
        idempotency_key="idem-saturation",
        agent_id="agent-saturation",
        parent_run_id="run-parent",
        proposal_id="proposal-saturation",
    )

    await store.record_message_consumed(
        identity,
        "message-saturation",
        payload={"surface": "message_bus.consume_events"},
    )
    await store.record_ontology_action_receipt(
        identity,
        action_name="Approve",
        object_type="ActionProposal",
        object_id="proposal-saturation",
    )
    await store.record_ontology_action_receipt(
        identity,
        action_name="Approve",
        object_type="ActionProposal",
        object_id="proposal-saturation",
        applied=True,
    )
    await store.record_receipt_for_identity(
        identity,
        receipt_type="child_spawned",
        status="claimed",
        side_effect_key="child:run-parent:run-saturation",
        payload={"child_run_id": identity.run_id},
    )
    await store.record_receipt_for_identity(
        identity,
        receipt_type="child_completed",
        status="completed",
        side_effect_key="child:run-parent:run-saturation",
        payload={"child_run_id": identity.run_id},
    )
    for stage in ("proposal", "gate", "apply", "verify", "promote", "revert"):
        await store.record_self_mod_receipt(
            identity,
            stage=stage,
            status="recorded",
            proposal_id="proposal-saturation",
        )

    receipts = await store.list_runtime_receipts(run_id=identity.run_id, limit=50)
    receipt_types = {receipt.receipt_type for receipt in receipts}
    expected = {
        "message_consumed",
        "ontology_action_requested",
        "ontology_action_applied",
        "child_spawned",
        "child_completed",
        "self_mod_proposal",
        "self_mod_gate",
        "self_mod_apply",
        "self_mod_verify",
        "self_mod_promote",
        "self_mod_revert",
    }

    assert expected <= receipt_types
    assert expected <= RUNTIME_RECEIPT_TYPES
    assert all(receipt.run_id == identity.run_id for receipt in receipts)
    assert all(receipt.trace_id == identity.trace_id for receipt in receipts)
