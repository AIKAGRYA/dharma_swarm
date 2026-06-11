from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.event_log import EventLog
from dharma_swarm.recursive_discovery import (
    CandidateDiffReceipt,
    CommandReceipt,
    ExperimentResultReceipt,
    PromotionDecisionReceipt,
    RecursiveDiscoveryRecorder,
    RecursiveReceipt,
    build_recursive_shadow_run_receipts,
)
from scripts.validate_recursive_proof import validate_recursive_proof_packet


def test_recursive_proof_validator_accepts_complete_packet(tmp_path: Path) -> None:
    proof_dir = _write_packet(tmp_path, _receipts(exit_code=0))

    report = validate_recursive_proof_packet(proof_dir)

    assert report.ok is True
    assert report.errors == ()
    assert report.foundry_chain_count == 1


def test_recursive_proof_validator_fails_on_missing_receipt_type(tmp_path: Path) -> None:
    receipts = [r for r in _receipts(exit_code=0) if r.receipt_type != "generated_eval"]
    proof_dir = _write_packet(tmp_path, receipts)

    report = validate_recursive_proof_packet(proof_dir)

    assert report.ok is False
    assert any("missing receipt_type:generated_eval" in error for error in report.errors)


def test_recursive_proof_validator_fails_on_autonomous_promotion(tmp_path: Path) -> None:
    receipts = [
        receipt.model_copy(update={"decision": "promote_to_pr"})
        if isinstance(receipt, PromotionDecisionReceipt)
        else receipt
        for receipt in _receipts(exit_code=0)
    ]
    proof_dir = _write_packet(tmp_path, receipts)

    report = validate_recursive_proof_packet(proof_dir)

    assert report.ok is False
    assert any("autonomous_promotion" in error for error in report.errors)


def test_recursive_proof_validator_fails_on_applied_candidate_diff(tmp_path: Path) -> None:
    receipts = [
        receipt.model_copy(update={"metadata": {**receipt.metadata, "diff_applied": True}})
        if isinstance(receipt, CandidateDiffReceipt)
        else receipt
        for receipt in _receipts(exit_code=0)
    ]
    proof_dir = _write_packet(tmp_path, receipts)

    report = validate_recursive_proof_packet(proof_dir)

    assert report.ok is False
    assert any("candidate_diff_applied" in error for error in report.errors)


def test_recursive_proof_validator_fails_when_failed_variant_not_blocked(
    tmp_path: Path,
) -> None:
    receipts = [
        receipt.model_copy(update={"status": "passed"})
        if isinstance(receipt, ExperimentResultReceipt)
        else receipt
        for receipt in _receipts(exit_code=1)
    ]
    proof_dir = _write_packet(tmp_path, receipts)

    report = validate_recursive_proof_packet(proof_dir)

    assert report.ok is False
    assert any("failed_variant_experiment_not_blocked" in error for error in report.errors)


def test_recursive_proof_validator_fails_on_failed_swarm_integrity_report(
    tmp_path: Path,
) -> None:
    proof_dir = _write_packet(tmp_path, _receipts(exit_code=0), v1_all_passed=False)

    report = validate_recursive_proof_packet(proof_dir)

    assert report.ok is False
    assert any("swarm_integrity_v1:failed_report" in error for error in report.errors)


def _receipts(*, exit_code: int) -> list[RecursiveReceipt]:
    return build_recursive_shadow_run_receipts(
        parent_id="foundry-test-variant-01",
        limitation_id="lim-foundry-test-variant-01",
        candidate_id="cand-foundry-test-variant-01",
        eval_id="eval-foundry-test-variant-01",
        prompt="Validate one no-apply recursive proof variant.",
        model_id="deterministic-shadow",
        files_touched=["reports/evolution_foundry/README.md"],
        proof=CommandReceipt(command="python -c pass", exit_code=exit_code),
        sandbox_path="/tmp/foundry/variant-01",
        source="evolution_foundry_shadow",
        metadata={"variant_id": "variant-01"},
    )


def _write_packet(
    root: Path,
    receipts: list[RecursiveReceipt],
    *,
    v0_all_passed: bool = True,
    v1_all_passed: bool = True,
) -> Path:
    proof_dir = root / "proof"
    event_log = EventLog(proof_dir / "events")
    recorder = RecursiveDiscoveryRecorder(event_log)
    for receipt in receipts:
        recorder.record(receipt, session_id="validator-test", trace_id="validator-test")
    _write_integrity_report(
        proof_dir / "swarm_integrity_v0_report.json",
        schema_version="swarm_integrity.v0",
        all_passed=v0_all_passed,
    )
    _write_integrity_report(
        proof_dir / "swarm_integrity_v1_report.json",
        schema_version="swarm_integrity.v1",
        all_passed=v1_all_passed,
    )
    return proof_dir


def _write_integrity_report(
    path: Path,
    *,
    schema_version: str,
    all_passed: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": schema_version,
        "case_count": 1,
        "passed_count": 1 if all_passed else 0,
        "all_passed": all_passed,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
