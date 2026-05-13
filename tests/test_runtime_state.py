from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from dharma_swarm.runtime_state import (
    ArtifactRecord,
    ContextBundleRecord,
    MemoryFact,
    RuntimeStateStore,
    SessionState,
    SessionEventRecord,
    build_session_event_from_ledger_record,
    memory_fact_id_for_artifact,
    operator_action_id_for_payload,
    result_artifact_id_for_event,
    OperatorAction,
)


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

    with sqlite3.connect(db_path) as db:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        journal_mode = str(db.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    assert journal_mode == "wal"
    assert {"sessions", "task_claims", "delegation_runs", "context_bundles"} <= tables
    assert "event_log" in tables


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


def test_runtime_state_records_operator_action_sync_idempotently(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    payload = {"decision": "accepted", "surface": "gate_registry"}
    action = OperatorAction(
        action_id=operator_action_id_for_payload(
            action_name="gate_proposal_approved",
            actor="operator",
            reason="ok",
            payload=payload,
        ),
        action_name="gate_proposal_approved",
        actor="operator",
        reason="ok",
        payload=payload,
    )

    store.record_operator_action_sync(action)
    store.record_operator_action_sync(action)

    saved = store.get_operator_action_sync(action.action_id)
    assert saved is not None
    assert saved.action_name == "gate_proposal_approved"
    assert saved.payload == payload


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


@pytest.mark.asyncio
async def test_result_persisted_session_event_projects_artifact(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    event = SessionEventRecord(
        event_id="sevt-result-1",
        session_id="sess-result",
        ledger_kind="task",
        event_name="result_persisted",
        task_id="task-result",
        agent_id="agent-1",
        payload={
            "artifact_path": "/tmp/task-result.md",
            "artifact_checksum": "sha256-artifact",
            "provenance_file": "/tmp/task-result.json",
            "result_sha256": "sha256-result",
            "trace_id": "trace-result",
        },
    )

    await store.record_session_event(event)

    artifacts = await store.list_artifacts(task_id="task-result", limit=10)

    assert len(artifacts) == 1
    assert artifacts[0].artifact_id == result_artifact_id_for_event(
        event.event_id,
        task_id=event.task_id,
        result_sha256="sha256-result",
    )
    assert artifacts[0].artifact_kind == "task_result"
    assert artifacts[0].promotion_state == "candidate"
    assert artifacts[0].payload_path == "/tmp/task-result.md"
    assert artifacts[0].manifest_path == "/tmp/task-result.json"
    assert artifacts[0].checksum == "sha256-artifact"
    assert artifacts[0].metadata["source_event_id"] == event.event_id
    assert artifacts[0].metadata["trace_id"] == "trace-result"


@pytest.mark.asyncio
async def test_record_artifact_projects_task_result_memory_fact(tmp_path) -> None:
    payload = tmp_path / "task-result.md"
    payload.write_text(
        "# Task Result\n\n"
        "**Task ID:** task-result\n\n"
        "---\n\n"
        "The result projector converts durable artifacts into memory facts.",
        encoding="utf-8",
    )
    store = RuntimeStateStore(tmp_path / "runtime.db")
    artifact = await store.record_artifact(
        ArtifactRecord(
            artifact_id="artifact_result_projection",
            session_id="sess-result",
            task_id="task-result",
            artifact_kind="task_result",
            payload_path=str(payload),
            checksum="sha256-artifact",
            promotion_state="candidate",
            metadata={"source_event_id": "sevt-result", "trace_id": "trace-result"},
        )
    )

    facts = await store.list_memory_facts(task_id="task-result", limit=10)

    assert len(facts) == 1
    assert facts[0].fact_id == memory_fact_id_for_artifact(artifact.artifact_id)
    assert facts[0].fact_kind == "task_result"
    assert facts[0].truth_state == "candidate"
    assert facts[0].confidence == 0.75
    assert facts[0].source_event_id == "sevt-result"
    assert facts[0].source_artifact_id == artifact.artifact_id
    assert facts[0].text == "The result projector converts durable artifacts into memory facts."
    assert facts[0].provenance["payload_path"] == str(payload)


@pytest.mark.asyncio
async def test_project_artifacts_to_memory_facts_backfills_existing_rows(tmp_path) -> None:
    payload = tmp_path / "late-result.md"
    db_path = tmp_path / "runtime.db"
    store = RuntimeStateStore(db_path)
    await store.init_db()
    artifact = ArtifactRecord(
        artifact_id="artifact_late_result",
        session_id="sess-late",
        task_id="task-late",
        artifact_kind="task_result",
        payload_path=str(payload),
        checksum="sha256-late",
        promotion_state="candidate",
        metadata={"source_event_id": "sevt-late"},
    )
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO artifact_records (artifact_id, session_id, task_id, run_id,"
            " artifact_kind, manifest_path, payload_path, checksum,"
            " parent_artifact_id, promotion_state, created_at, metadata_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                artifact.artifact_id,
                artifact.session_id,
                artifact.task_id,
                artifact.run_id,
                artifact.artifact_kind,
                artifact.manifest_path,
                artifact.payload_path,
                artifact.checksum,
                artifact.parent_artifact_id,
                artifact.promotion_state,
                artifact.created_at.isoformat(),
                json.dumps(artifact.metadata, sort_keys=True, ensure_ascii=True),
            ),
        )
        db.commit()
    payload.write_text("Backfilled artifact becomes one memory fact.", encoding="utf-8")

    first = await store.project_artifacts_to_memory_facts(session_id="sess-late")
    second = await store.project_artifacts_to_memory_facts(session_id="sess-late")
    facts = await store.list_memory_facts(task_id="task-late", limit=10)

    assert [fact.fact_id for fact in first] == [memory_fact_id_for_artifact(artifact.artifact_id)]
    assert [fact.fact_id for fact in second] == [memory_fact_id_for_artifact(artifact.artifact_id)]
    assert len(facts) == 1
    assert facts[0].text == "Backfilled artifact becomes one memory fact."


@pytest.mark.asyncio
async def test_blank_shared_artifact_does_not_project_memory_fact(tmp_path) -> None:
    payload = tmp_path / "blank-result.md"
    payload.write_text(
        "# Blank Result\n\n"
        "**Task ID:** task-blank\n\n"
        "---\n\n"
        "   ",
        encoding="utf-8",
    )
    store = RuntimeStateStore(tmp_path / "runtime.db")

    await store.record_artifact(
        ArtifactRecord(
            artifact_id="artifact_blank_result",
            session_id="sess-blank",
            task_id="task-blank",
            artifact_kind="task_result",
            payload_path=str(payload),
            checksum="sha256-blank",
            promotion_state="candidate",
        )
    )

    assert await store.list_memory_facts(task_id="task-blank", limit=10) == []


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


def test_runtime_state_backfills_result_artifacts_from_historic_ledgers(tmp_path) -> None:
    ledger_base = tmp_path / "ledgers"
    session_dir = ledger_base / "sess-results"
    session_dir.mkdir(parents=True)
    result_record = {
        "ts_utc": "2026-03-13T08:40:16+00:00",
        "session_id": "sess-results",
        "event": "result_persisted",
        "task_id": "task-result",
        "agent_id": "agent-1",
        "artifact_path": "/tmp/task-result.md",
        "artifact_checksum": "sha256-artifact",
        "provenance_file": "/tmp/task-result.json",
        "result_sha256": "sha256-result",
        "trace_id": "trace-result",
    }
    (session_dir / "task_ledger.jsonl").write_text(json.dumps(result_record) + "\n", encoding="utf-8")

    store = RuntimeStateStore(tmp_path / "runtime.db")
    first = store.index_ledgers_sync(ledger_base=ledger_base)
    second = store.index_ledgers_sync(ledger_base=ledger_base)

    rebuilt = build_session_event_from_ledger_record(
        session_id="sess-results",
        ledger_kind="task",
        record=result_record,
    )
    artifact_id = result_artifact_id_for_event(
        rebuilt.event_id,
        task_id="task-result",
        result_sha256="sha256-result",
    )
    with sqlite3.connect(tmp_path / "runtime.db") as db:
        rows = db.execute(
            "SELECT artifact_id, task_id, payload_path, metadata_json"
            " FROM artifact_records WHERE task_id = ?",
            ("task-result",),
        ).fetchall()

    assert first == (1, 1)
    assert second == (1, 1)
    assert rows == [
        (
            artifact_id,
            "task-result",
            "/tmp/task-result.md",
            json.dumps(
                {
                    "agent_id": "agent-1",
                    "artifact_checksum": "sha256-artifact",
                    "provenance_file": "/tmp/task-result.json",
                    "result_sha256": "sha256-result",
                    "source_event_id": rebuilt.event_id,
                    "projection_source": "runtime_state.result_persisted",
                    "trace_id": "trace-result",
                },
                sort_keys=True,
                ensure_ascii=True,
            ),
        )
    ]
