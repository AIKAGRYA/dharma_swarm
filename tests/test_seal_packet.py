from __future__ import annotations

from dharma_swarm.runtime_contract import validate_envelope
from tools.build_protocol.seal_packet import seal_packet


def test_seal_packet_emits_review_and_valid_proof_packet() -> None:
    sealed = seal_packet(
        build_packet_id="build_1",
        work_packet_id="wp_001",
        session_id="session_1",
        reviewer_agent="reviewer",
        builder_agent="builder",
        diff_ref="diff.patch",
        test_output_ref="test_output.txt",
        diff_summary={"files": 1, "added": 2, "removed": 0},
        gate_results={"scoped_tests": {"result": "pass", "reason": "ok", "evidence": "pytest"}},
    )

    review = sealed["review_packet"]
    proof = sealed["proof_packet"]
    assert review["status"] == "approved"
    assert review["metadata"]["kind"] == "review_packet"
    assert proof["event_type"] == "audit.event"
    assert proof["payload"]["merge_decision"] == "seal"
    assert validate_envelope(proof) == (True, [])


def test_rejected_packet_holds_proof_and_counts_failed_gate() -> None:
    sealed = seal_packet(
        build_packet_id="build_1",
        work_packet_id="wp_002",
        session_id="session_1",
        reviewer_agent="reviewer",
        builder_agent="builder",
        diff_ref="diff.patch",
        test_output_ref="test_output.txt",
        diff_summary={"files": 1, "added": 20, "removed": 0},
        gate_results={"scope_check": {"result": "fail", "reason": "scope", "evidence": "diff"}},
        findings=[{"finding_id": "scope_001", "severity": "blocker"}],
        decision="reject",
    )

    assert sealed["review_packet"]["status"] == "rejected"
    assert sealed["proof_packet"]["payload"]["result"] == "hold"
    assert sealed["proof_packet"]["payload"]["merge_decision"] == "hold"
    assert sealed["proof_packet"]["payload"]["gate_results_aggregate"]["scope_check"]["fail_count"] == 1
