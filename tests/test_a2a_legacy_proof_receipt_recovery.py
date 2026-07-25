from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.operator_core.a2a_task_lifecycle import read_queue, task_lifecycle_state
from scripts.governance.a2a_recover_legacy_proof_receipts import build_report
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness


def _queue_path(root: Path) -> Path:
    return root / "a2a_bus" / "tasks" / "queue.jsonl"


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = _queue_path(root)
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_recovers_terminal_legacy_proof_without_closing_duplicate_open_row(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    proof_root = tmp_path / "proofs"
    proof = proof_root / "convergence" / "SHARED_PICTURE.md"
    proof.parent.mkdir(parents=True)
    proof.write_text("# Shared Picture\n\nco-signed evidence\n", encoding="utf-8")
    relative_proof = proof.relative_to(proof_root)
    _write_queue(
        state_root,
        [
            {
                "id": "ts-converge-0611",
                "status": "pending",
                "body": "original mandate remains open unless separately closed",
            },
            {
                "id": "ts-converge-0611",
                "status": "completed",
                "closed_by": "fable_composer",
                "closed_at": "2026-06-12T00:00:00Z",
                "closed_via": "a2a_hygiene_pass_20260612",
                "closure_note": "Convergence mandate executed with co-signed shared picture.",
                "original_row_status_was": "pending",
                "proof_pointer": str(relative_proof),
            },
        ],
    )

    dry_run = build_report(
        state_root=state_root,
        artifact_roots=[proof_root],
        timestamp="2026-07-01T04:04:37Z",
    )

    assert dry_run["candidate_count"] == 1
    assert dry_run["applied_count"] == 0
    assert dry_run["post_readiness"]["open_tasks"] == 1
    assert dry_run["post_readiness"]["unverified_closed_tasks"] == 1

    applied = build_report(
        state_root=state_root,
        artifact_roots=[proof_root],
        apply=True,
        timestamp="2026-07-01T04:04:37Z",
    )

    assert applied["candidate_count"] == 1
    assert applied["applied_count"] == 1
    assert Path(applied["backup_path"]).exists()
    readiness = evaluate_a2a_readiness(state_root)
    assert readiness.ready is False
    assert readiness.open_tasks == 1
    assert readiness.unverified_closed_tasks == 0
    rows = read_queue(state_root)
    assert task_lifecycle_state(rows[0])["state"] == "open_unclaimed"
    assert task_lifecycle_state(rows[1])["state"] == "completed_verified"
    assert rows[1]["required_receipt_schema"] == "dharma_a2a_task_receipt.v1"
    assert rows[1]["receipt"]["artifacts"] == [str(proof)]
    assert rows[1]["receipt"]["evidence"]["recovery_scope"] == "terminal_row_only_no_duplicate_task_inference"


def test_legacy_proof_recovery_skips_missing_proof_file(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    proof_root = tmp_path / "proofs"
    _write_queue(
        state_root,
        [
            {
                "id": "missing-proof",
                "status": "completed",
                "closed_by": "agent-1",
                "closed_via": "legacy-close",
                "proof_pointer": "missing.md",
            }
        ],
    )

    report = build_report(
        state_root=state_root,
        artifact_roots=[proof_root],
        timestamp="2026-07-01T04:04:37Z",
    )

    assert report["candidate_count"] == 0
    assert report["skips"][0]["reason"] == "proof_pointer_missing"
    assert evaluate_a2a_readiness(state_root).unverified_closed_tasks == 1


def test_legacy_proof_recovery_does_not_adapt_open_rows(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    proof_root = tmp_path / "proofs"
    proof = proof_root / "open.md"
    proof.parent.mkdir(parents=True)
    proof.write_text("open proof should not matter\n", encoding="utf-8")
    _write_queue(
        state_root,
        [
            {
                "id": "open-proof",
                "status": "pending",
                "closed_by": "agent-1",
                "closed_via": "legacy-close",
                "proof_pointer": str(proof.relative_to(proof_root)),
            }
        ],
    )

    report = build_report(
        state_root=state_root,
        artifact_roots=[proof_root],
        timestamp="2026-07-01T04:04:37Z",
    )

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 0
    assert evaluate_a2a_readiness(state_root).open_tasks == 1
