from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from dharma_swarm.operator_core import (
    CanonicalEntity,
    CanonicalEventEnvelope,
    CanonicalPermissionDecision,
    CanonicalRelation,
    CanonicalRoutingDecision,
    CanonicalRuntimeSnapshot,
    CanonicalSession,
    CanonicalWorkflowState,
    EntityBadge,
    EntityRef,
    EventAudience,
    EventSource,
    EventTransport,
    PermissionDecisionKind,
    PermissionRisk,
    RuntimeHealth,
    RuntimeTruthPacket,
    RuntimeTruthState,
    WorkflowExecutionMode,
    runtime_truth_packets_from_runtime_db,
    summarize_runtime_truth_packets,
)


def test_operator_core_contracts_hold_shell_neutral_shapes() -> None:
    entity = CanonicalEntity(
        kind="agent",
        id="qwen35-surgeon",
        title="Qwen Surgeon",
        subtitle="bounded coding lane",
        source_route="tui.agents",
        status=RuntimeHealth.OK,
        badges=[EntityBadge(label="live", tone=RuntimeHealth.OK)],
        raw={"provider": "openrouter"},
    )
    relation = CanonicalRelation(
        kind="assigned_to",
        from_ref=EntityRef(kind="task", id="task-1"),
        to_ref=EntityRef(kind="agent", id=entity.id),
        label="owns",
        evidence=["/api/commands/tasks"],
    )
    session = CanonicalSession(
        session_id="sess-1",
        provider_id="codex",
        model_id="gpt-5.4",
        cwd="/Users/dhyana/dharma_swarm",
        created_at="2026-04-02T00:00:00Z",
        updated_at="2026-04-02T00:10:00Z",
        status="running",
        branch_label="main",
        worktree_path="/Users/dhyana/dharma_swarm",
    )
    permission = CanonicalPermissionDecision(
        action_id="act-1",
        tool_name="Bash",
        risk=PermissionRisk.SHELL_OR_NETWORK,
        decision=PermissionDecisionKind.REQUIRE_APPROVAL,
        rationale="shell mutations must remain operator-gated",
        policy_source="workspace-policy",
        requires_confirmation=True,
        command_prefix="git status",
    )
    routing = CanonicalRoutingDecision(
        route_id="deep_code_work",
        provider_id="codex",
        model_id="gpt-5.4",
        strategy="responsive",
        reason="coding task with bounded mutability",
        fallback_chain=["claude:claude-sonnet-4-6", "openrouter:qwen2.5-coder"],
    )
    runtime = CanonicalRuntimeSnapshot(
        snapshot_id="snap-1",
        created_at="2026-04-02T00:00:00Z",
        repo_root="/Users/dhyana/dharma_swarm",
        runtime_db="/Users/dhyana/.dharma/state/runtime.db",
        health=RuntimeHealth.DEGRADED,
        bridge_status="connected",
        active_session_count=12,
        active_run_count=2,
        artifact_count=7,
        context_bundle_count=3,
        anomaly_count=1,
        verification_status="1 failing, 3/4 passing",
        warnings=["session rail delayed"],
    )
    workflow = CanonicalWorkflowState(
        workflow_id="wf-1",
        title="terminal convergence",
        execution_mode=WorkflowExecutionMode.SERIAL_WRITE,
        status="running",
        active_lane_ids=["lane-a", "lane-b"],
        blocked_by=["approval:workspace-write"],
        writable_scopes=["terminal/", "dharma_swarm/operator_core/"],
    )
    event = CanonicalEventEnvelope(
        event_id="evt-1",
        event_type="tool.result",
        source=EventSource.PROVIDER,
        audience=EventAudience.ALL,
        transport=EventTransport.STDIO,
        session_id=session.session_id,
        created_at="2026-04-02T00:00:05Z",
        payload={"tool_name": "Read", "ok": True},
        entity_refs=[EntityRef(kind="agent", id=entity.id)],
    )

    assert entity.badges[0].label == "live"
    assert relation.to_ref.id == entity.id
    assert session.worktree_path == "/Users/dhyana/dharma_swarm"
    assert permission.decision is PermissionDecisionKind.REQUIRE_APPROVAL
    assert routing.fallback_chain[0] == "claude:claude-sonnet-4-6"
    assert runtime.health is RuntimeHealth.DEGRADED
    assert workflow.execution_mode is WorkflowExecutionMode.SERIAL_WRITE
    assert event.entity_refs[0].kind == "agent"


