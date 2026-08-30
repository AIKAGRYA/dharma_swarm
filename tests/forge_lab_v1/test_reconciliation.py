from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.forge_lab import reconciliation
from dharma_swarm.forge_lab.source_guard import CANONICAL_REPOSITORY
from dharma_swarm.forge_lab.state_io import content_digest


def _source(commit: str = "a" * 40) -> dict[str, Any]:
    repo = f"/immutable/releases/{commit}/repo"
    return {
        "ready": True,
        "repo": repo,
        "expected_repo": repo,
        "commit": commit,
        "remote": CANONICAL_REPOSITORY,
        "canonical_repository": CANONICAL_REPOSITORY,
        "release_manifest_present": True,
        "release_manifest_commit": commit,
        "reasons": [],
    }


def _write_marker(root: Path, **changes: Any) -> dict[str, Any]:
    marker = {
        "campaign_id": "campaign-stale-001",
        "manifest_digest": "sha256:" + "b" * 64,
        "state": "RUNNING",
        "updated_at": "2026-08-27T00:00:00Z",
        **changes,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "active_campaign.json").write_text(
        json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8"
    )
    return marker


def _fixture(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    root = (tmp_path / "state" / ".dharma" / "forge_lab").resolve()
    marker = _write_marker(root)
    (root / "campaigns" / "runs").mkdir(parents=True)
    return root, marker


def _plan(root: Path, **kwargs: Any) -> dict[str, Any]:
    return reconciliation.plan_reconciliation(
        forge_root=root,
        source_status=lambda: _source(),
        process_probe=lambda _marker: False,
        **kwargs,
    )


def _apply(root: Path, plan: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    request_id = str(kwargs.pop("request_id", "test-reconcile-001"))
    return reconciliation.apply_reconciliation(
        forge_root=root,
        plan_digest=plan["plan_digest"],
        request_id=request_id,
        source_status=lambda: _source(),
        process_probe=lambda _marker: False,
        **kwargs,
    )


def _tree(root: Path) -> list[tuple[str, int, bytes | None]]:
    rows: list[tuple[str, int, bytes | None]] = []
    for path in sorted(root.rglob("*")):
        metadata = path.lstat()
        rows.append(
            (
                path.relative_to(root).as_posix(),
                metadata.st_mode,
                path.read_bytes() if path.is_file() and not path.is_symlink() else None,
            )
        )
    return rows


def test_status_and_plan_are_read_only_and_digest_bound(tmp_path: Path) -> None:
    root, marker = _fixture(tmp_path)
    before = _tree(root)

    status = reconciliation.reconciliation_status(forge_root=root)
    plan = _plan(root)

    assert status == {
        "schema": reconciliation.STATUS_SCHEMA,
        "ok": False,
        "read_only": True,
        "findings": [
            {"code": reconciliation.FINDING, "campaign": marker["campaign_id"]}
        ],
    }
    assert _tree(root) == before
    assert plan["read_only"] is True
    assert plan["finding"]["campaign"] == marker["campaign_id"]
    assert plan["state_identity"]["active_projection"]["content_digest"] == content_digest(marker)
    assert reconciliation.validate_reconciliation_plan(plan) == plan

    tampered = {**plan, "action": "DELETE_HISTORY"}
    with pytest.raises(reconciliation.ReconciliationError) as error:
        reconciliation.validate_reconciliation_plan(tampered)
    assert error.value.code == "INVALID_PLAN"


def test_apply_atomically_quarantines_and_receipts_then_replays(tmp_path: Path) -> None:
    root, marker = _fixture(tmp_path)
    plan = _plan(root)

    result = _apply(root, plan)

    assert result["ok"] is True
    assert result["idempotent"] is False
    assert not (root / "active_campaign.json").exists()
    history = root / result["quarantine_path"]
    receipt_path = Path(result["receipt_path"])
    assert json.loads(history.read_text(encoding="utf-8")) == marker
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["history_preserved"] is True
    assert receipt["before_digest"] == content_digest(receipt["before"])
    assert receipt["after_digest"] == content_digest(receipt["after"])
    assert receipt["receipt_digest"] == content_digest(
        {key: value for key, value in receipt.items() if key != "receipt_digest"}
    )
    receipt_bytes = receipt_path.read_bytes()

    replay = _apply(root, plan)

    assert replay["idempotent"] is True
    assert receipt_path.read_bytes() == receipt_bytes
    assert list((root / "reconciliation" / "receipts").glob("*.json")) == [receipt_path]
    assert list((root / "reconciliation" / "quarantine").rglob("*.json")) == [history]


def test_request_id_cannot_be_rebound_to_another_plan(tmp_path: Path) -> None:
    root, _marker = _fixture(tmp_path)
    plan = _plan(root)
    _apply(root, plan)
    different = "sha256:" + ("0" if plan["plan_digest"][-1] != "0" else "1") * 64

    with pytest.raises(reconciliation.ReconciliationError) as error:
        reconciliation.apply_reconciliation(
            forge_root=root,
            plan_digest=different,
            request_id="test-reconcile-001",
            source_status=lambda: _source(),
            process_probe=lambda _marker: False,
        )

    assert error.value.code == "REQUEST_ID_REUSED"


def test_apply_refuses_projection_change_as_stale_plan(tmp_path: Path) -> None:
    root, marker = _fixture(tmp_path)
    plan = _plan(root)
    marker["updated_at"] = "2026-08-27T00:01:00Z"
    (root / "active_campaign.json").write_text(json.dumps(marker) + "\n", encoding="utf-8")

    with pytest.raises(reconciliation.ReconciliationError) as error:
        _apply(root, plan)

    assert error.value.code == "STALE_PLAN"
    assert (root / "active_campaign.json").exists()
    assert not (root / "reconciliation" / "receipts").exists()


def test_apply_revalidates_missing_run_under_control_locks(tmp_path: Path) -> None:
    root, marker = _fixture(tmp_path)
    plan = _plan(root)
    (root / "campaigns" / "runs" / marker["campaign_id"]).mkdir()

    with pytest.raises(reconciliation.ReconciliationError) as error:
        _apply(root, plan)

    assert error.value.code == "ACTIVE_RUN_PRESENT"
    assert (root / "active_campaign.json").exists()


def test_apply_refuses_unsafe_source_halt_and_active_process(tmp_path: Path) -> None:
    root, _marker = _fixture(tmp_path)
    plan = _plan(root)

    with pytest.raises(reconciliation.ReconciliationError) as source_error:
        reconciliation.apply_reconciliation(
            forge_root=root,
            plan_digest=plan["plan_digest"],
            request_id="unsafe-source",
            source_status=lambda: {"ready": False, "reasons": ["dirty"]},
            process_probe=lambda _marker: False,
        )
    assert source_error.value.code == "UNSAFE_SOURCE"

    (root / "HALT").touch()
    with pytest.raises(reconciliation.ReconciliationError) as halt_error:
        _apply(root, plan, request_id="halt-present")
    assert halt_error.value.code == "HALT_PRESENT"
    (root / "HALT").unlink()

    with pytest.raises(reconciliation.ReconciliationError) as process_error:
        reconciliation.apply_reconciliation(
            forge_root=root,
            plan_digest=plan["plan_digest"],
            request_id="active-process",
            source_status=lambda: _source(),
            process_probe=lambda _marker: True,
        )
    assert process_error.value.code == "ACTIVE_PROCESS_PRESENT"
    assert (root / "active_campaign.json").exists()


def test_plan_refuses_unknown_finding_and_unsafe_source(tmp_path: Path) -> None:
    root, _marker = _fixture(tmp_path)

    with pytest.raises(reconciliation.ReconciliationError) as finding_error:
        reconciliation.plan_reconciliation(
            finding_code="ACTIVE_CAMPAIGN_STATE_DRIFT",
            forge_root=root,
            source_status=lambda: _source(),
            process_probe=lambda _marker: False,
        )
    assert finding_error.value.code == "UNKNOWN_FINDING"

    with pytest.raises(reconciliation.ReconciliationError) as source_error:
        reconciliation.plan_reconciliation(
            forge_root=root,
            source_status=lambda: {"ready": False, "reasons": ["mutable"]},
            process_probe=lambda _marker: False,
        )
    assert source_error.value.code == "UNSAFE_SOURCE"


def test_ambiguous_projection_and_run_paths_fail_closed(tmp_path: Path) -> None:
    root = (tmp_path / "forge").resolve()
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"campaign_id": "campaign-1", "state": "RUNNING"}))
    (root / "active_campaign.json").symlink_to(outside)

    status = reconciliation.reconciliation_status(forge_root=root)
    assert status["ok"] is False
    assert status["findings"][0]["code"] == "AMBIGUOUS_PATH"
    with pytest.raises(reconciliation.ReconciliationError) as projection_error:
        reconciliation.plan_reconciliation(
            forge_root=root,
            source_status=lambda: _source(),
            process_probe=lambda _marker: False,
        )
    assert projection_error.value.code == "AMBIGUOUS_PATH"

    (root / "active_campaign.json").unlink()
    marker = _write_marker(root)
    (root / "campaigns").mkdir()
    (root / "campaigns" / "runs").symlink_to(tmp_path)
    with pytest.raises(reconciliation.ReconciliationError) as run_error:
        _plan(root, campaign_id=marker["campaign_id"])
    assert run_error.value.code == "AMBIGUOUS_PATH"


