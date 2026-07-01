from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.operator_core.a2a_task_lifecycle import read_queue, task_lifecycle_state
from scripts.governance.a2a_block_stale_forge_v01 import (
    DEFAULT_MISSION_ID,
    DEFAULT_TASK_ID,
    DEFAULT_TARGET_AGENT,
    HANDOFF_NAME,
    SPEC_RELATIVE_PATH,
    build_report,
)
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness


def _queue_path(root: Path) -> Path:
    return root / "a2a_bus" / "tasks" / "queue.jsonl"


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = _queue_path(root)
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _forge_row(**overrides: object) -> dict:
    row = {
        "id": DEFAULT_TASK_ID,
        "status": "pending",
        "created": "2026-06-01T01:30:00+08:00",
        "from": "opus_forge_architect",
        "to": DEFAULT_TARGET_AGENT,
        "type": "build",
        "mission_id": DEFAULT_MISSION_ID,
        "body": (
            "forge_council: (1) countersign v0.1.0 verifier_artifact (decorrelated); "
            f"(2) build v0.1.1 transfer-gate in shadow per {SPEC_RELATIVE_PATH}. "
            f"See inbox handoff {HANDOFF_NAME}. SHADOW ONLY, no merge/promote (human rung)."
        ),
    }
    row.update(overrides)
    return row


def _write_stale_target(root: Path, *, last_seen_at: str = "2026-05-31T17:04:12.385566+00:00") -> None:
    agent_dir = root / "agents" / DEFAULT_TARGET_AGENT
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "living_agent.json").write_text(
        json.dumps(
            {
                "agent_uid": DEFAULT_TARGET_AGENT,
                "status": "starting",
                "last_seen_at": last_seen_at,
                "metadata": {
                    "authority": "external_worker_evidence_only",
                    "autonomy_policy": {
                        "requires_approval": True,
                        "can_write_source": False,
                    },
                    "workspace_policy": {
                        "repo_writes_allowed": False,
                        "canonical_dharma_dir_writes_allowed": False,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    external_dir = root / "external_agents" / DEFAULT_TARGET_AGENT
    external_dir.mkdir(parents=True, exist_ok=True)
    (external_dir / "registration.json").write_text(
        json.dumps(
            {
                "agent_uid": DEFAULT_TARGET_AGENT,
                "authority": "external_worker_evidence_only",
                "status": "registered",
                "last_seen_at": last_seen_at,
                "autonomy_policy": {
                    "requires_approval": True,
                    "can_write_source": False,
                },
                "workspace_policy": {
                    "repo_writes_allowed": False,
                    "canonical_dharma_dir_writes_allowed": False,
                },
                "metadata": {
                    "cannot_certify_own_lane": True,
                    "requires_decorrelated_evaluator": True,
                },
            }
        ),
        encoding="utf-8",
    )


def _write_mission(root: Path) -> None:
    mission_dir = root / "autonomy_spine" / DEFAULT_MISSION_ID
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "brief.md").write_text("# Brief\n", encoding="utf-8")
    (mission_dir / "tasks.jsonl").write_text(
        json.dumps(
            {
                "task_id": f"{DEFAULT_MISSION_ID}-t02-builder",
                "role": "builder",
                "status": "completed",
                "receipt_id": "r-099cde40c5b64803",
                "lease": {"claimed_by": DEFAULT_TARGET_AGENT},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_dry_run_selects_only_stale_forge_v01_row(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    canonical = tmp_path / "canonical"
    repo_root.mkdir()
    canonical.mkdir()
    _write_stale_target(tmp_path)
    _write_mission(tmp_path)
    _write_queue(
        tmp_path,
        [
            _forge_row(),
            _forge_row(id="forge-other"),
            {"id": "ordinary-open", "status": "pending", "created": "2026-06-01T00:00:00Z"},
        ],
    )

    report = build_report(
        tmp_path,
        timestamp="2026-07-01T07:20:00Z",
        repo_root=repo_root,
        canonical_repo=canonical,
    )

    assert report["candidate_count"] == 1
    assert report["applied_count"] == 0
    assert report["actions"][0]["task_id"] == DEFAULT_TASK_ID
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 3


def test_apply_blocks_forge_v01_with_supervisor_receipt(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    canonical = tmp_path / "canonical"
    repo_root.mkdir()
    canonical.mkdir()
    _write_stale_target(tmp_path)
    _write_mission(tmp_path)
    _write_queue(tmp_path, [_forge_row()])

    report = build_report(
        tmp_path,
        apply=True,
        timestamp="2026-07-01T07:20:00Z",
        repo_root=repo_root,
        canonical_repo=canonical,
    )

    assert report["candidate_count"] == 1
    assert report["applied_count"] == 1
    assert Path(report["backup_path"]).exists()
    assert report["post_readiness"]["ready"] is True
    rows = {row["id"]: row for row in read_queue(tmp_path)}
    row = rows[DEFAULT_TASK_ID]
    assert task_lifecycle_state(row)["state"] == "blocked_verified"
    assert row["receipt"]["authority"] == "stale_forge_v01_supervisor_block"
    assert row["receipt"]["failure_reason"] == "forge_work_packet_missing_and_target_stale_or_external_gated"
    assert row["receipt"]["evidence"]["supervisor_scope"] == "block_only_no_forge_build_or_lane_selection_claimed"


def test_existing_spec_prevents_forge_block(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    canonical = tmp_path / "canonical"
    spec = repo_root / SPEC_RELATIVE_PATH
    spec.parent.mkdir(parents=True)
    spec.write_text("# transfer gate\n", encoding="utf-8")
    canonical.mkdir()
    _write_stale_target(tmp_path)
    _write_mission(tmp_path)
    _write_queue(tmp_path, [_forge_row()])

    report = build_report(
        tmp_path,
        timestamp="2026-07-01T07:20:00Z",
        repo_root=repo_root,
        canonical_repo=canonical,
    )

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 1
    assert report["skips"][0]["reason"] == "required_spec_present"
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 1


def test_existing_handoff_prevents_forge_block(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    canonical = tmp_path / "canonical"
    repo_root.mkdir()
    canonical.mkdir()
    handoff = tmp_path / "a2a_bus" / "inboxes" / DEFAULT_TARGET_AGENT / HANDOFF_NAME
    handoff.parent.mkdir(parents=True)
    handoff.write_text("{}\n", encoding="utf-8")
    _write_stale_target(tmp_path)
    _write_mission(tmp_path)
    _write_queue(tmp_path, [_forge_row()])

    report = build_report(
        tmp_path,
        timestamp="2026-07-01T07:20:00Z",
        repo_root=repo_root,
        canonical_repo=canonical,
    )

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 1
    assert report["skips"][0]["reason"] == "handoff_present"
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 1


def test_fresh_target_prevents_forge_block(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    canonical = tmp_path / "canonical"
    repo_root.mkdir()
    canonical.mkdir()
    _write_stale_target(tmp_path, last_seen_at="2026-07-01T07:10:00Z")
    _write_mission(tmp_path)
    _write_queue(tmp_path, [_forge_row()])

    report = build_report(
        tmp_path,
        timestamp="2026-07-01T07:20:00Z",
        repo_root=repo_root,
        canonical_repo=canonical,
    )

    assert report["candidate_count"] == 0
    assert report["skip_count"] == 1
    assert report["skips"][0]["reason"] == "target_not_stale_or_gated"
    assert evaluate_a2a_readiness(tmp_path).open_tasks == 1
