"""Sarathi unattended-proof harness (PR-S4): mechanical, fail-closed.

Gate-10 made executable: 14 consecutive clean propose-only cycles, every
brief audited against resolvable receipts, kill path verified first, any
fabricated state resets the window.
"""

from __future__ import annotations

from dharma_swarm.holon_system.sarathi.proof import (
    PROOF_DIAL_LEVEL,
    REQUIRED_UNATTENDED_CYCLES,
    ProofCycleRecord,
    dial_advance_on_pass,
    evaluate_unattended_proof,
    sakshi_audit_brief,
)


def _clean(index: int) -> ProofCycleRecord:
    return ProofCycleRecord(cycle_index=index, status="ran", dial_level=PROOF_DIAL_LEVEL)


def test_fourteen_clean_cycles_with_kill_path_pass() -> None:
    records = [_clean(i) for i in range(REQUIRED_UNATTENDED_CYCLES)]
    verdict = evaluate_unattended_proof(records, kill_path_verified=True)
    assert verdict.passed is True
    assert verdict.consecutive_clean == 14
    assert verdict.failures == ()
    assert dial_advance_on_pass(verdict) == "dispatch"


def test_kill_path_unverified_fails_regardless_of_cycles() -> None:
    records = [_clean(i) for i in range(20)]
    verdict = evaluate_unattended_proof(records, kill_path_verified=False)
    assert verdict.passed is False
    assert any("loop-emergency-stop" in f for f in verdict.failures)
    assert dial_advance_on_pass(verdict) is None


def test_fabricated_state_resets_the_window() -> None:
    from dharma_swarm.holon_system.sarathi.proof import BriefAuditFinding

    records = [_clean(i) for i in range(10)]
    records.append(
        ProofCycleRecord(
            cycle_index=10,
            status="ran",
            dial_level=PROOF_DIAL_LEVEL,
            audit_findings=(BriefAuditFinding("missing_receipt", "row X unbacked"),),
        )
    )
    records += [_clean(11 + i) for i in range(13)]
    verdict = evaluate_unattended_proof(records, kill_path_verified=True)
    assert verdict.passed is False  # only 13 clean since the reset
    assert verdict.consecutive_clean == 13
    assert any("window reset" in f for f in verdict.failures)
    # One more clean cycle after the reset completes the window.
    records.append(_clean(24))
    assert evaluate_unattended_proof(records, kill_path_verified=True).passed is True


def test_proof_window_is_propose_only() -> None:
    records = [_clean(i) for i in range(13)]
    records.append(ProofCycleRecord(cycle_index=13, status="ran", dial_level="dispatch"))
    verdict = evaluate_unattended_proof(records, kill_path_verified=True)
    assert verdict.passed is False
    assert any("propose-only" in f for f in verdict.failures)


def test_halted_cycles_are_not_clean() -> None:
    records = [_clean(0), ProofCycleRecord(1, "halted:error", PROOF_DIAL_LEVEL)]
    verdict = evaluate_unattended_proof(
        records, kill_path_verified=True, required_cycles=2
    )
    assert verdict.passed is False
    assert verdict.consecutive_clean == 0


def test_sakshi_audit_flags_unbacked_and_unresolvable_receipts() -> None:
    outcomes = [
        {"status": "dispatched", "summary": "good", "receipt_ref": "mbx_ok"},
        {"status": "dispatched", "summary": "no-ref", "receipt_ref": ""},
        {"status": "dispatched", "summary": "bad-ref", "receipt_ref": "mbx_missing"},
        {"status": "proposed", "summary": "proposal", "receipt_ref": ""},
        {"status": "gated", "summary": "blocked", "receipt_ref": ""},
    ]
    findings = sakshi_audit_brief(
        outcomes, receipt_exists=lambda ref: ref == "mbx_ok"
    )
    kinds = sorted(f.kind for f in findings)
    assert kinds == ["missing_receipt", "unresolvable_receipt"]
    # A fully-backed ledger audits clean.
    assert (
        sakshi_audit_brief(
            [{"status": "dispatched", "summary": "s", "receipt_ref": "mbx_ok"}],
            receipt_exists=lambda ref: True,
        )
        == []
    )