def test_campaign_control_lock_is_a_real_mutual_exclusion_fence(tmp_path: Path) -> None:
    root, _marker = _fixture(tmp_path)
    plan = _plan(root)
    lock_path = root / "campaigns" / "control.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(reconciliation.ReconciliationError) as error:
            _apply(root, plan)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    assert error.value.code == "CONTROL_BUSY"
    assert (root / "active_campaign.json").exists()


def test_interrupted_move_is_recovered_without_losing_history(tmp_path: Path) -> None:
    root, marker = _fixture(tmp_path)
    plan = _plan(root)
    history = root / plan["mutation"]["destination"]
    history.parent.mkdir(parents=True)
    os.rename(root / "active_campaign.json", history)

    recovered = _apply(root, plan, request_id="recover-interrupted")

    assert recovered["idempotent"] is False
    assert recovered["receipt"]["recovered_after_interruption"] is True
    assert json.loads(history.read_text(encoding="utf-8")) == marker
    assert Path(recovered["receipt_path"]).is_file()


def test_existing_history_is_never_overwritten(tmp_path: Path) -> None:
    root, marker = _fixture(tmp_path)
    plan = _plan(root)
    history = root / plan["mutation"]["destination"]
    history.parent.mkdir(parents=True)
    sentinel = {"sentinel": "immutable-history"}
    history.write_text(json.dumps(sentinel) + "\n", encoding="utf-8")

    with pytest.raises(reconciliation.ReconciliationError) as error:
        _apply(root, plan, request_id="history-collision")

    assert error.value.code == "HISTORY_COLLISION"
    assert json.loads(history.read_text(encoding="utf-8")) == sentinel
    assert json.loads((root / "active_campaign.json").read_text()) == marker


