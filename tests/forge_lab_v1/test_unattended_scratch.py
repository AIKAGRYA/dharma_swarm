from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dharma_swarm.forge_lab import unattended_scratch as scratch
from dharma_swarm.forge_lab.state_io import content_digest

_COMMIT = "a" * 40
_SPEC_DIGEST = "sha256:" + "b" * 64


def _create(state: Path, run_id: str = "unattended-test") -> dict[str, object]:
    return scratch.create_run_scratch(
        state,
        run_id,
        source_commit=_COMMIT,
        spec_digest=_SPEC_DIGEST,
        created_at="2026-08-28T00:00:00Z",
    )


def _cleanup(
    state: Path,
    create_proof: dict[str, object],
    run_id: str = "unattended-test",
) -> dict[str, object]:
    return scratch.cleanup_run_scratch(
        state,
        run_id,
        source_commit=_COMMIT,
        spec_digest=_SPEC_DIGEST,
        expected_root_identity=create_proof["root_identity"],
        expected_marker_digest=create_proof["marker_digest"],
    )


def test_parent_creates_attests_and_removes_exact_run_root(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    root = scratch.run_root(state, "unattended-test")

    created = _create(state)
    marker = root / scratch.SCRATCH_MARKER

    assert created["ok"] is True
    assert created["operation"] == "create"
    assert created["proof_digest"] == content_digest(
        {key: value for key, value in created.items() if key != "proof_digest"}
    )
    assert root.stat().st_mode & 0o777 == 0o700
    assert marker.stat().st_mode & 0o777 == 0o600

    attested = scratch.attest_run_scratch(
        state,
        "unattended-test",
        source_commit=_COMMIT,
        spec_digest=_SPEC_DIGEST,
    )
    assert attested["ok"] is True
    assert attested["marker_digest"] == created["marker_digest"]

    cleaned = _cleanup(state, created)
    assert cleaned["ok"] is True
    assert cleaned["inventory"]["entries"] == 1
    assert not os.path.lexists(root)


def test_parent_removes_killed_child_git_tree(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    created = _create(state)
    root = scratch.run_root(state, "unattended-test")
    repo = root / "experiment-1" / "repo"
    (repo / ".git" / "objects").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (repo / ".git" / "objects" / "partial").write_bytes(b"partial clone")
    (repo / "partial.py").write_text("raise SystemExit\n")

    proof = _cleanup(state, created)

    assert proof["ok"] is True
    assert proof["inventory"]["entries"] >= 7
    assert proof["inventory"]["regular_files"] == 4
    assert not os.path.lexists(root)


def test_parent_unlinks_git_symlink_without_following_target(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    created = _create(state)
    root = scratch.run_root(state, "unattended-test")
    repo = root / "experiment-1" / "repo"
    repo.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_text("preserve")
    link = repo / "linked"
    link.symlink_to(outside)
    dangling = repo / "dangling"
    dangling.symlink_to(tmp_path / "missing")

    proof = _cleanup(state, created)

    assert proof["ok"] is True
    assert proof["inventory"]["symlinks"] == 2
    assert outside.read_text() == "preserve"
    assert not os.path.lexists(root)
    assert scratch.validate_parent_scratch_proofs(
        created,
        proof,
        state_root=state,
        run_id="unattended-test",
    )


def test_parent_refuses_marker_mismatch_without_deleting_root(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    created = _create(state)
    root = scratch.run_root(state, "unattended-test")
    marker_path = root / scratch.SCRATCH_MARKER
    marker = json.loads(marker_path.read_text())
    marker["source_commit"] = "c" * 40
    marker_path.write_text(json.dumps(marker) + "\n")
    os.chmod(marker_path, 0o600)

    with pytest.raises(scratch.ScratchCustodyError) as error:
        _cleanup(state, created)

    assert error.value.code == "SCRATCH_MARKER_MISMATCH"
    assert os.path.lexists(root)


def test_recomputed_marker_drift_blocks_lease_and_cleanup(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    created = _create(state)
    root = scratch.run_root(state, "unattended-test")
    marker_path = root / scratch.SCRATCH_MARKER
    marker = json.loads(marker_path.read_text())
    marker["created_at"] = "2026-08-28T00:00:01Z"
    marker["marker_digest"] = content_digest(
        {key: value for key, value in marker.items() if key != "marker_digest"}
    )
    marker_path.write_text(json.dumps(marker) + "\n")
    os.chmod(marker_path, 0o600)

    with pytest.raises(scratch.ScratchCustodyError) as lease_error:
        scratch.acquire_run_scratch_lease(
            state,
            "unattended-test",
            source_commit=_COMMIT,
            spec_digest=_SPEC_DIGEST,
            expected_root_identity=created["root_identity"],
            expected_marker_digest=created["marker_digest"],
        )
    assert lease_error.value.code == "SCRATCH_MARKER_MISMATCH"

    with pytest.raises(scratch.ScratchCustodyError) as cleanup_error:
        _cleanup(state, created)
    assert cleanup_error.value.code == "SCRATCH_MARKER_MISMATCH"
    assert os.path.lexists(root)
    assert marker_path.is_file()


def test_partial_marker_creation_is_rolled_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    root = scratch.run_root(state, "unattended-test")

    def fail_after_side_effect(run_fd: int, _marker: dict[str, object]) -> None:
        os.mkdir("partial", mode=0o700, dir_fd=run_fd)
        raise OSError("simulated marker failure")

    monkeypatch.setattr(scratch, "_write_marker", fail_after_side_effect)

    with pytest.raises(scratch.ScratchCustodyError) as error:
        _create(state)

    assert error.value.code == "SCRATCH_CREATE_REFUSED"
    assert not os.path.lexists(root)


def test_existing_run_root_is_never_adopted_or_deleted(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    root = scratch.run_root(state, "unattended-test")
    root.mkdir(parents=True)
    sentinel = root / "user-data"
    sentinel.write_text("preserve")

    with pytest.raises(scratch.ScratchCustodyError) as error:
        _create(state)

    assert error.value.code == "SCRATCH_CREATE_REFUSED"
    assert sentinel.read_text() == "preserve"


def test_cleanup_refuses_recreated_root_even_with_recomputed_marker(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    created = _create(state)
    root = scratch.run_root(state, "unattended-test")
    original = root.with_name("unattended-test-original")
    root.rename(original)
    root.mkdir(mode=0o700)
    marker = json.loads((original / scratch.SCRATCH_MARKER).read_text())
    metadata = root.stat()
    marker["root_identity"] = {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
    }
    marker["marker_digest"] = content_digest(
        {key: value for key, value in marker.items() if key != "marker_digest"}
    )
    marker_path = root / scratch.SCRATCH_MARKER
    marker_path.write_text(json.dumps(marker) + "\n")
    os.chmod(marker_path, 0o600)

    with pytest.raises(scratch.ScratchCustodyError) as error:
        _cleanup(state, created)

    assert error.value.code == "SCRATCH_MARKER_MISMATCH"
    assert (original / scratch.SCRATCH_MARKER).is_file()
    assert marker_path.is_file()


def test_live_child_directory_lease_blocks_parent_cleanup(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    created = _create(state)
    lease = scratch.acquire_run_scratch_lease(
        state,
        "unattended-test",
        source_commit=_COMMIT,
        spec_digest=_SPEC_DIGEST,
        expected_root_identity=created["root_identity"],
        expected_marker_digest=created["marker_digest"],
    )
    try:
        with pytest.raises(scratch.ScratchCustodyError) as error:
            _cleanup(state, created)
        assert error.value.code == "SCRATCH_ROOT_BUSY"
    finally:
        lease.close()

    cleaned = _cleanup(state, created)
    assert cleaned["ok"] is True


def test_world_writable_custody_parent_is_never_adopted(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    parent = state / ".dharma" / "evolution_worktrees" / "unattended"
    parent.mkdir(parents=True)
    parent.chmod(0o777)

    with pytest.raises(scratch.ScratchCustodyError) as error:
        _create(state)

    assert error.value.code == "SCRATCH_CREATE_REFUSED"
    assert list(parent.iterdir()) == []


def test_marker_survives_if_post_inventory_deletion_refuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    created = _create(state)
    root = scratch.run_root(state, "unattended-test")
    repo = root / "experiment-1" / "repo"
    repo.mkdir(parents=True)
    os.mkfifo(repo / "special")
    monkeypatch.setattr(
        scratch,
        "_inventory_run",
        lambda *_args, **_kwargs: {
            "entries": 3,
            "directories": 2,
            "regular_files": 1,
            "symlinks": 0,
            "bytes": 1,
            "inventory_digest": "sha256:" + "f" * 64,
            "run_id": "unattended-test",
        },
    )

    with pytest.raises(scratch.ScratchCustodyError) as error:
        _cleanup(state, created)

    assert error.value.code == "SCRATCH_CLEANUP_REFUSED"
    assert (root / scratch.SCRATCH_MARKER).is_file()


def test_marker_is_restored_if_final_run_root_removal_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    created = _create(state)
    root = scratch.run_root(state, "unattended-test")
    original_rmdir = scratch.os.rmdir

    def fail_final_rmdir(name, *args, **kwargs):
        if name == "unattended-test" and kwargs.get("dir_fd") is not None:
            raise OSError("simulated final rmdir failure")
        return original_rmdir(name, *args, **kwargs)

    monkeypatch.setattr(scratch.os, "rmdir", fail_final_rmdir)
    with pytest.raises(scratch.ScratchCustodyError) as error:
        _cleanup(state, created)

    assert error.value.code == "SCRATCH_CLEANUP_REFUSED"
    assert os.path.lexists(root)
    assert (root / scratch.SCRATCH_MARKER).is_file()
    attested = scratch.attest_run_scratch(
        state,
        "unattended-test",
        source_commit=_COMMIT,
        spec_digest=_SPEC_DIGEST,
        expected_root_identity=created["root_identity"],
        expected_marker_digest=created["marker_digest"],
    )
    assert attested["ok"] is True

    monkeypatch.setattr(scratch.os, "rmdir", original_rmdir)
    cleaned = _cleanup(state, created)
    assert cleaned["ok"] is True
    assert not os.path.lexists(root)
