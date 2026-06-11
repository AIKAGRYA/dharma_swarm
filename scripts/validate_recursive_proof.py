#!/usr/bin/env python3
"""Validate a governed recursive proof packet."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dharma_swarm.event_log import EventLog
from dharma_swarm.recursive_discovery import (
    CandidateDiffReceipt,
    ExperimentResultReceipt,
    PromotionDecisionReceipt,
    RECEIPT_TYPES,
    RecursiveReceipt,
    WitnessVerdictReceipt,
    load_recursive_receipts,
    receipt_counts_by_type,
    validate_minimum_receipt_chain,
)


@dataclass(frozen=True)
class RecursiveProofValidationReport:
    schema_version: str
    proof_dir: str
    ok: bool
    errors: tuple[str, ...]
    receipt_count: int
    foundry_chain_count: int
    receipt_counts: dict[str, int]
    swarm_integrity: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proof_dir": self.proof_dir,
            "ok": self.ok,
            "errors": self.errors,
            "receipt_count": self.receipt_count,
            "foundry_chain_count": self.foundry_chain_count,
            "receipt_counts": self.receipt_counts,
            "swarm_integrity": self.swarm_integrity,
        }


def validate_recursive_proof_packet(proof_dir: Path) -> RecursiveProofValidationReport:
    """Validate a recursive proof packet directory."""

    root = proof_dir.resolve()
    errors: list[str] = []
    event_dir = root / "events"
    receipts = load_recursive_receipts(EventLog(event_dir))
    if not receipts:
        errors.append("missing recursive_discovery receipts")

    foundry_receipts = [
        receipt for receipt in receipts if _is_foundry_receipt(receipt)
    ]
    foundry_counts = receipt_counts_by_type(foundry_receipts)
    for receipt_type in RECEIPT_TYPES:
        if foundry_counts.get(receipt_type, 0) < 1:
            errors.append(f"missing receipt_type:{receipt_type}")

    grouped = _group_by_parent(foundry_receipts)
    if not grouped:
        errors.append("missing foundry receipt chains")
    for parent_id, chain in grouped.items():
        ok, chain_errors = validate_minimum_receipt_chain(chain)
        if not ok:
            errors.extend(f"{parent_id}:{error}" for error in chain_errors)
        errors.extend(_validate_no_apply_candidate_diffs(parent_id, chain))
        errors.extend(_validate_failed_variants_blocked_or_held(parent_id, chain))
        errors.extend(_validate_no_autonomous_promotion(parent_id, chain))

    swarm_integrity = _validate_swarm_integrity_reports(root, errors)

    return RecursiveProofValidationReport(
        schema_version="recursive_proof_validation.v0",
        proof_dir=str(root),
        ok=not errors,
        errors=tuple(errors),
        receipt_count=len(receipts),
        foundry_chain_count=len(grouped),
        receipt_counts=foundry_counts,
        swarm_integrity=swarm_integrity,
    )


def _is_foundry_receipt(receipt: RecursiveReceipt) -> bool:
    source = str(receipt.metadata.get("source") or "")
    return source == "evolution_foundry_shadow" or bool(receipt.metadata.get("variant_id"))


def _group_by_parent(receipts: Sequence[RecursiveReceipt]) -> dict[str, list[RecursiveReceipt]]:
    grouped: dict[str, list[RecursiveReceipt]] = {}
    for receipt in receipts:
        grouped.setdefault(receipt.parent_id or receipt.receipt_id, []).append(receipt)
    return grouped


def _validate_no_apply_candidate_diffs(
    parent_id: str,
    chain: Sequence[RecursiveReceipt],
) -> list[str]:
    errors: list[str] = []
    for receipt in chain:
        if not isinstance(receipt, CandidateDiffReceipt):
            continue
        if receipt.metadata.get("diff_applied") is not False:
            errors.append(f"{parent_id}:{receipt.receipt_id}:candidate_diff_applied")
        if not receipt.rollback_pointer:
            errors.append(f"{parent_id}:{receipt.receipt_id}:missing_rollback_pointer")
    return errors


def _validate_failed_variants_blocked_or_held(
    parent_id: str,
    chain: Sequence[RecursiveReceipt],
) -> list[str]:
    failed = any(
        isinstance(receipt, ExperimentResultReceipt)
        and any(command.exit_code != 0 for command in receipt.commands)
        for receipt in chain
    )
    if not failed:
        return []

    errors: list[str] = []
    experiment_receipts = [
        receipt for receipt in chain if isinstance(receipt, ExperimentResultReceipt)
    ]
    witness_receipts = [
        receipt for receipt in chain if isinstance(receipt, WitnessVerdictReceipt)
    ]
    promotion_receipts = [
        receipt for receipt in chain if isinstance(receipt, PromotionDecisionReceipt)
    ]
    if not all(receipt.status == "blocked" for receipt in experiment_receipts):
        errors.append(f"{parent_id}:failed_variant_experiment_not_blocked")
    if not any(
        receipt.status == "blocked"
        or any(verdict.verdict == "blocked" for verdict in receipt.witness_verdicts)
        for receipt in witness_receipts
    ):
        errors.append(f"{parent_id}:failed_variant_witness_not_blocked")
    if not all(
        receipt.status in {"blocked", "pending"} and receipt.decision == "hold"
        for receipt in promotion_receipts
    ):
        errors.append(f"{parent_id}:failed_variant_promotion_not_held")
    return errors


def _validate_no_autonomous_promotion(
    parent_id: str,
    chain: Sequence[RecursiveReceipt],
) -> list[str]:
    errors: list[str] = []
    for receipt in chain:
        if isinstance(receipt, PromotionDecisionReceipt) and receipt.decision == "promote_to_pr":
            errors.append(f"{parent_id}:{receipt.receipt_id}:autonomous_promotion")
    return errors


def _validate_swarm_integrity_reports(
    proof_dir: Path,
    errors: list[str],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for version in ("v0", "v1"):
        path = proof_dir / f"swarm_integrity_{version}_report.json"
        key = f"swarm_integrity_{version}"
        if not path.exists():
            errors.append(f"{key}:missing_report")
            summary[key] = {"ok": False, "path": str(path)}
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{key}:invalid_json:{exc}")
            summary[key] = {"ok": False, "path": str(path)}
            continue
        ok = bool(report.get("all_passed")) and int(report.get("passed_count") or 0) == int(
            report.get("case_count") or -1
        )
        if not ok:
            errors.append(f"{key}:failed_report")
        summary[key] = {
            "ok": ok,
            "schema_version": report.get("schema_version", ""),
            "case_count": report.get("case_count", 0),
            "passed_count": report.get("passed_count", 0),
            "path": str(path),
        }
    return summary


def write_validation_report(path: Path, report: RecursiveProofValidationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_json(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-dir", type=Path, default=Path("reports/recursive_shadow_foundry"))
    parser.add_argument("--report-json", type=Path, default=None)
    args = parser.parse_args(argv)

    report = validate_recursive_proof_packet(args.proof_dir)
    if args.report_json is not None:
        write_validation_report(args.report_json, report)
    print(json.dumps(report.to_json(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
