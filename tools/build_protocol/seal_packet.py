"""Shape-only ReviewPacket and ProofPacket helpers for build protocol work."""

from __future__ import annotations

from typing import Any

from dharma_swarm.runtime_contract import RuntimeEnvelope, RuntimeEventType


def seal_packet(
    *,
    build_packet_id: str,
    work_packet_id: str,
    session_id: str,
    reviewer_agent: str,
    builder_agent: str,
    diff_ref: str,
    test_output_ref: str,
    diff_summary: dict[str, int],
    gate_results: dict[str, dict[str, str]],
    findings: list[dict[str, Any]] | None = None,
    decision: str = "pass",
    reason: str = "WorkPacket passed review and proof seal.",
) -> dict[str, dict[str, Any]]:
    """Return ReviewPacket-shaped and ProofPacket RuntimeEnvelope JSON."""
    checkpoint_id = f"review_{work_packet_id}"
    findings = findings or []
    review_status = {"pass": "approved", "reject": "rejected", "fixup": "draft"}[decision]
    merge_decision = "seal" if decision == "pass" else "hold"
    proof_result = "pass" if decision == "pass" else "hold"
    review_packet = {
        "checkpoint_id": checkpoint_id,
        "session_id": session_id,
        "task_id": work_packet_id,
        "run_id": "",
        "status": review_status,
        "summary": reason,
        "artifact_refs": [diff_ref, test_output_ref],
        "metadata": {
            "kind": "review_packet",
            "protocol_version": "v0",
            "work_packet_id": work_packet_id,
            "reviewer_agent": reviewer_agent,
            "builder_agent": builder_agent,
            "diff_ref": diff_ref,
            "gate_results": gate_results,
            "findings": findings,
            "decision": decision,
        },
    }
    proof_payload = {
        "build_packet_id": build_packet_id,
        "work_packet_id": work_packet_id,
        "gate": "proof_seal",
        "result": proof_result,
        "reason": reason,
        "gate_results_aggregate": _aggregate_gates(gate_results),
        "test_outputs_ref": test_output_ref,
        "diff_summary": diff_summary,
        "signed_by": [reviewer_agent],
        "witness_log_ref": "",
        "child_checkpoint_ids": [checkpoint_id],
        "merge_decision": merge_decision,
    }
    proof_packet = RuntimeEnvelope.create(
        event_type=RuntimeEventType.AUDIT_EVENT,
        source="sovereign-build-packet-protocol-v0",
        agent_id=reviewer_agent,
        session_id=session_id,
        payload=proof_payload,
    ).as_dict()
    return {"review_packet": review_packet, "proof_packet": proof_packet}


def _aggregate_gates(gate_results: dict[str, dict[str, str]]) -> dict[str, dict[str, int]]:
    aggregate: dict[str, dict[str, int]] = {}
    for gate, record in gate_results.items():
        result = record.get("result", "hold")
        aggregate[gate] = {
            "pass_count": 1 if result == "pass" else 0,
            "fail_count": 1 if result == "fail" else 0,
            "hold_count": 1 if result == "hold" else 0,
        }
    return aggregate
