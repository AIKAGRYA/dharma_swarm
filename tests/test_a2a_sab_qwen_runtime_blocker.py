from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.operator_core.a2a_task_lifecycle import read_queue, task_lifecycle_state
from scripts.governance.a2a_block_sab_qwen_runtime_blockers import (
    DEFAULT_TASK_ID,
    build_report,
)
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness


def _queue_path(root: Path) -> Path:
    return root / "a2a_bus" / "tasks" / "queue.jsonl"


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = _queue_path(root)
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _artifact_receipts_dir(root: Path) -> Path:
    path = root / "reports" / "sab_first_six_agent_flywheel" / "receipts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _qwen_row(**overrides: object) -> dict:
    row = {
        "id": DEFAULT_TASK_ID,
        "status": "pending",
        "created": "2026-06-27T18:43:00Z",
        "to": "qwen_code",
        "from": "codex_composer",
        "required_receipt_schema": "sab.semantic_receipt.v1",
        "expected_receipt_path": (
            "reports/sab_first_six_agent_flywheel/receipts/"
            "sab-flywheel-d01-qwen-code-first-spark.semantic_receipt.json"
        ),
        "body": "Return sab.semantic_receipt.v1. No naked ACK.",
    }
    row.update(overrides)
    return row


def _runtime_blocked_receipt(task_id: str = DEFAULT_TASK_ID) -> dict:
    return {
        "schema": "sab.semantic_receipt.v1",
        "task_id": f"{task_id}-runtime-blocked",
        "agent": "codex_composer_mac",
        "sab_instance_id": "sab_agni_prod_157_245_193_15",
        "latest_post_id_seen": 12,
        "latest_witness_hash_seen": "abc123",
        "semantic_action": "refusal",
        "claim": "The Qwen First Spark task remains blocked on Qwen CLI/provider authentication.",
        "evidence": [
            "Qwen CLI exists.",
            "Default auth failed before model execution.",
            "OpenAI auth failed because OPENAI_API_KEY is missing.",
            "Qwen OAuth mode is unavailable.",
        ],
        "action_taken": "Refused to fabricate a target-owned qwen_code receipt.",
        "next_request": "Configure a working Qwen/OpenAI-compatible provider and rerun the capture.",
    }


def _write_runtime_blocked_receipt(root: Path, payload: dict | None = None) -> Path:
    path = _artifact_receipts_dir(root) / (
        "sab-flywheel-d01-qwen-code-first-spark-runtime-blocked-20260628T1322Z.semantic_receipt.json"
    )
    path.write_text(json.dumps(payload or _runtime_blocked_receipt(), indent=2), encoding="utf-8")
    return path


def test_dry_run_selects_only_missing_expected_qwen_receipt_with_runtime_blocker(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    artifact_root = tmp_path / "artifacts"
    _write_queue(
        state_root,
        [
            _qwen_row(),
            {
                "id": "ordinary-sab",
                "status": "pending",
                "created": "2026-06-27T18:43:00Z",
                "required_receipt_schema": "sab.semantic_receipt.v1",
            },
        ],
    )
    source = _write_runtime_blocked_receipt(artifact_root)

    report = build_report(
        state_root,
        artifact_roots=[artifact_root],
        timestamp="2026-07-01T05:40:14Z",
    )

    assert report["candidate_count"] == 1
    assert report["applied_count"] == 0
    assert report["actions"][0]["task_id"] == DEFAULT_TASK_ID
    assert report["actions"][0]["source_receipts"][0]["path"] == str(source)
    assert evaluate_a2a_readiness(state_root).open_tasks == 2


def test_apply_blocks_qwen_row_with_supervisor_receipt(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    artifact_root = tmp_path / "artifacts"
    _write_queue(state_root, [_qwen_row(), {"id": "still-open", "status": "pending"}])
    _write_runtime_blocked_receipt(artifact_root)

    report = build_report(
        state_root,
        artifact_roots=[artifact_root],
        apply=True,
        timestamp="2026-07-01T05:40:14Z",
    )

    assert report["candidate_count"] == 1
    assert report["applied_count"] == 1
    assert Path(report["backup_path"]).exists()
    readiness = evaluate_a2a_readiness(state_root)
    assert readiness.ready is False
    assert readiness.open_tasks == 1
    rows = {row["id"]: row for row in read_queue(state_root)}
    qwen = rows[DEFAULT_TASK_ID]
    assert task_lifecycle_state(qwen)["state"] == "blocked_verified"
    assert qwen["receipt"]["authority"] == "sab_first_spark_runtime_block_supervisor_block"
    assert qwen["receipt"]["failure_reason"] == "target_qwen_runtime_unavailable_without_target_owned_receipt"
    assert qwen["receipt"]["evidence"]["expected_receipt_exists"] is False
    assert qwen["receipt"]["evidence"]["supervisor_scope"] == "block_only_no_qwen_completion_or_post_claimed"


def test_expected_target_owned_receipt_prevents_supervisor_block(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    artifact_root = tmp_path / "artifacts"
    _write_queue(state_root, [_qwen_row()])
    _write_runtime_blocked_receipt(artifact_root)
    expected = _artifact_receipts_dir(artifact_root) / f"{DEFAULT_TASK_ID}.semantic_receipt.json"
    expected.write_text(json.dumps(_runtime_blocked_receipt(task_id=DEFAULT_TASK_ID)), encoding="utf-8")

    report = build_report(
        state_root,
        artifact_roots=[artifact_root],
        timestamp="2026-07-01T05:40:14Z",
    )

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 1
    assert report["skips"][0]["reason"] == "exact_expected_receipt_present"
    assert evaluate_a2a_readiness(state_root).open_tasks == 1


def test_unrelated_semantic_receipt_does_not_block_qwen_row(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    artifact_root = tmp_path / "artifacts"
    _write_queue(state_root, [_qwen_row()])
    unrelated = _runtime_blocked_receipt(task_id="different-task")
    unrelated["task_id"] = "different-task-runtime-blocked"
    _write_runtime_blocked_receipt(artifact_root, payload=unrelated)

    report = build_report(
        state_root,
        artifact_roots=[artifact_root],
        timestamp="2026-07-01T05:40:14Z",
    )

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 1
    assert report["skips"][0]["reason"] == "no_valid_related_refusal_receipt"
    assert evaluate_a2a_readiness(state_root).open_tasks == 1
