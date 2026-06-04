from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.operator_core.control_surface_models import ControlSurfaceRow
from dharma_swarm.operator_core.control_surface_proposals import (
    emit_proposal_packets,
    pr_merge_proposal_for_row,
    proposal_for_row,
    proposal_packets_for_rows,
)


FIXED_NOW = "2026-06-04T00:00:00+00:00"


def _runtime_row() -> ControlSurfaceRow:
    row = ControlSurfaceRow(
        id="live_ops.nats",
        kind="fleet",
        label="NATS substrate",
        authority_role="observed_authority",
        declared_state="live",
        desired_state="live",
        observed_state="degraded",
        coherence_state="drifted",
        priority="p0",
        owner_module="scripts/runtime/live_ops_census.py",
        truth_owner="live_ops_census",
        gap_codes=["human_authority_required", "authority_tier:direct_probe"],
        next_action="operator-approved restart after ack receipt inspection",
        human_decision_required=True,
        raw={"risk": "high"},
    )
    row.add_source_ref("file", "scripts/runtime/live_ops_census.py", exists=True)
    row.add_evidence("process", "nats port open only", status="degraded", provenance_chain=["live_ops_census", "nats"])
    return row


def _pr_row(**raw) -> ControlSurfaceRow:
    defaults = {
        "pr_number": 446,
        "head_sha": "abc123",
        "queue_status": "GITHUB_GREEN_NEEDS_PACKET",
        "gate_decision": "",
        "blockers": [],
        "review_receipts": [],
        "risk": "medium",
    }
    defaults.update(raw)
    row = ControlSurfaceRow(
        id=f"pr.#{defaults['pr_number']}",
        kind="pr_queue",
        label=f"PR #{defaults['pr_number']}",
        authority_role="observed_authority",
        declared_state="receipt-backed-pr-queue",
        desired_state="operator-reviewed",
        observed_state="merge_ready_needs_packet",
        coherence_state="partial",
        priority="p1",
        owner_module="scripts/runtime/pr_merge_control.py",
        truth_owner="pr_merge_control_queue_receipt",
        gap_codes=["pr_queue_status:GITHUB_GREEN_NEEDS_PACKET"],
        next_action="run make pr-packet and merge gate before any merge decision",
        raw=defaults,
    )
    row.add_source_ref("file", "scripts/runtime/pr_merge_control.py", exists=True)
    row.add_evidence("file", "~/.dharma/pr_review/queue/latest.json", status="fresh")
    return row


def test_runtime_proposal_packet_is_typed_draft_and_preserves_refs() -> None:
    packet = proposal_for_row(_runtime_row(), created_at=FIXED_NOW)

    assert packet.kind == "runtime_restart_proposal"
    assert packet.status == "draft"
    assert packet.forbidden_inline_execution is True
    assert packet.authority_required == "operator_explicit_confirmation"
    assert packet.operator_confirmation_token.startswith("CONFIRM_OPERATOR_ONLY::")
    assert packet.risk == "high"
    assert packet.source_refs[0]["path"] == "scripts/runtime/live_ops_census.py"
    assert packet.evidence_refs[0]["source"] == "nats port open only"
    assert "restart" in packet.proposed_command_text


def test_proposal_generation_is_pure_until_explicit_write(tmp_path: Path) -> None:
    packets = proposal_packets_for_rows([_runtime_row(), _pr_row()], created_at=FIXED_NOW)

    dry_result = emit_proposal_packets(packets, output_dir=tmp_path, write=False)

    assert len(packets) == 2
    assert dry_result.written_paths == []
    assert list(tmp_path.iterdir()) == []

    write_result = emit_proposal_packets(packets, output_dir=tmp_path, write=True)

    assert len(write_result.written_paths) == 2
    assert all(path.exists() for path in write_result.written_paths)


def test_pr_packet_proposal_contains_pr_lineage_fields() -> None:
    packet = proposal_for_row(_pr_row(), created_at=FIXED_NOW)

    assert packet.kind == "pr_packet_proposal"
    assert packet.pr_number == 446
    assert packet.head_sha == "abc123"
    assert packet.queue_status == "GITHUB_GREEN_NEEDS_PACKET"
    assert packet.forbidden_inline_execution is True
    assert packet.external_execution_eligible is False
    assert packet.source_refs[0]["path"] == "scripts/runtime/pr_merge_control.py"
    assert packet.evidence_refs[0]["source"] == "~/.dharma/pr_review/queue/latest.json"


def test_pr_merge_proposal_cannot_be_external_eligible_without_gate_receipts() -> None:
    with pytest.raises(ValueError, match="not externally execution-eligible"):
        pr_merge_proposal_for_row(_pr_row(gate_decision="PASS", review_receipts=[]), allow_external_execution=True)


def test_pr_merge_proposal_external_eligibility_requires_gate_head_reviews_and_human_authority() -> None:
    packet = pr_merge_proposal_for_row(
        _pr_row(
            gate_decision="PASS",
            review_receipts=["codex_review.md", "claude_review.md"],
            human_authority_explicit=True,
            risk="high",
        ),
        created_at=FIXED_NOW,
        allow_external_execution=True,
    )

    assert packet.kind == "pr_merge_proposal"
    assert packet.external_execution_eligible is True
    assert packet.forbidden_inline_execution is True
    assert packet.gate_decision == "PASS"
    assert packet.head_sha == "abc123"
    assert packet.review_receipts == ["codex_review.md", "claude_review.md"]


def test_proposal_module_has_no_mutation_substrate_imports() -> None:
    source = Path("dharma_swarm/operator_core/control_surface_proposals.py").read_text(encoding="utf-8")

    forbidden = [
        "subprocess",
        "requests",
        "urllib",
        "socket",
        "gh pr merge",
        "gh pr close",
        "pkill",
        "kill ",
        "nats",
    ]
    for token in forbidden:
        assert token not in source
