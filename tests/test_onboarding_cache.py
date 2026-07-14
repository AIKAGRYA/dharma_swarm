"""WP-O3 cache groundwork: manifest invalidators, key stability, fail-closed
paths, and the honest no-reuse posture of this packet slice.

Covers the groundwork half of O3-B4 (every declared invalidator changes the
key; same bytes with different mtimes/inodes do not) and the path/adversarial
subset of O3-B5 that exists before section reuse is enabled (direct/symlink
``DHARMA_OPS_DIR`` escapes, corrupt prior receipts, cache-hit honesty).
"""

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
    """O3-B6/§3.2: identity is content-derived, never mtime/inode-derived."""
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


def test_cache_hit_is_honestly_false_while_reuse_is_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """This slice computes manifest/key/fingerprints but reuses nothing; a
    receipt claiming a cache hit before the §3.2 adversarial matrix lands
    would be a false-green (spec: cache is a hint, never admission).  The v2
    receipt is seeded through the source-controlled ``WRITER_SCHEMA_DEFAULT``
    seam — the ambient ``DHARMA_ONBOARD_WRITER`` bypass is denied pre-D3
    (O3R-B2)."""
    from dharma_swarm.operator_core.onboarding import cli

    ops = tmp_path / "ops"
    monkeypatch.setenv("DHARMA_OPS_DIR", str(ops))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.delenv("DHARMA_ONBOARD_WRITER", raising=False)
    monkeypatch.setattr(cli, "WRITER_SCHEMA_DEFAULT", "v2")
    assert cli.assemble_and_run(["--json"]) == 0
    capsys.readouterr()
    payload = load_receipt(ops / "onboard_receipt.json").payload
    assert payload["cache"]["hit"] is False
    assert payload["cache"]["miss_reasons"] == ["section_reuse_not_yet_enabled"]
    assert payload["cache"]["input_manifest"]
    assert payload["cache"]["section_fingerprints"]


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