def test_runtime_truth_packet_keeps_state_axes_separate() -> None:
    packet = RuntimeTruthPacket(
        surface_id="mission.demo",
        kind="mission_projection",
        observed_at="2026-06-04T00:00:00Z",
        owner_surface="tests",
        source_kind="fixture",
        run_id="run-1",
        mission_id="mission-1",
        correlation_id="corr-1",
        task_id="task-1",
        receipt_refs=["receipts/mission-1.json"],
        artifact_refs=["artifacts/mission-1/report.md"],
        source_refs=["tests/fixtures/runtime_truth.json"],
        heartbeat_state=RuntimeTruthState.RUNNING_BY_HEARTBEAT,
        progress_state=RuntimeTruthState.STALLED_BY_ARTIFACT_PROGRESS,
        completion_state=RuntimeTruthState.BLOCKED_BY_RECEIPT,
        authority_state=RuntimeTruthState.PROJECTION_ONLY,
        mutation_state=RuntimeTruthState.NO_MUTATION_OBSERVED,
        external_state=RuntimeTruthState.EXTERNAL_GATED,
        missing_machine_fields=["last_progress_at"],
        metadata={"nested": {"refs": ["mutable-at-input"]}},
    )

    row = packet.to_dict()

    assert row["heartbeat_state"] == "running_by_heartbeat"
    assert row["progress_state"] == "stalled_by_artifact_progress"
    assert row["completion_state"] == "blocked_by_receipt"
    assert row["authority_state"] == "projection_only"
    assert row["mutation_state"] == "no_mutation_observed"
    assert row["external_state"] == "external_gated"
    assert row["proof_grade"] == "MISSING"
    assert packet.heartbeat_state is not packet.progress_state
    assert packet.is_projection is True
    assert packet.is_authoritative is False
    assert packet.receipt_refs == ("receipts/mission-1.json",)
    assert row["receipt_refs"] == ["receipts/mission-1.json"]
    assert row["missing_machine_fields"] == ["last_progress_at"]
    assert row["metadata"] == {"nested": {"refs": ["mutable-at-input"]}}

    try:
        packet.receipt_refs.append("receipts/late-mutation.json")  # type: ignore[attr-defined]
    except AttributeError:
        pass
    else:
        raise AssertionError("RuntimeTruthPacket ref fields must be immutable")

    try:
        packet.metadata["late"] = "mutation"
    except TypeError:
        pass
    else:
        raise AssertionError("RuntimeTruthPacket metadata must be immutable")

    try:
        RuntimeTruthPacket(
            surface_id="bad.authority",
            kind="bad_projection",
            observed_at="2026-06-04T00:00:00Z",
            owner_surface="tests",
            source_kind="fixture",
            is_authoritative=True,
        )
    except ValueError as exc:
        assert "authority lives in owner surfaces" in str(exc)
    else:
        raise AssertionError("RuntimeTruthPacket must reject authority claims")