def test_source_identity_change_invalidates_plan(tmp_path: Path) -> None:
    root, _marker = _fixture(tmp_path)
    plan = _plan(root)

    with pytest.raises(reconciliation.ReconciliationError) as error:
        reconciliation.apply_reconciliation(
            forge_root=root,
            plan_digest=plan["plan_digest"],
            request_id="source-moved",
            source_status=lambda: _source("c" * 40),
            process_probe=lambda _marker: False,
        )

    assert error.value.code == "STALE_PLAN"
    assert (root / "active_campaign.json").exists()


@pytest.mark.parametrize("failure_stage", ["root", "history", "receipt"])
def test_post_mutation_directory_sync_failure_has_recoverable_unknown_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    root, marker = _fixture(tmp_path)
    plan = _plan(root)
    history = root / plan["mutation"]["destination"]
    targets = {
        "root": root,
        "history": history.parent,
        "receipt": root / "reconciliation" / "receipts",
    }
    original_fsync = reconciliation._fsync

    def failing_fsync(path: Path) -> None:
        if path == targets[failure_stage]:
            raise OSError("raw fsync diagnostic must stay private")
        original_fsync(path)

    monkeypatch.setattr(reconciliation, "_fsync", failing_fsync)
    with pytest.raises(reconciliation.ReconciliationError) as error:
        _apply(root, plan, request_id=f"fsync-{failure_stage}")

    assert error.value.code == "APPLY_OUTCOME_UNKNOWN"
    assert "same plan digest and request id" in str(error.value)
    assert "raw fsync diagnostic" not in str(error.value)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True
    assert not (root / "active_campaign.json").exists()
    assert json.loads(history.read_text(encoding="utf-8")) == marker

    monkeypatch.setattr(reconciliation, "_fsync", original_fsync)
    recovered = _apply(root, plan, request_id=f"fsync-{failure_stage}")
    assert recovered["ok"] is True
    assert Path(recovered["receipt_path"]).is_file()


