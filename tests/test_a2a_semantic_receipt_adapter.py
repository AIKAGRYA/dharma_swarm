from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.operator_core.a2a_task_lifecycle import read_queue, task_lifecycle_state
from scripts.governance.a2a_adapt_semantic_receipts import build_report
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness


def _queue_path(root: Path) -> Path:
    return root / "a2a_bus" / "tasks" / "queue.jsonl"


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = _queue_path(root)
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _semantic_receipt(task_id: str, agent_id: str) -> dict:
    return {
        "schema": "sab.semantic_receipt.v1",
        "receipt_id": f"sab.semantic_receipt:{task_id}:20260701T0000Z",
        "task_id": task_id,
        "agent_id": agent_id,
        "mission_id": "sab-test",
        "created_at": "2026-07-01T00:00:00Z",
        "sab_instance_id": "sab-test-instance",
        "latest_post_id_seen": 7,
        "latest_witness_hash_seen": "abc123",
        "semantic_action": "verification",
        "claim": "The semantic task produced the required evidence.",
        "evidence": ["observed post id 7", "observed witness hash abc123"],
        "action_taken": "Recorded the verified semantic result.",
        "next_request": "No follow-up required.",
    }


def _write_semantic_receipt(root: Path, task_id: str, agent_id: str) -> Path:
    path = root / "reports" / "sab" / f"{task_id}.semantic_receipt.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(_semantic_receipt(task_id, agent_id), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def test_adapts_terminal_semantic_receipt_into_verified_a2a_receipt(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    artifact_root = tmp_path / "artifacts"
    task_id = "semantic-done"
    receipt_path = _write_semantic_receipt(artifact_root, task_id, "sab-agent")
    relative_receipt_path = receipt_path.relative_to(artifact_root)
    _write_queue(
        state_root,
        [
            {
                "id": task_id,
                "status": "completed",
                "closed_by": "sab-agent",
                "completed_by": "sab-agent",
                "closed_at": "2026-07-01T00:01:00Z",
                "completed_at": "2026-07-01T00:01:00Z",
                "receipt_id": f"sab.semantic_receipt:{task_id}:20260701T0000Z",
                "receipt_path": str(relative_receipt_path),
                "receipt_validation": {"schema": "sab.semantic_receipt.v1", "valid": True},
                "required_receipt_schema": "sab.semantic_receipt.v1",
            }
        ],
    )

    dry_run = build_report(
        state_root=state_root,
        artifact_roots=[artifact_root],
        timestamp="2026-07-01T03:40:35Z",
    )

    assert dry_run["mode"] == "dry_run"
    assert dry_run["candidate_count"] == 1
    assert dry_run["applied_count"] == 0
    assert dry_run["post_readiness"]["unverified_closed_tasks"] == 1

    applied = build_report(
        state_root=state_root,
        artifact_roots=[artifact_root],
        apply=True,
        timestamp="2026-07-01T03:40:35Z",
    )

    assert applied["candidate_count"] == 1
    assert applied["applied_count"] == 1
    assert Path(applied["backup_path"]).exists()
    readiness = evaluate_a2a_readiness(state_root)
    assert readiness.ready is True
    row = read_queue(state_root)[0]
    assert row["required_receipt_schema"] == "dharma_a2a_task_receipt.v1"
    assert row["semantic_receipt_id"] == f"sab.semantic_receipt:{task_id}:20260701T0000Z"
    assert row["receipt"]["schema_version"] == "dharma_a2a_task_receipt.v1"
    assert row["receipt"]["artifacts"] == [str(receipt_path)]
    assert task_lifecycle_state(row)["state"] == "completed_verified"


def test_semantic_adapter_skips_agent_identity_mismatch(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    artifact_root = tmp_path / "artifacts"
    task_id = "semantic-mismatch"
    receipt_path = _write_semantic_receipt(artifact_root, task_id, "sab-agent")
    _write_queue(
        state_root,
        [
            {
                "id": task_id,
                "status": "completed",
                "closed_by": "different-agent",
                "completed_by": "different-agent",
                "receipt_id": f"sab.semantic_receipt:{task_id}:20260701T0000Z",
                "receipt_path": str(receipt_path.relative_to(artifact_root)),
                "receipt_validation": {"schema": "sab.semantic_receipt.v1", "valid": True},
                "required_receipt_schema": "sab.semantic_receipt.v1",
            }
        ],
    )

    report = build_report(
        state_root=state_root,
        artifact_roots=[artifact_root],
        timestamp="2026-07-01T03:40:35Z",
    )

    assert report["candidate_count"] == 0
    assert report["skips"][0]["reason"] == "agent_identity_mismatch"
    assert evaluate_a2a_readiness(state_root).unverified_closed_tasks == 1


def test_semantic_adapter_does_not_adapt_open_rows(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    artifact_root = tmp_path / "artifacts"
    task_id = "semantic-open"
    receipt_path = _write_semantic_receipt(artifact_root, task_id, "sab-agent")
    _write_queue(
        state_root,
        [
            {
                "id": task_id,
                "status": "pending",
                "receipt_id": f"sab.semantic_receipt:{task_id}:20260701T0000Z",
                "receipt_path": str(receipt_path.relative_to(artifact_root)),
                "receipt_validation": {"schema": "sab.semantic_receipt.v1", "valid": True},
                "required_receipt_schema": "sab.semantic_receipt.v1",
            }
        ],
    )

    report = build_report(
        state_root=state_root,
        artifact_roots=[artifact_root],
        timestamp="2026-07-01T03:40:35Z",
    )

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 0
    assert evaluate_a2a_readiness(state_root).open_tasks == 1
