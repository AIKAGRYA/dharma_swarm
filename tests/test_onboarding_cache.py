"""Session-status cache invalidation, safe paths, and fail-closed reuse."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dharma_swarm.operator_core.onboarding.models import (
    ConfigError,
    ReceiptValidationError,
)
from dharma_swarm.operator_core.onboarding.receipt import (
    build_input_manifest,
    cache_key,
    compute_delta,
    load_receipt,
    resolve_ops_dir,
    section_fingerprints,
    write_receipt,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


# --- O3-B4 groundwork: manifest invalidation ---------------------------------

def test_each_manifest_invalidator_forces_miss(tmp_path: Path) -> None:
    """Changing any manifest input's bytes must change the cache key."""
    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "b.txt").write_text("beta")
    categories = {"instruction_custody": ["a.txt"], "dependency_contract": ["b.txt"]}

    baseline = cache_key(build_input_manifest(tmp_path, categories), "py-test")

    (tmp_path / "a.txt").write_text("alpha-changed")
    after_a = cache_key(build_input_manifest(tmp_path, categories), "py-test")
    assert after_a != baseline

    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "b.txt").write_text("beta-changed")
    after_b = cache_key(build_input_manifest(tmp_path, categories), "py-test")
    assert after_b != baseline

    (tmp_path / "b.txt").write_text("beta")
    restored = cache_key(build_input_manifest(tmp_path, categories), "py-test")
    assert restored == baseline

    assert cache_key(build_input_manifest(tmp_path, categories), "py-other") != baseline


def test_absent_input_is_itself_an_invalidator(tmp_path: Path) -> None:
    categories = {"instruction_custody": ["missing.md"]}
    manifest = build_input_manifest(tmp_path, categories)
    assert manifest["instruction_custody"]["missing.md"] == "ABSENT"
    (tmp_path / "missing.md").write_text("now present")
    assert build_input_manifest(tmp_path, categories) != manifest


def test_same_bytes_different_mtime_keeps_stable_key(tmp_path: Path) -> None:
    """Cache identity is content-derived, never mtime/inode-derived."""
    target = tmp_path / "doc.md"
    target.write_text("stable bytes")
    categories = {"instruction_custody": ["doc.md"]}
    first = cache_key(build_input_manifest(tmp_path, categories), "py-test")
    os.utime(target, (1_000_000_000, 1_000_000_000))
    second = cache_key(build_input_manifest(tmp_path, categories), "py-test")
    assert first == second


def test_section_fingerprints_move_only_with_their_inputs(tmp_path: Path) -> None:
    (tmp_path / "custody.md").write_text("one")
    (tmp_path / "deps.lock").write_text("two")
    categories = {
        "entry_implementation": [],
        "instruction_custody": ["custody.md"],
        "intent_surface_breakage": [],
        "dependency_contract": ["deps.lock"],
    }
    before = section_fingerprints(build_input_manifest(tmp_path, categories))
    (tmp_path / "deps.lock").write_text("two-changed")
    after = section_fingerprints(build_input_manifest(tmp_path, categories))
    assert before["toolchain"] != after["toolchain"]
    assert before["contract"] == after["contract"]
    assert before["portfolio"] == after["portfolio"]


# --- O3-B5 subset: fail-closed paths and receipts -----------------------------

def test_ops_dir_inside_worktree_fails_closed() -> None:
    with pytest.raises(ConfigError):
        resolve_ops_dir(REPO_ROOT, {"DHARMA_OPS_DIR": str(REPO_ROOT / "sub")})


def test_ops_dir_symlink_escape_into_repo_fails_closed(tmp_path: Path) -> None:
    link = tmp_path / "innocent-looking"
    link.symlink_to(REPO_ROOT)
    with pytest.raises(ConfigError):
        resolve_ops_dir(REPO_ROOT, {"DHARMA_OPS_DIR": str(link / "ops")})


def test_git_dir_escape_fails_closed() -> None:
    with pytest.raises(ConfigError):
        resolve_ops_dir(REPO_ROOT, {"DHARMA_OPS_DIR": str(REPO_ROOT / ".git" / "ops")})


