from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.models import TaskPriority, TaskStatus
from dharma_swarm.task_board import Task
from dharma_swarm.venture_cell.darshan.bundle import create_bundle
from dharma_swarm.venture_cell.darshan.schema import (
    DecisionDelta,
    ExternalReaderEvent,
    GoEvidenceReceiptRef,
)
from dharma_swarm.venture_cell.operator_os import (
    OperatorOSInputs,
    build_operator_projection,
    render_operator_daily_digest,
)


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
    assert any(dept.department_id == "growth" and dept.status == "blocked_on_external_reader_gate" for dept in projection.departments)
    assert any(item.item_id == "darshan.article.md" and item.status == "available" for item in projection.canvas)


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
    assert any(gate.gate_id == "darshan.external_reader_go_receipts" and gate.decision == "allow" for gate in projection.gates)
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
    assert "`L0_read_only_plan`" in digest
    assert "autonomous external send" not in digest.lower()