def test_post_mutation_receipt_write_failure_has_recovery_guidance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, marker = _fixture(tmp_path)
    plan = _plan(root)
    history = root / plan["mutation"]["destination"]
    original_write = reconciliation.write_json_exclusive

    def failing_write(path: Path, payload: dict[str, Any], **kwargs: Any) -> None:
        raise OSError("raw receipt diagnostic must stay private")

    monkeypatch.setattr(reconciliation, "write_json_exclusive", failing_write)
    with pytest.raises(reconciliation.ReconciliationError) as error:
        _apply(root, plan, request_id="receipt-write-failure")

    assert error.value.code == "APPLY_OUTCOME_UNKNOWN"
    assert "same plan digest and request id" in str(error.value)
    assert "raw receipt diagnostic" not in str(error.value)
    assert error.value.__cause__ is None
    assert not (root / "active_campaign.json").exists()
    assert json.loads(history.read_text(encoding="utf-8")) == marker

    monkeypatch.setattr(reconciliation, "write_json_exclusive", original_write)
    recovered = _apply(root, plan, request_id="receipt-write-failure")
    assert recovered["receipt"]["recovered_after_interruption"] is True


def test_pre_mutation_receipt_directory_failure_is_typed_and_non_mutating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, marker = _fixture(tmp_path)
    plan = _plan(root)
    original_mkdir = reconciliation._mkdir

    def failing_mkdir(root_path: Path, relative: Path) -> Path:
        if relative == Path("reconciliation/receipts"):
            raise OSError("raw prepare diagnostic must stay private")
        return original_mkdir(root_path, relative)

    monkeypatch.setattr(reconciliation, "_mkdir", failing_mkdir)
    with pytest.raises(reconciliation.ReconciliationError) as error:
        _apply(root, plan, request_id="receipt-prepare-failure")

    assert error.value.code == "RECEIPT_PREPARE_FAILED"
    assert "no projection was moved" in str(error.value)
    assert "raw prepare diagnostic" not in str(error.value)
    assert error.value.__cause__ is None
    assert json.loads((root / "active_campaign.json").read_text()) == marker
    assert not (root / plan["mutation"]["destination"]).exists()


@pytest.mark.parametrize("failure_stage", ["prepare", "write", "sync"])
def test_recovery_receipt_failure_is_typed_and_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    root, marker = _fixture(tmp_path)
    plan = _plan(root)
    history = root / plan["mutation"]["destination"]
    history.parent.mkdir(parents=True)
    os.rename(root / "active_campaign.json", history)
    original_mkdir = reconciliation._mkdir
    original_write = reconciliation.write_json_exclusive
    original_fsync = reconciliation._fsync

    if failure_stage == "prepare":
        monkeypatch.setattr(
            reconciliation,
            "_mkdir",
            lambda _root, _relative: (_ for _ in ()).throw(OSError("raw recovery prepare")),
        )
    elif failure_stage == "write":
        monkeypatch.setattr(
            reconciliation,
            "write_json_exclusive",
            lambda _path, _payload: (_ for _ in ()).throw(OSError("raw recovery write")),
        )
    else:
        monkeypatch.setattr(
            reconciliation,
            "_fsync",
            lambda _path: (_ for _ in ()).throw(OSError("raw recovery sync")),
        )

    request_id = f"recovery-receipt-{failure_stage}"
    with pytest.raises(reconciliation.ReconciliationError) as error:
        _apply(root, plan, request_id=request_id)

    assert error.value.code == "APPLY_OUTCOME_UNKNOWN"
    assert "same plan digest and request id" in str(error.value)
    assert "raw recovery" not in str(error.value)
    assert error.value.__cause__ is None
    assert json.loads(history.read_text(encoding="utf-8")) == marker

    monkeypatch.setattr(reconciliation, "_mkdir", original_mkdir)
    monkeypatch.setattr(reconciliation, "write_json_exclusive", original_write)
    monkeypatch.setattr(reconciliation, "_fsync", original_fsync)
    recovered = _apply(root, plan, request_id=request_id)
    assert recovered["ok"] is True
    assert Path(recovered["receipt_path"]).is_file()