def test_writer_refuses_unloadable_payload(tmp_path: Path) -> None:
    """The atomic writer validates before replace — it cannot mint corruption."""
    outside = tmp_path / "ops"
    with pytest.raises(ReceiptValidationError):
        write_receipt(
            {"schema": "dharma_swarm.onboard_receipt.v2", "garbage": True},
            repo_root=REPO_ROOT,
            env={"DHARMA_OPS_DIR": str(outside)},
        )
    assert not (outside / "onboard_receipt.json").exists()


def test_truncated_receipt_is_typed_corruption(tmp_path: Path) -> None:
    path = tmp_path / "onboard_receipt.json"
    path.write_text('{"schema": "dharma_swarm.onboard_receipt.v2", "trunc')
    with pytest.raises(ReceiptValidationError):
        load_receipt(path)


def test_unknown_future_major_is_explicitly_unsupported(tmp_path: Path) -> None:
    from dharma_swarm.operator_core.onboarding.models import UnsupportedReceiptSchema

    path = tmp_path / "onboard_receipt.json"
    path.write_text(json.dumps({"schema": "dharma_swarm.onboard_receipt.v9"}))
    with pytest.raises(UnsupportedReceiptSchema):
        load_receipt(path)


def _run_in_process(
    ops: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> dict:
    from dharma_swarm.operator_core.onboarding import cli

    monkeypatch.setenv("DHARMA_OPS_DIR", str(ops))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.delenv("DHARMA_ONBOARD_WRITER", raising=False)
    exit_code = cli.assemble_and_run(["--json"])
    rendered = json.loads(capsys.readouterr().out)
    payload = load_receipt(ops / "onboard_receipt.json").payload
    assert exit_code == rendered["exit_code"]
    return payload


def test_unchanged_input_run_reuses_stable_core(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Post-D3 activation: the second unchanged-input run reuses the prior
    receipt's stable core (honest ``hit: true``), while hard/live checks are
    still recomputed and the reused core equals a fresh recomputation —
    reuse is never staleness."""
    from dharma_swarm.operator_core.onboarding import evidence

    ops = tmp_path / "ops"
    first = _run_in_process(ops, monkeypatch, capsys)
    assert first["cache"]["hit"] is False
    assert "no_prior_receipt" in first["cache"]["miss_reasons"]

    second = _run_in_process(ops, monkeypatch, capsys)
    assert second["cache"]["hit"] is True
    assert second["cache"]["miss_reasons"] == []
    assert second["stable_core"] == first["stable_core"]
    assert second["stable_core"] == evidence.collect_stable_core()
    # Hard/live checks always rerun on a hit. The on-disk draft
    # is written before its own persistence condition can exist, so assert
    # the recomputed live conditions, not receipt_persisted.
    live_ids = {row["id"] for row in second["live_delta"]["conditions"]}
    assert {"repo_clean", "repo_unconflicted", "broken_register_parses"} <= live_ids
    assert second["stable_digest"] == first["stable_digest"]


def test_reuse_misses_are_typed_and_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Every reuse miss carries a typed reason; poisoned or version-skewed
    corrupt priors can never seed the stable core."""
    from dharma_swarm.operator_core.onboarding import cli
    from dharma_swarm.operator_core.onboarding.receipt import compute_stable_digest

    ops = tmp_path / "ops"
    receipt_file = ops / "onboard_receipt.json"

    # v1 prior cannot seed reuse.
    monkeypatch.setattr(cli, "WRITER_SCHEMA_DEFAULT", "v1")
    _run_in_process(ops, monkeypatch, capsys)
    monkeypatch.setattr(cli, "WRITER_SCHEMA_DEFAULT", "v2")
    after_v1 = _run_in_process(ops, monkeypatch, capsys)
    assert after_v1["cache"]["hit"] is False
    assert "prior_not_v2" in after_v1["cache"]["miss_reasons"]

    # Key mismatch (manifest change) is a typed miss.
    tampered = json.loads(receipt_file.read_text(encoding="utf-8"))
    tampered["cache"]["key"] = "0" * 64
    receipt_file.write_text(json.dumps(tampered), encoding="utf-8")
    key_miss = _run_in_process(ops, monkeypatch, capsys)
    assert key_miss["cache"]["hit"] is False
    assert "manifest_changed" in key_miss["cache"]["miss_reasons"]

    # Head movement invalidates even on a full manifest match.
    tampered = json.loads(receipt_file.read_text(encoding="utf-8"))
    tampered["stable_core"]["repository"]["head"] = "f" * 40
    tampered["stable_digest"] = compute_stable_digest(tampered["stable_core"])
    receipt_file.write_text(json.dumps(tampered), encoding="utf-8")
    head_miss = _run_in_process(ops, monkeypatch, capsys)
    assert head_miss["cache"]["hit"] is False
    assert "head_changed" in head_miss["cache"]["miss_reasons"]

    # A poisoned stable digest fails closed: no reuse, ever.
    tampered = json.loads(receipt_file.read_text(encoding="utf-8"))
    tampered["stable_core"]["required_reading"] = ["poisoned"]
    receipt_file.write_text(json.dumps(tampered), encoding="utf-8")
    poison_miss = _run_in_process(ops, monkeypatch, capsys)
    assert poison_miss["cache"]["hit"] is False
    assert poison_miss["stable_core"]["required_reading"] != ["poisoned"]


def test_reuse_decision_is_serialized_under_receipt_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Cache concurrency invariant: the prior-receipt read and the reuse
    decision must happen under the same sidecar lock as the replace.  A
    writer that decides from a prior read outside the lock persists stale
    cache metadata when the prior changes while it waits (the Greptile/T-Rex
    repro on PR #942)."""
    import fcntl
    import subprocess
    import sys
    import time

    ops = tmp_path / "ops"
    receipt_file = ops / "onboard_receipt.json"
    first = _run_in_process(ops, monkeypatch, capsys)
    assert first["cache"]["hit"] is False

    env = {
        **os.environ,
        "DHARMA_OPS_DIR": str(ops),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.pop("DHARMA_ONBOARD_WRITER", None)
    lock_path = ops / "onboard_receipt.json.lock"
    with lock_path.open("w") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        proc = subprocess.Popen(
            [sys.executable, "-B", "-m", "dharma_swarm.operator_core.onboarding.cli", "--json"],
            cwd=REPO_ROOT, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        # Give the child ample time to reach its receipt read/decision point;
        # with correct serialization it is blocked on the lock right now.
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.2)
        assert proc.poll() is None, "child completed despite a held receipt lock"
        # The prior changes while the child waits: any pre-lock decision on it
        # is now stale.
        tampered = json.loads(receipt_file.read_text(encoding="utf-8"))
        tampered["cache"]["key"] = "e" * 64
        receipt_file.write_text(json.dumps(tampered), encoding="utf-8")
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    stdout, stderr = proc.communicate(timeout=120)
    truth = json.loads(stdout)
    assert proc.returncode == truth["exit_code"], stderr

    final = load_receipt(receipt_file).payload
    assert final["cache"]["hit"] is False
    assert "manifest_changed" in final["cache"]["miss_reasons"]


# --- delta doctrine ------------------------------------------------------------

def test_v1_receipt_can_never_seed_delta() -> None:
    v1_previous = {"schema": "dharma_swarm.onboard_receipt.v1", "repo": {}}
    delta = compute_delta(v1_previous, {"anything": 1}, [])
    assert delta == {
        "previous_stable_digest": "", "added": [], "resolved": [], "changed": [],
    }


def test_delta_reports_added_resolved_changed() -> None:
    previous = {
        "schema": "dharma_swarm.onboard_receipt.v2",
        "stable_digest": "d" * 64,
        "live_delta": {"conditions": [
            {"id": "gone", "state": "fail"},
            {"id": "flipped", "state": "fail"},
            {"id": "steady", "state": "pass"},
        ]},
    }
    current = [
        {"id": "flipped", "state": "pass"},
        {"id": "steady", "state": "pass"},
        {"id": "fresh", "state": "fail"},
    ]
    delta = compute_delta(previous, {}, current)
    assert delta["previous_stable_digest"] == "d" * 64
    assert delta["added"] == ["fresh"]
    assert delta["resolved"] == ["gone"]
    assert delta["changed"] == ["flipped"]