def _write_runtime_truth_fixture(
    db_path: Path,
    *,
    receipt_type: str = "a2a_task",
    receipt_status: str = "completed",
    run_status: str = "completed",
    completed_at: str | None = "2026-06-04T01:05:00+00:00",
    stale_after: str = "2099-01-01T00:00:00+00:00",
    current_artifact_id: str = "artifact-1",
    include_artifact: bool = True,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE runtime_receipts (
                receipt_id TEXT PRIMARY KEY,
                receipt_type TEXT NOT NULL,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                trace_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                causation_id TEXT NOT NULL DEFAULT '',
                parent_run_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                idempotency_key TEXT NOT NULL DEFAULT '',
                side_effect_key TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE execution_identities (
                run_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                claim_id TEXT NOT NULL DEFAULT '',
                idempotency_key TEXT NOT NULL DEFAULT '',
                causation_id TEXT NOT NULL DEFAULT '',
                parent_run_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL DEFAULT '',
                session_id TEXT NOT NULL DEFAULT '',
                external_a2a_task_id TEXT NOT NULL DEFAULT '',
                message_id TEXT NOT NULL DEFAULT '',
                event_id TEXT NOT NULL DEFAULT '',
                artifact_id TEXT NOT NULL DEFAULT '',
                proposal_id TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE idempotency_records (
                idempotency_key TEXT NOT NULL,
                side_effect_key TEXT NOT NULL,
                run_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                trace_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                result_receipt_id TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (idempotency_key, side_effect_key)
            );
            CREATE TABLE task_claims (
                claim_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                session_id TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL,
                status TEXT NOT NULL,
                claimed_at TEXT NOT NULL,
                acked_at TEXT,
                heartbeat_at TEXT,
                stale_after TEXT,
                recovered_at TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                trace_id TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE delegation_runs (
                run_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL,
                claim_id TEXT NOT NULL DEFAULT '',
                parent_run_id TEXT NOT NULL DEFAULT '',
                assigned_by TEXT NOT NULL DEFAULT '',
                assigned_to TEXT NOT NULL,
                current_artifact_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                failure_code TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE artifact_records (
                artifact_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                run_id TEXT NOT NULL DEFAULT '',
                trace_id TEXT NOT NULL DEFAULT '',
                artifact_kind TEXT NOT NULL,
                manifest_path TEXT NOT NULL DEFAULT '',
                payload_path TEXT NOT NULL DEFAULT '',
                checksum TEXT NOT NULL DEFAULT '',
                parent_artifact_id TEXT NOT NULL DEFAULT '',
                promotion_state TEXT NOT NULL DEFAULT 'ephemeral',
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            """
        )
        conn.execute(
            "INSERT INTO runtime_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "receipt-1",
                receipt_type,
                "run-1",
                "task-1",
                "trace-1",
                "corr-1",
                "",
                "",
                "agent-1",
                "idem-1",
                "a2a.submit",
                receipt_status,
                '{"mission_id": "mission-1"}',
                "2026-06-04T01:04:00+00:00",
            ),
        )
        conn.execute(
            "INSERT INTO execution_identities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-1",
                "trace-1",
                "corr-1",
                "task-1",
                "claim-1",
                "idem-1",
                "",
                "",
                "agent-1",
                "session-1",
                "",
                "",
                "",
                "",
                "",
                '{"mission_id": "mission-1"}',
            ),
        )
        conn.execute(
            "INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "idem-1",
                "a2a.submit",
                "run-1",
                "task-1",
                "trace-1",
                "corr-1",
                "completed",
                "receipt-1",
                "{}",
                "2026-06-04T01:00:00+00:00",
                "2026-06-04T01:04:00+00:00",
            ),
        )
        conn.execute(
            "INSERT INTO task_claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "claim-1",
                "task-1",
                "session-1",
                "agent-1",
                "claimed",
                "2026-06-04T01:00:00+00:00",
                "2026-06-04T01:00:10+00:00",
                "2026-06-04T01:03:00+00:00",
                stale_after,
                None,
                0,
                "{}",
                "trace-1",
            ),
        )
        conn.execute(
            "INSERT INTO delegation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-1",
                "session-1",
                "task-1",
                "claim-1",
                "",
                "operator",
                "agent-1",
                current_artifact_id,
                run_status,
                "2026-06-04T01:00:00+00:00",
                completed_at,
                "",
                "{}",
            ),
        )
        if include_artifact:
            conn.execute(
                "INSERT INTO artifact_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "artifact-1",
                    "session-1",
                    "task-1",
                    "run-1",
                    "trace-1",
                    "handoff",
                    "artifacts/run-1/manifest.json",
                    "artifacts/run-1/result.md",
                    "sha256:test",
                    "",
                    "ephemeral",
                    "2026-06-04T01:05:00+00:00",
                    "{}",
                ),
            )
        conn.commit()


def test_runtime_truth_projector_reads_runtime_db_without_writing(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    _write_runtime_truth_fixture(db_path)
    before_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
    before_sidecars = sorted(path.name for path in tmp_path.glob("runtime.db*"))

    packets = runtime_truth_packets_from_runtime_db(
        db_path,
        observed_at="2026-06-04T01:06:00+00:00",
    )

    after_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
    after_sidecars = sorted(path.name for path in tmp_path.glob("runtime.db*"))
    latest = next(packet for packet in packets if packet.surface_id == "runtime_state.latest_receipt")
    summary = summarize_runtime_truth_packets(packets)

    assert before_hash == after_hash
    assert before_sidecars == after_sidecars == ["runtime.db"]
    assert latest.run_id == "run-1"
    assert latest.task_id == "task-1"
    assert latest.correlation_id == "corr-1"
    assert latest.mission_id == "mission-1"
    assert latest.receipt_refs == ("runtime_receipts:receipt-1",)
    assert latest.artifact_refs == ("artifact_records:artifact-1:artifacts/run-1/result.md",)
    assert "idempotency_records:idem-1:a2a.submit" in latest.source_refs
    assert latest.metadata["idempotency_record_ref"] == "idempotency_records:idem-1:a2a.submit"
    assert latest.metadata["idempotency_result_receipt_ref"] == "runtime_receipts:receipt-1"
    assert "idempotency_record" not in latest.missing_machine_fields
    assert latest.heartbeat_state is RuntimeTruthState.RUNNING_BY_HEARTBEAT
    assert latest.progress_state is RuntimeTruthState.PROGRESSING_BY_ARTIFACT
    assert latest.completion_state is RuntimeTruthState.COMPLETED_BY_RECEIPT
    assert latest.retry_state is RuntimeTruthState.RETRY_EQUIVALENT
    assert latest.is_authoritative is False
    assert summary["latest_receipt"] == "runtime_receipts:receipt-1"


def test_runtime_truth_projector_missing_db_does_not_create_file(tmp_path: Path) -> None:
    db_path = tmp_path / "missing-runtime.db"

    packets = runtime_truth_packets_from_runtime_db(
        db_path,
        observed_at="2026-06-04T01:06:00+00:00",
    )

    assert not db_path.exists()
    assert len(packets) == 1
    assert packets[0].surface_id == "runtime_state.store"
    assert packets[0].readiness_state is RuntimeTruthState.NOT_READY_BY_PROBE
    assert packets[0].missing_machine_fields == ("runtime_db",)


def test_runtime_truth_projector_malformed_db_is_not_ready(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE unrelated_state (id TEXT PRIMARY KEY)")
        conn.commit()
    before_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()

    packets = runtime_truth_packets_from_runtime_db(
        db_path,
        observed_at="2026-06-04T01:06:00+00:00",
    )

    after_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
    store = packets[0]
    assert before_hash == after_hash
    assert store.surface_id == "runtime_state.store"
    assert store.probe_ok is False
    assert store.readiness_state is RuntimeTruthState.NOT_READY_BY_PROBE
    assert "runtime_receipts_table" in store.missing_machine_fields
    assert "idempotency_records_table" in store.missing_machine_fields


def test_runtime_truth_projector_does_not_complete_from_nonterminal_receipt(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "runtime.db"
    _write_runtime_truth_fixture(
        db_path,
        receipt_type="provider_call",
        receipt_status="completed",
        run_status="running",
        completed_at=None,
        current_artifact_id="",
        include_artifact=False,
    )

    packets = runtime_truth_packets_from_runtime_db(
        db_path,
        observed_at="2026-06-04T01:06:00+00:00",
    )

    latest = next(packet for packet in packets if packet.surface_id == "runtime_state.latest_receipt")
    assert latest.completion_state is RuntimeTruthState.UNKNOWN


def test_runtime_truth_projector_stale_claim_dominates_artifact_progress(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "runtime.db"
    _write_runtime_truth_fixture(
        db_path,
        run_status="running",
        completed_at=None,
        stale_after="2000-01-01T00:00:00+00:00",
    )

    packets = runtime_truth_packets_from_runtime_db(
        db_path,
        observed_at="2026-06-04T01:06:00+00:00",
    )

    latest = next(packet for packet in packets if packet.surface_id == "runtime_state.latest_receipt")
    assert latest.heartbeat_state is RuntimeTruthState.STALLED_BY_ARTIFACT_PROGRESS
    assert latest.progress_state is RuntimeTruthState.STALLED_BY_ARTIFACT_PROGRESS
    assert latest.completion_state is RuntimeTruthState.UNKNOWN
