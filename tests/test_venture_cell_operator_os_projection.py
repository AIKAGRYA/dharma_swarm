from __future__ import annotations

import asyncio
import json
from pathlib import Path

from dharma_swarm.models import TaskPriority, TaskStatus
from dharma_swarm.task_board import Task, TaskBoard
from dharma_swarm.venture_cell.darshan.bundle import create_bundle
from dharma_swarm.venture_cell.darshan.schema import (
    DecisionDelta,
    ExternalReaderEvent,
    GoEvidenceReceiptRef,
)
from dharma_swarm.venture_cell.operator_os import (
    OperatorOSInputs,
    build_operator_projection,
    build_memory_kernel_index,
    load_live_operator_inputs,
    query_memory_kernel_index,
    render_operator_daily_digest,
)
from dharma_swarm.venture_cell.operator_os.cli import render_operator_surface


OBSERVED_AT = "2026-06-02T00:00:00Z"


def _bundle(tmp_path: Path, artifact_id: str = "darshan-artifact-001") -> Path:
    return create_bundle(
        title="Operator OS Fixture",
        root=tmp_path / "artifacts",
        artifact_id=artifact_id,
        overwrite=True,
    )


def _receipt(path: Path, *, artifact_id: str = "darshan-artifact-001") -> Path:
    raw = {
        "receipt_id": "goev_reply_001",
        "correlation_id": artifact_id,
        "source": "darshan_external_reader",
        "source_url": "fixture://darshan/external-reader/reply-001",
        "observed_at": OBSERVED_AT,
        "content_hash": "sha256:reply",
        "event_uid": "evt_reply_001",
        "schema_version": "go_evidence_receipt.v0",
        "status": "accepted",
        "payload": {
            "artifact_id": artifact_id,
            "event_type": "reply",
            "reader_label": "external_reader_001",
            "contact_surface": "email",
            "summary": "Reader replied with substantive inspection.",
            "human_approved_contact": True,
            "privacy_redacted": True,
            "consent_public": False,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _attach_reader_event(bundle_path: Path, receipt_path: Path) -> None:
    decision_path = bundle_path / "decision_delta.json"
    decision = DecisionDelta.model_validate(json.loads(decision_path.read_text()))
    event = ExternalReaderEvent(
        artifact_id=decision.artifact_id,
        event_type="reply",
        reader_label="external_reader_001",
        contact_surface="email",
        summary="Reader replied with substantive inspection.",
        human_approved_contact=True,
        go_receipt=GoEvidenceReceiptRef(
            receipt_path=str(receipt_path),
            receipt_id="goev_reply_001",
            source="darshan_external_reader",
            source_url="fixture://darshan/external-reader/reply-001",
            observed_at=OBSERVED_AT,
            content_hash="sha256:reply",
            event_uid="evt_reply_001",
            status="accepted",
        ),
    )
    updated = decision.model_copy(update={"external_reader_events": [event]})
    decision_path.write_text(
        json.dumps(updated.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_a2a_queue(state_root: Path, rows: list[dict[str, object]]) -> None:
    queue = state_root / "a2a_bus" / "tasks" / "queue.jsonl"
    queue.parent.mkdir(parents=True)
    queue.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


async def _seed_task_board(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True)
    board = TaskBoard(db_path)
    await board.init_db()
    await board.create(
        "Operator OS live task",
        priority=TaskPriority.NORMAL,
        created_by="venturecell_operator_os_test",
        metadata={"cell_id": "DARSHAN"},
    )


def test_projection_blocks_external_autonomy_without_reader_gate(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    trusted = tmp_path / "wiki" / "concepts"
    trusted.mkdir(parents=True)
    (trusted / "operator-os.md").write_text("# Operator OS\n", encoding="utf-8")

    projection = build_operator_projection(
        OperatorOSInputs(
            bundle_path=bundle,
            trusted_root=trusted,
            staging_root=tmp_path / "staging",
            quarantine_root=tmp_path / "quarantine",
        )
    )

    assert projection.status == "blocked_on_external_reader_gate"
    assert projection.autonomy_level == "L0_read_only_plan"
    assert len(projection.departments) >= 8
    assert "darshan_external_reader_event_missing" in projection.gap_codes
    assert any(
        dept.department_id == "growth" and dept.status == "blocked_on_external_reader_gate"
        for dept in projection.departments
    )
    assert any(item.item_id == "darshan.article.md" and item.status == "available" for item in projection.canvas)


def test_live_loader_reads_injected_taskboard_and_a2a_state(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    task_db = state_root / "db" / "tasks.db"
    asyncio.run(_seed_task_board(task_db))
    _write_a2a_queue(
        state_root,
        [
            {
                "id": "a2a-live-1",
                "from": "mission_control",
                "to": "codex",
                "status": "claimed",
                "body": "Render Operator OS live projection",
            }
        ],
    )

    inputs = load_live_operator_inputs(
        state_root=state_root,
        task_db_path=task_db,
        max_memory_scan=1,
    )

    assert len(inputs.task_board_tasks) == 1
    assert inputs.task_board_tasks[0].title == "Operator OS live task"
    assert inputs.a2a_tasks is not None
    assert inputs.a2a_tasks[0]["id"] == "a2a-live-1"


def test_projection_maps_reader_gate_taskboard_a2a_and_memory(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    receipt = _receipt(bundle / "receipts" / "reader.json")
    _attach_reader_event(bundle, receipt)
    trusted = tmp_path / "wiki" / "concepts"
    staging = tmp_path / "staging" / "2026-06-02"
    trusted.mkdir(parents=True)
    staging.mkdir(parents=True)
    (trusted / "operator-os.md").write_text("# Operator OS\n", encoding="utf-8")
    (staging / "raw-research.md").write_text("# Raw research\n", encoding="utf-8")
    task = Task(
        id="task-1",
        title="Build Operator OS projection",
        status=TaskStatus.RUNNING,
        priority=TaskPriority.NORMAL,
        created_by="darshan_venture_cell",
    )

    projection = build_operator_projection(
        OperatorOSInputs(
            bundle_path=bundle,
            task_board_tasks=(task,),
            a2a_tasks=(
                {
                    "id": "a2a-1",
                    "from": "planner",
                    "to": "codex",
                    "status": "claimed",
                    "body": "Wire the projection",
                },
            ),
            trusted_root=trusted,
            staging_root=tmp_path / "staging",
            quarantine_root=tmp_path / "quarantine",
        )
    )

    assert projection.status == "ready_for_reviewed_internal_execution"
    assert projection.autonomy_level == "L1_reviewed_internal_only"
    assert projection.memory_kernel.status == "projection_available"
    assert projection.memory_kernel.staged_count == 1
    assert projection.memory_kernel.trusted_count == 1
    assert projection.memory_kernel.index_status == "available"
    assert projection.memory_kernel.indexed_count >= 2
    assert any(
        gate.gate_id == "darshan.external_reader_go_receipts" and gate.decision == "allow"
        for gate in projection.gates
    )
    assert any(item.item_id == "task_board.task-1" and item.status == "running" for item in projection.canvas)
    assert any(item.item_id == "a2a.a2a-1" and item.status == "claimed_open" for item in projection.canvas)


def test_operator_daily_digest_renders_structure_without_live_authority_claim(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    projection = build_operator_projection(
        OperatorOSInputs(
            bundle_path=bundle,
            trusted_root=tmp_path / "trusted",
            staging_root=tmp_path / "staging",
            quarantine_root=tmp_path / "quarantine",
        )
    )

    digest = render_operator_daily_digest(projection)

    assert "# VentureCell Operator OS Digest: DARSHAN" in digest
    assert "## Departments" in digest
    assert "## Gates" in digest
    assert "## Memory Kernel" in digest
    assert "`L0_read_only_plan`" in digest
    assert "autonomous external send" not in digest.lower()


def test_operator_surface_renderer_writes_projection_digest_and_memory_index(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    state_root = tmp_path / "state"
    _write_a2a_queue(
        state_root,
        [
            {
                "id": "a2a-render-1",
                "from": "planner",
                "to": "codex",
                "status": "pending",
                "body": "Write local Operator OS digest",
            }
        ],
    )

    paths = render_operator_surface(
        output_dir=tmp_path / "reports",
        bundle_path=bundle,
        state_root=state_root,
        max_memory_scan=1,
    )

    projection = json.loads(paths["projection"].read_text(encoding="utf-8"))
    digest = paths["digest"].read_text(encoding="utf-8")
    memory_index = json.loads(paths["memory_index"].read_text(encoding="utf-8"))

    assert projection["status"] == "blocked_on_external_reader_gate"
    assert projection["autonomy_level"] == "L0_read_only_plan"
    assert "# VentureCell Operator OS Digest: DARSHAN" in digest
    assert "index_status" in memory_index


def test_memory_kernel_query_eval_distinguishes_tiers_and_provenance(tmp_path: Path) -> None:
    trusted = tmp_path / "wiki" / "concepts"
    staged = tmp_path / "staging"
    quarantine = tmp_path / "quarantine"
    trusted.mkdir(parents=True)
    staged.mkdir(parents=True)
    quarantine.mkdir(parents=True)
    (trusted / "operator-os.md").write_text(
        "# Operator OS\n"
        "Cofounder Canvas Library Plan Execute publishing mapped to Dharma Swarm Operator OS.",
        encoding="utf-8",
    )
    (staged / "darshan-go.md").write_text(
        "# Darshan Go Gate\n"
        "Darshan external reader gate requires an accepted Go evidence receipt "
        "with source_url and event_uid.",
        encoding="utf-8",
    )
    (quarantine / "polsia-raw.md").write_text(
        "# Polsia Raw Note\n"
        "Untrusted Polsia operator company claim kept in quarantine until provenance review.",
        encoding="utf-8",
    )

    index = build_memory_kernel_index(
        staging_root=staged,
        trusted_root=trusted,
        quarantine_root=quarantine,
        max_scan=20,
        max_entries=6,
        query_terms=(
            "Polsia",
            "Cofounder",
            "Darshan",
            "external reader",
            "Go evidence receipt",
            "MemoryKernel",
        ),
    )

    assert {entry.tier for entry in index.entries} == {"trusted", "staged", "quarantine"}

    gate_result = query_memory_kernel_index(
        index,
        "Darshan external reader gate Go evidence receipt",
    )
    assert gate_result.status == "available"
    assert gate_result.trusted_promotion_claimed is False
    assert gate_result.matches[0].tier == "staged"
    assert "source_url" in gate_result.matches[0].excerpt
    assert gate_result.source_roots

    trusted_result = index.query(
        "Cofounder Canvas Library Plan Execute publishing",
        trusted_only=True,
    )
    assert trusted_result.status == "available"
    assert trusted_result.tier_counts["trusted"] == 1
    assert all(match.tier == "trusted" for match in trusted_result.matches)

    untrusted_only = index.query("Polsia quarantine provenance review", trusted_only=True)
    assert untrusted_only.status == "trusted_missing"
    assert "only_untrusted_matches_available" in untrusted_only.notes
