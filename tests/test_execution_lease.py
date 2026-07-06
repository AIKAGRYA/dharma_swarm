from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from dharma_swarm.operator_core.execution_lease import (
    build_execution_lease,
    find_execution_lease_for_task,
    load_execution_lease,
    load_revoked_lease_ids,
    record_lease_revocation,
    validate_execution_lease,
    write_execution_lease,
)


def test_build_validate_and_write_execution_lease(tmp_path: Path) -> None:
    lease = build_execution_lease(
        issued_to="codex_composer",
        task_id="task-1",
        correlation_id="corr-1",
        allowed_actions=["read", "write_artifact", "close_task"],
        allowed_paths=[tmp_path / "reports"],
    )

    validation = validate_execution_lease(
        lease,
        agent_uid="codex_composer",
        task_id="task-1",
        requested_actions=["read", "close_task"],
        requested_paths=[tmp_path / "reports" / "artifact.md"],
    )
    assert validation.valid, validation.errors

    path = write_execution_lease(lease, tmp_path / "leases")
    loaded = load_execution_lease(tmp_path / "leases", lease["lease_id"])
    assert path.exists()
    assert loaded == lease


def test_execution_lease_rejects_wrong_agent_expiry_action_path_and_hash(tmp_path: Path) -> None:
    lease = build_execution_lease(
        issued_to="codex_composer",
        task_id="task-1",
        allowed_actions=["read"],
        allowed_paths=[tmp_path / "allowed"],
        max_seconds=60,
        issued_at="2026-07-02T00:00:00+00:00",
    )

    expired = validate_execution_lease(
        lease,
        now="2026-07-02T00:02:00+00:00",
        agent_uid="fable_composer",
        task_id="task-1",
        requested_actions=["git_push"],
        requested_paths=[tmp_path / "denied" / "artifact.md"],
    )

    assert not expired.valid
    assert any("expired" in error for error in expired.errors)
    assert any("does not match agent" in error for error in expired.errors)
    assert any("not allowed" in error or "forbidden" in error for error in expired.errors)
    assert any("outside lease allowed_paths" in error for error in expired.errors)

    tampered = dict(lease)
    tampered["allowed_actions"] = ["read", "git_push"]
    invalid = validate_execution_lease(tampered, now="2026-07-02T00:00:30+00:00")
    assert not invalid.valid
    assert any("content_hash" in error for error in invalid.errors)


def test_execution_lease_revocation_invalidates(tmp_path: Path) -> None:
    root = tmp_path / "leases"
    lease = build_execution_lease(issued_to="codex_composer", allowed_actions=["read"])
    write_execution_lease(lease, root)
    record_lease_revocation(root, lease["lease_id"], reason="operator test")

    revoked = load_revoked_lease_ids(root)
    validation = validate_execution_lease(lease, revoked_lease_ids=revoked)

    assert lease["lease_id"] in revoked
    assert not validation.valid
    assert "lease is revoked" in validation.errors


def test_find_execution_lease_for_task_matches_without_packet_mutation(tmp_path: Path) -> None:
    root = tmp_path / "leases"
    lease = build_execution_lease(
        issued_to="codex_composer",
        task_id="packet-123",
        correlation_id="corr-123",
        allowed_actions=["read", "write_artifact"],
    )
    write_execution_lease(lease, root)

    match = find_execution_lease_for_task(
        root,
        agent_uid="codex_composer",
        task_id="packet-123",
        correlation_id="",
    )

    assert match is not None
    _path, matched, validation = match
    assert matched == lease
    assert validation.valid


def test_issue_execution_lease_cli_dry_run_outputs_valid_json(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/runtime/issue_execution_lease.py",
            "--lease-root",
            str(tmp_path / "leases"),
            "--issued-to",
            "codex_composer",
            "--allowed-action",
            "read",
            "--allowed-path",
            str(tmp_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["validation"]["valid"] is True
    assert not (tmp_path / "leases").exists()
