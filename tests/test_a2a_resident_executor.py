from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.operator_core.a2a_task_lifecycle import read_queue, validate_task_receipt
from dharma_swarm.operator_core.execution_lease import (
    build_execution_lease,
    record_lease_revocation,
    write_execution_lease,
)
from scripts.runtime import a2a_resident_executor as executor


def _write_queue(root: Path, rows: list[dict]) -> None:
    path = root / "a2a_bus" / "tasks" / "queue.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _result_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    state_root = tmp_path / ".dharma"
    repo_root = tmp_path / "repo"
    artifact_root = repo_root / "reports" / "a2a" / "phase_a"
    repo_root.mkdir(parents=True, exist_ok=True)
    return state_root, repo_root, artifact_root


def _write_lease(
    state_root: Path,
    *,
    task_id: str,
    issued_to: str = "codex_composer",
    allowed_path: Path,
    allowed_actions: list[str] | None = None,
    **kwargs,
) -> dict:
    lease = build_execution_lease(
        issued_to=issued_to,
        task_id=task_id,
        correlation_id=f"corr-{task_id}",
        allowed_actions=allowed_actions or ["read", "write_artifact", "close_task", "publish_domain_reply"],
        allowed_paths=[allowed_path],
        **kwargs,
    )
    write_execution_lease(lease, state_root / "a2a_bus" / "leases")
    return lease


def test_valid_lease_closes_task_writes_artifact_receipt_and_local_domain_reply(tmp_path: Path) -> None:
    state_root, repo_root, artifact_root = _result_paths(tmp_path)
    task_id = "phase-a-boring-local"
    _write_queue(
        state_root,
        [
            {
                "id": task_id,
                "from": "operator",
                "to": "codex_composer",
                "status": "pending",
                "body": "Write one boring Phase A local artifact and close with a receipt.",
                "correlation_id": f"corr-{task_id}",
                "reply_subject": f"dharma.agent.operator.inbox.reply.{task_id}",
            }
        ],
    )
    lease = _write_lease(state_root, task_id=task_id, allowed_path=artifact_root)

    result = executor.run_once(
        state_root=state_root,
        repo_root=repo_root,
        artifact_root=artifact_root,
        task_id=task_id,
    )

    assert result["status"] == "completed"
    assert result["lease"]["lease_id"] == lease["lease_id"]
    artifact_path = Path(result["artifact_path"])
    assert artifact_path.exists()
    assert artifact_path.is_relative_to(artifact_root)
    task_receipt = json.loads(Path(result["task_receipt_path"]).read_text(encoding="utf-8"))
    validation = validate_task_receipt(
        task_receipt,
        task_id=task_id,
        agent_uid="codex_composer",
        status="completed",
        require_artifact_or_evidence=True,
    )
    assert validation["valid"], validation["errors"]
    row = read_queue(state_root)[0]
    assert row["status"] == "completed"
    assert row["completed_by"] == "codex_composer"
    assert row["receipt_validation"]["valid"] is True
    domain_reply = result["domain_reply"]
    assert domain_reply["status"] == "DOMAIN_REPLY_PUBLISHED"
    assert domain_reply["live_nats_publish"] is False
    assert Path(domain_reply["receipt_path"]).exists()
    assert (artifact_root / "domain_reply_payloads" / f"{task_id}_domain_payload.json").exists()
    executor_receipt = json.loads(Path(result["executor_receipt_path"]).read_text(encoding="utf-8"))
    assert executor_receipt["status"] == "completed"
    assert executor_receipt["safety"]["git_push_performed"] is False


def test_missing_lease_blocks_forbidden_task_without_task_artifact(tmp_path: Path) -> None:
    state_root, repo_root, artifact_root = _result_paths(tmp_path)
    task_id = "phase-a-forbidden-launchd-install"
    _write_queue(
        state_root,
        [
            {
                "id": task_id,
                "from": "operator",
                "to": "codex_composer",
                "status": "pending",
                "body": "Install and bootstrap the Fable LaunchAgent now, then git push.",
                "requires_execution_lease": True,
            }
        ],
    )

    result = executor.run_once(
        state_root=state_root,
        repo_root=repo_root,
        artifact_root=artifact_root,
        task_id=task_id,
    )

    assert result["status"] == "blocked"
    assert result["failure_reason"] == "execution_lease_required"
    assert not Path(artifact_root / f"{task_id}_artifact.md").exists()
    task_receipt = json.loads(Path(result["task_receipt_path"]).read_text(encoding="utf-8"))
    assert task_receipt["status"] == "blocked"
    assert task_receipt["failure_reason"] == "execution_lease_required"
    validation = validate_task_receipt(task_receipt, task_id=task_id, agent_uid="codex_composer", status="blocked")
    assert validation["valid"], validation["errors"]
    row = read_queue(state_root)[0]
    assert row["status"] == "blocked"
    assert row["failure_reason"] == "execution_lease_required"
    executor_receipt = json.loads(Path(result["executor_receipt_path"]).read_text(encoding="utf-8"))
    assert executor_receipt["safety"]["launchd_install_performed"] is False
    assert executor_receipt["safety"]["git_push_performed"] is False


