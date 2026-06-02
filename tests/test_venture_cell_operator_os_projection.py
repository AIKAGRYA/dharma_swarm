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
    MEMORY_KERNEL_EVAL_QUERIES,
    OperatorOSInputs,
    build_operator_projection,
    build_memory_kernel_index,
    evaluate_memory_kernel_queries,
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


def _write_memory_source_packet(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "memory-source.md"
    path.write_text(
        "# VentureCell Operator OS Memory Source\n"
        "Polsia Cofounder VentureCell Operator OS context maps the company "
        "workspace to Dharma governance.\n"
        "Darshan external reader gate Go evidence receipt requires accepted "
        "source_url and event_uid fields before growth or communications act.\n"
        "Cofounder Canvas Library Plan Execute publishing remains read-only "
        "until review gates pass.\n"
        "Chetana wiki MemoryKernel distinguishes staged trusted quarantine "
        "tiers without trusted promotion claims.\n"
        "VentureCell autonomy ladder blocks external action approval until "
        "governed evidence exists.\n",
        encoding="utf-8",
    )
    return path


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
    assert projection.next_action_packet.decision == "hold_external_authority"
    assert projection.next_action_packet.owner_department == "growth"
    assert projection.next_action_packet.blocked_departments == (
        "growth",
        "communications",
    )
    assert "darshan_external_reader_event_missing" in projection.next_action_packet.blockers
    assert "external-reader Go evidence receipt" in (
        projection.next_action_packet.required_unblock_artifact
    )
    assert "live_external_authority" in projection.next_action_packet.forbidden_actions
    authority = projection.authority_boundary_packet
    assert authority.decision == "local_read_only_external_blocked"
    assert "render_operator_os" in authority.allowed_local_actions
    assert "live_external_authority" in authority.blocked_actions
    assert "push" in authority.blocked_actions
    assert authority.liveness_claims["operator_os_nats_action_ack_proof_present"] is False
    assert authority.liveness_claims["operator_os_a2a_live_action_ack_proof_present"] is False
    assert authority.liveness_claims["filesystem_a2a_rows_are_evidence_only"] is True
    assert authority.promotion_claims["trusted_chetana_promotion_claimed"] is False
    triage = projection.gap_triage_packet
    assert triage.decision == "external_blocked_with_local_followups"
    assert "darshan_external_reader_event_missing" in triage.external_authority_required_gaps
    assert "memory_kernel_query_eval_partial" in triage.locally_actionable_gaps
    assert triage.not_authority is True
    assert "fake_go_receipt_creation" in triage.forbidden_actions
    repair = projection.memory_kernel_repair_packet
    assert repair.decision == "queue_repair_without_promotion"
    assert repair.status == "queued"
    assert repair.query_eval_status == "partial"
    assert repair.query_eval_total == len(MEMORY_KERNEL_EVAL_QUERIES)
    assert repair.repair_items
    assert "trusted_chetana_promotion" in repair.forbidden_actions
    assert repair.raw["trusted_promotion_claimed"] is False
    go_gate = projection.darshan_go_gate_packet
    assert go_gate.decision == "block_external_authority"
    assert go_gate.required_receipt_source == "darshan_external_reader"
    assert go_gate.required_receipt_schema == "go_evidence_receipt.v0"
    assert "source_url" in go_gate.required_receipt_fields
    assert "payload.privacy_redacted" in go_gate.required_receipt_fields
    assert go_gate.blocked_departments == ("growth", "communications")
    assert "external_outreach" in go_gate.blocked_actions
    assert "decision_delta.json" in " ".join(go_gate.expected_local_artifacts)
    assert go_gate.receipt_template["template_status"] == "draft_template_not_evidence"
    assert go_gate.receipt_template["not_receipt"] is True
    assert go_gate.receipt_template["receipt"]["status"] == "template_only_not_accepted"
    assert "do_not_use_as_go_gate_evidence" in go_gate.receipt_template["forbidden_use"]
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
    assert projection.darshan_go_gate_packet.decision == "gate_passed_reviewed_internal_only"
    assert projection.darshan_go_gate_packet.accepted_receipts == ("goev_reply_001",)
    assert projection.darshan_go_gate_packet.blocked_actions == ()


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
    assert "## Authority Boundary" in digest
    assert "local_read_only_external_blocked" in digest
    assert "## Darshan GO Gate" in digest
    assert "block_external_authority" in digest
    assert "draft_template_not_evidence" in digest
    assert "## Next Action Packet" in digest
    assert "hold_external_authority" in digest
    assert "## Gap Triage" in digest
    assert "external_blocked_with_local_followups" in digest
    assert "## Memory Kernel" in digest
    assert "## Memory Repair Packet" in digest
    assert "queue_repair_without_promotion" in digest
    assert "`L0_read_only_plan`" in digest
    assert "autonomous external send" not in digest.lower()


def test_operator_daily_digest_caps_repeated_canvas_lane_details(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    a2a_rows = tuple(
        {
            "id": f"a2a-{index}",
            "from": "planner",
            "to": "codex",
            "status": "pending",
            "body": f"Repeated canvas row {index}",
        }
        for index in range(12)
    )

    projection = build_operator_projection(
        OperatorOSInputs(
            bundle_path=bundle,
            a2a_tasks=a2a_rows,
            trusted_root=tmp_path / "trusted",
            staging_root=tmp_path / "staging",
            quarantine_root=tmp_path / "quarantine",
        )
    )

    digest = render_operator_daily_digest(projection)

    assert len([item for item in projection.canvas if item.lane == "a2a_queue"]) == 12
    assert "Repeated canvas row 0" in digest
    assert "Repeated canvas row 7" in digest
    assert "Repeated canvas row 8" not in digest
    assert "`a2a_queue` omitted items: `4` of `12` total." in digest


def test_operator_surface_renderer_writes_projection_digest_and_memory_index(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    state_root = tmp_path / "state"
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    (report_dir / "00_opening_truth.md").write_text(
        "# Opening Truth\n",
        encoding="utf-8",
    )
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
        output_dir=report_dir,
        bundle_path=bundle,
        state_root=state_root,
        max_memory_scan=1,
    )

    projection = json.loads(paths["projection"].read_text(encoding="utf-8"))
    digest = paths["digest"].read_text(encoding="utf-8")
    memory_index = json.loads(paths["memory_index"].read_text(encoding="utf-8"))
    memory_coverage_packet = json.loads(
        paths["memory_coverage_packet"].read_text(encoding="utf-8")
    )
    memory_query_eval = json.loads(
        paths["memory_query_eval"].read_text(encoding="utf-8")
    )
    next_action_packet = json.loads(
        paths["next_action_packet"].read_text(encoding="utf-8")
    )
    go_gate_packet = json.loads(
        paths["darshan_go_gate_packet"].read_text(encoding="utf-8")
    )
    go_receipt_template = json.loads(
        paths["darshan_go_receipt_template"].read_text(encoding="utf-8")
    )
    memory_repair_packet = json.loads(
        paths["memory_kernel_repair_packet"].read_text(encoding="utf-8")
    )
    authority_boundary_packet = json.loads(
        paths["authority_boundary_packet"].read_text(encoding="utf-8")
    )
    gap_triage_packet = json.loads(
        paths["gap_triage_packet"].read_text(encoding="utf-8")
    )
    artifact_manifest = json.loads(
        paths["artifact_manifest"].read_text(encoding="utf-8")
    )

    assert projection["status"] == "blocked_on_external_reader_gate"
    assert projection["autonomy_level"] == "L0_read_only_plan"
    assert projection["next_action_packet"]["decision"] == "hold_external_authority"
    assert projection["darshan_go_gate_packet"]["decision"] == "block_external_authority"
    assert "# VentureCell Operator OS Digest: DARSHAN" in digest
    assert "index_status" in memory_index
    assert "root_coverage" in memory_index
    assert memory_coverage_packet["schema"] == "dharma.venture_cell_operator_os.memory_coverage.v0"
    assert memory_coverage_packet["not_authority"] is True
    assert memory_coverage_packet["trusted_promotion_claimed"] is False
    assert memory_coverage_packet["root_coverage"]
    assert "query_eval_status" in memory_index
    assert "query_eval_results" in memory_query_eval
    assert memory_query_eval["trusted_promotion_claimed"] is False
    assert next_action_packet["decision"] == "hold_external_authority"
    assert next_action_packet["blocked_departments"] == ["growth", "communications"]
    assert "live_external_authority" in next_action_packet["forbidden_actions"]
    assert go_gate_packet["required_receipt_source"] == "darshan_external_reader"
    assert "payload.privacy_redacted" in go_gate_packet["required_receipt_fields"]
    assert "publishing" in go_gate_packet["blocked_actions"]
    assert go_receipt_template["template_status"] == "draft_template_not_evidence"
    assert go_receipt_template["not_receipt"] is True
    assert go_receipt_template["receipt"]["status"] == "template_only_not_accepted"
    assert go_receipt_template["receipt"]["source"] == "darshan_external_reader"
    assert "do_not_store_as_accepted_receipt_without_real_event" in go_receipt_template["forbidden_use"]
    assert memory_repair_packet["decision"] == "queue_repair_without_promotion"
    assert memory_repair_packet["status"] == "queued"
    assert memory_repair_packet["raw"]["trusted_promotion_claimed"] is False
    assert "trusted_chetana_promotion" in memory_repair_packet["forbidden_actions"]
    assert authority_boundary_packet["decision"] == "local_read_only_external_blocked"
    assert authority_boundary_packet["liveness_claims"]["operator_os_nats_action_ack_proof_present"] is False
    assert authority_boundary_packet["liveness_claims"]["operator_os_a2a_live_action_ack_proof_present"] is False
    assert authority_boundary_packet["promotion_claims"]["trusted_chetana_promotion_claimed"] is False
    assert gap_triage_packet["decision"] == "external_blocked_with_local_followups"
    assert "darshan_external_reader_event_missing" in gap_triage_packet["external_authority_required_gaps"]
    assert "memory_kernel_index_truncated" in gap_triage_packet["locally_actionable_gaps"]
    assert gap_triage_packet["not_authority"] is True
    assert "fake_go_receipt_creation" in gap_triage_packet["forbidden_actions"]
    assert artifact_manifest["schema"] == "dharma.venture_cell_operator_os.render_manifest.v0"
    assert artifact_manifest["status"] == "blocked_on_external_reader_gate"
    assert artifact_manifest["darshan_go_decision"] == "block_external_authority"
    assert artifact_manifest["authority_decision"] == "local_read_only_external_blocked"
    assert artifact_manifest["gap_triage_decision"] == "external_blocked_with_local_followups"
    assert "memory_coverage_truncated" in artifact_manifest
    assert artifact_manifest["not_authority"] is True
    assert "projection" in artifact_manifest["artifact_paths"]
    assert "authority_boundary_packet" in artifact_manifest["artifact_paths"]
    assert "gap_triage_packet" in artifact_manifest["artifact_paths"]
    assert "memory_coverage_packet" in artifact_manifest["artifact_paths"]
    assert str(report_dir / "00_opening_truth.md") in artifact_manifest["receipt_paths"]
    assert str(report_dir / "operator_os_digest.md") not in artifact_manifest["receipt_paths"]


def test_operator_surface_uses_report_local_memory_source_without_trusted_promotion(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    report_dir = tmp_path / "reports"
    source = _write_memory_source_packet(report_dir)

    paths = render_operator_surface(
        output_dir=report_dir,
        bundle_path=bundle,
        state_root=tmp_path / "state",
        max_memory_scan=20,
    )

    memory_index = json.loads(paths["memory_index"].read_text(encoding="utf-8"))
    memory_query_eval = json.loads(
        paths["memory_query_eval"].read_text(encoding="utf-8")
    )
    memory_repair_packet = json.loads(
        paths["memory_kernel_repair_packet"].read_text(encoding="utf-8")
    )

    assert str(report_dir) in memory_index["source_roots"]
    assert any(entry["path"] == str(source) for entry in memory_index["index_entries"])
    assert memory_query_eval["query_eval_status"] == "pass"
    assert memory_query_eval["query_eval_passed"] == len(MEMORY_KERNEL_EVAL_QUERIES)
    assert memory_query_eval["trusted_promotion_claimed"] is False
    assert memory_repair_packet["decision"] == "no_repair_needed"
    assert "claim_memory_eval_pass" not in memory_repair_packet["forbidden_actions"]
    assert "trusted_chetana_promotion" in memory_repair_packet["forbidden_actions"]
    assert memory_repair_packet["raw"]["trusted_promotion_claimed"] is False


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
    (staged / "venturecell-autonomy.md").write_text(
        "# VentureCell Autonomy Ladder\n"
        "VentureCell autonomy ladder keeps external action approval blocked "
        "until governed evidence exists.",
        encoding="utf-8",
    )
    (trusted / "memory-kernel.md").write_text(
        "# Chetana Memory Kernel\n"
        "Chetana wiki memory kernel distinguishes staged trusted quarantine tiers.",
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
    coverage_by_role = {coverage["role"]: coverage for coverage in index.root_coverage}
    assert coverage_by_role["trusted"]["scanned_count"] == 2
    assert coverage_by_role["staging"]["scanned_count"] == 2
    assert coverage_by_role["quarantine"]["scanned_count"] == 1
    assert coverage_by_role["staging"]["truncated"] is False

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

    untrusted_only = index.query("Polsia raw untrusted company claim", trusted_only=True)
    assert untrusted_only.status == "trusted_missing"
    assert "only_untrusted_matches_available" in untrusted_only.notes

    evals = evaluate_memory_kernel_queries(index)
    assert len(evals) == len(MEMORY_KERNEL_EVAL_QUERIES)
    assert all(result.passed for result in evals)
    assert all(result.source_refs for result in evals)
    assert all(result.trusted_promotion_claimed is False for result in evals)


def test_memory_kernel_root_coverage_marks_truncated_roots(tmp_path: Path) -> None:
    trusted = tmp_path / "trusted"
    staged = tmp_path / "staging"
    quarantine = tmp_path / "quarantine"
    trusted.mkdir()
    staged.mkdir()
    quarantine.mkdir()
    (trusted / "operator-os.md").write_text("# Operator OS\n", encoding="utf-8")
    (staged / "first.md").write_text("# Darshan\nGo evidence receipt\n", encoding="utf-8")
    (staged / "second.md").write_text("# MemoryKernel\nChetana staged source\n", encoding="utf-8")
    (quarantine / "raw.md").write_text("# Raw\n", encoding="utf-8")

    index = build_memory_kernel_index(
        staging_root=staged,
        trusted_root=trusted,
        quarantine_root=quarantine,
        max_scan=1,
        max_entries=6,
    )

    coverage_by_role = {coverage["role"]: coverage for coverage in index.root_coverage}

    assert index.truncated is True
    assert coverage_by_role["trusted"]["truncated"] is True
    assert coverage_by_role["staging"]["truncated"] is True
    assert coverage_by_role["quarantine"]["truncated"] is True
    assert coverage_by_role["staging"]["scanned_count"] == 1
    assert coverage_by_role["staging"]["indexed_count"] <= coverage_by_role["staging"]["entry_budget"]