@pytest.mark.parametrize(
    ("case_name", "lease_kwargs", "agent_uid", "task_id", "artifact_subdir", "expected_error"),
    [
        (
            "expired",
            {
                "issued_at": "2099-07-02T00:00:00+00:00",
                "max_seconds": 60,
            },
            "codex_composer",
            "task-expired",
            "phase_a",
            "lease is expired",
        ),
        (
            "wrong_agent",
            {"issued_to": "other_resident"},
            "codex_composer",
            "task-wrong-agent",
            "phase_a",
            "does not match agent",
        ),
        (
            "outside_path",
            {},
            "codex_composer",
            "task-outside-path",
            "outside_phase_a",
            "outside lease allowed_paths",
        ),
    ],
)
def test_invalid_lease_closes_blocked_with_precise_reason(
    tmp_path: Path,
    case_name: str,
    lease_kwargs: dict,
    agent_uid: str,
    task_id: str,
    artifact_subdir: str,
    expected_error: str,
) -> None:
    lease_kwargs = dict(lease_kwargs)
    state_root, repo_root, artifact_root = _result_paths(tmp_path)
    allowed_root = repo_root / "reports" / "a2a" / "phase_a"
    actual_artifact_root = repo_root / "reports" / "a2a" / artifact_subdir
    _write_queue(
        state_root,
        [
            {
                "id": task_id,
                "from": "operator",
                "to": agent_uid,
                "status": "pending",
                "body": f"Run invalid lease case {case_name}.",
                "correlation_id": f"corr-{task_id}",
            }
        ],
    )
    issued_to = lease_kwargs.pop("issued_to", agent_uid)
    lease = _write_lease(
        state_root,
        task_id=task_id,
        issued_to=issued_to,
        allowed_path=allowed_root,
        allowed_actions=["read", "write_artifact", "close_task"],
        **lease_kwargs,
    )
    rows = read_queue(state_root)
    rows[0]["execution_lease_id"] = lease["lease_id"]
    _write_queue(state_root, rows)

    result = executor.run_once(
        agent_uid=agent_uid,
        state_root=state_root,
        repo_root=repo_root,
        artifact_root=actual_artifact_root,
        task_id=task_id,
        now="2099-07-02T00:02:00+00:00" if case_name == "expired" else None,
    )

    assert result["status"] == "blocked"
    assert expected_error in result["failure_reason"]
    assert not Path(result["artifact_path"] or actual_artifact_root / f"{task_id}_artifact.md").exists()
    assert read_queue(state_root)[0]["status"] == "blocked"


def test_wrong_task_revoked_and_forbidden_action_are_refused(tmp_path: Path) -> None:
    state_root, repo_root, artifact_root = _result_paths(tmp_path)
    rows = []
    cases = [
        ("task-wrong-task", "lease-task-a", "does not match task", "Run wrong task case."),
        ("task-revoked", "task-revoked", "lease is revoked", "Run revoked case."),
        ("task-forbidden", "task-forbidden", "requested action is forbidden: git_push", "Run git push now."),
    ]
    for task_id, _lease_task_id, _expected, body in cases:
        rows.append(
            {
                "id": task_id,
                "from": "operator",
                "to": "codex_composer",
                "status": "pending",
                "body": body,
                "correlation_id": f"corr-{task_id}",
            }
        )
    _write_queue(state_root, rows)

    wrong_task_lease = _write_lease(
        state_root,
        task_id="lease-task-a",
        allowed_path=artifact_root,
        allowed_actions=["read", "write_artifact", "close_task"],
    )
    revoked_lease = _write_lease(
        state_root,
        task_id="task-revoked",
        allowed_path=artifact_root,
        allowed_actions=["read", "write_artifact", "close_task"],
    )
    record_lease_revocation(state_root / "a2a_bus" / "leases", revoked_lease["lease_id"], reason="unit test")
    forbidden_lease = _write_lease(
        state_root,
        task_id="task-forbidden",
        allowed_path=artifact_root,
        allowed_actions=["read", "write_artifact", "close_task", "git_push"],
    )

    rows = read_queue(state_root)
    rows[0]["execution_lease_id"] = wrong_task_lease["lease_id"]
    rows[1]["execution_lease_id"] = revoked_lease["lease_id"]
    rows[2]["execution_lease_id"] = forbidden_lease["lease_id"]
    _write_queue(state_root, rows)

    for task_id, _lease_task_id, expected, _body in cases:
        result = executor.run_once(
            state_root=state_root,
            repo_root=repo_root,
            artifact_root=artifact_root,
            task_id=task_id,
        )
        assert result["status"] == "blocked"
        assert expected in result["failure_reason"]

    rows_by_id = {row["id"]: row for row in read_queue(state_root)}
    assert all(row["status"] == "blocked" for row in rows_by_id.values())


@pytest.mark.parametrize(
    ("lease_overrides", "expected"),
    [
        ({"allowed_actions": []}, "allowed_actions must be explicit"),
        ({"allowed_paths": []}, "allowed_paths must be explicit"),
        ({"max_usd": 1.0}, "max_usd must be 0"),
    ],
)
def test_phase_a_executor_rejects_broad_or_spend_leases(
    tmp_path: Path,
    lease_overrides: dict,
    expected: str,
) -> None:
    state_root, repo_root, artifact_root = _result_paths(tmp_path)
    task_id = "task-hardening"
    _write_queue(
        state_root,
        [
            {
                "id": task_id,
                "from": "operator",
                "to": "codex_composer",
                "status": "pending",
                "body": "Write one allowed artifact.",
                "correlation_id": f"corr-{task_id}",
            }
        ],
    )
    allowed_actions = lease_overrides.pop("allowed_actions", ["read", "write_artifact", "close_task"])
    allowed_paths = lease_overrides.pop("allowed_paths", [artifact_root])
    lease = build_execution_lease(
        issued_to="codex_composer",
        task_id=task_id,
        correlation_id=f"corr-{task_id}",
        allowed_actions=allowed_actions,
        allowed_paths=allowed_paths,
        **lease_overrides,
    )
    write_execution_lease(lease, state_root / "a2a_bus" / "leases")

    result = executor.run_once(
        state_root=state_root,
        repo_root=repo_root,
        artifact_root=artifact_root,
        task_id=task_id,
    )

    assert result["status"] == "blocked"
    assert expected in result["failure_reason"]
