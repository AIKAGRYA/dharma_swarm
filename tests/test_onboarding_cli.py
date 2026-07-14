"""WP-O3 door behavior through the real CLI engine.

Covers O3-B6 (deterministic JSON: repeated byte-identical output), O3-B8
(entry modes attempt no repository write), O3-B10 (receipt persistence is an
admission requirement), O3-B11 (legacy exit changes only process exit, never
v2 truth), the strict fixtures the spec's verification block names, usage-error
handling, and the pre-D3 writer default.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = "dharma_swarm.operator_core.onboarding.cli"


def _run(args: list[str], ops_dir: Path, **env_extra: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DHARMA_OPS_DIR": str(ops_dir),
        "PYTHONDONTWRITEBYTECODE": "1",
        **env_extra,
    }
    return subprocess.run(
        [sys.executable, "-B", "-m", CLI, *args],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=300,
    )


def _porcelain() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--ignored=matching"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    ).stdout


@pytest.fixture()
def ops_dir(tmp_path: Path) -> Path:
    return tmp_path / "external-ops"


# --- O3-B6: deterministic machine output ------------------------------------

def test_repeated_json_is_byte_identical(ops_dir: Path) -> None:
    first = _run(["--json"], ops_dir)
    second = _run(["--json"], ops_dir)
    assert first.returncode == 0 and second.returncode == 0
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    assert payload["schema"] == "dharma_swarm.onboard_json.v1"
    # The projection excludes volatile fields by construction (spec §2.5).
    assert "observed_at" not in first.stdout
    assert "age_minutes" not in first.stdout
    assert "input_manifest" not in first.stdout


def test_json_carries_true_verdict_and_conditions(ops_dir: Path) -> None:
    result = _run(["--json"], ops_dir)
    payload = json.loads(result.stdout)
    assert payload["verdict"] in {
        "READY", "BLOCKED", "NEEDS_HOST", "CONFIG_ERROR", "TOOLCHAIN_MISSING",
        "USAGE_ERROR",
    }
    ids = [row["id"] for row in payload["conditions"]]
    assert ids == sorted(ids)
    assert "receipt_persisted" in ids


# --- O3-B8: no repository write in any entry mode ----------------------------

@pytest.mark.parametrize("mode", [[], ["--deep"], ["--json"]])
def test_all_entry_modes_attempt_no_repository_write(ops_dir: Path, mode: list[str]) -> None:
    before = _porcelain()
    result = _run(mode, ops_dir)
    assert result.returncode == 0, result.stderr
    assert _porcelain() == before


# --- O3-B10: receipt persistence is an admission requirement -----------------

def test_receipt_persistence_is_admission_requirement(ops_dir: Path) -> None:
    """An ops dir inside the worktree is CONFIG_ERROR — never READY."""
    inside = REPO_ROOT / ".dharma-ops-test-escape"
    result = _run(["--json"], inside)
    try:
        payload = json.loads(result.stdout)
        assert payload["verdict"] == "CONFIG_ERROR"
        assert payload["exit_code"] == 3
        ids = {row["id"] for row in payload["conditions"]}
        assert "receipt_path_invalid" in ids
        assert not inside.exists()  # fail-closed: nothing written inside the repo
    finally:
        if inside.exists():  # defensive cleanup; the assert above already failed
            import shutil

            shutil.rmtree(inside)


def test_receipt_write_lands_outside_and_validates(ops_dir: Path) -> None:
    result = _run([], ops_dir)
    assert result.returncode == 0
    receipt = ops_dir / "onboard_receipt.json"
    assert receipt.exists()
    from dharma_swarm.operator_core.onboarding.receipt import load_receipt

    loaded = load_receipt(receipt)
    assert loaded.admission_eligible is False  # loader integrity is not admission


# --- O3-B11 + strict fixtures -------------------------------------------------

def test_strict_blocked_fixture(ops_dir: Path, tmp_path: Path) -> None:
    """--strict surfaces the true nonzero exit; the fixture asserts exit 1
    exactly when the door reports BLOCKED (dirty tree forced via a temp file
    is NOT used — we assert consistency between JSON truth and strict exit)."""
    probe = _run(["--json"], ops_dir)
    truth = json.loads(probe.stdout)
    strict = _run(["--strict"], ops_dir, DHARMA_ONBOARD_STRICT="1")
    assert strict.returncode == truth["exit_code"]
    if truth["verdict"] == "BLOCKED":
        assert strict.returncode == 1


def test_strict_ready_fixture(ops_dir: Path) -> None:
    """Whatever the verdict, the legacy default exits 0 and strict exits the
    receipt's true code — the pair can only both be zero when READY-like."""
    legacy = _run([], ops_dir)
    strict = _run(["--strict"], ops_dir)
    truth = json.loads(_run(["--json"], ops_dir).stdout)
    assert legacy.returncode == 0
    assert strict.returncode == truth["exit_code"]
    if strict.returncode == 0:
        assert truth["verdict"] in {"READY", "NEEDS_HOST"}


def test_legacy_exit_compatibility_never_changes_v2_truth(ops_dir: Path) -> None:
    legacy = json.loads(_run(["--json"], ops_dir).stdout)
    strict = json.loads(_run(["--json", "--strict"], ops_dir).stdout)
    assert legacy["verdict"] == strict["verdict"]
    assert legacy["exit_code"] == strict["exit_code"]
    assert legacy["conditions"] == strict["conditions"]


# --- usage errors --------------------------------------------------------------

def test_unknown_flag_exits_two_and_retains_conditions(ops_dir: Path) -> None:
    result = _run(["--json", "--definitely-not-a-flag"], ops_dir)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "USAGE_ERROR"
    ids = {row["id"] for row in payload["conditions"]}
    assert "usage_error" in ids
    assert len(ids) > 1  # safe state collection still ran (spec §2.1)


def test_fast_maps_to_compact_with_deprecation_line(ops_dir: Path) -> None:
    result = _run(["--fast"], ops_dir)
    assert result.returncode == 0
    assert "deprecated" in result.stderr


# --- pre-D3 writer doctrine ----------------------------------------------------

def test_writer_default_is_v1_until_d3() -> None:
    from dharma_swarm.operator_core.onboarding import cli

    assert cli.WRITER_SCHEMA_DEFAULT == "v1"


def test_writer_migration_and_rollback_matrix(
    ops_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """O3-B9 slice: default writes valid v1; the SOURCE-CONTROLLED
    ``WRITER_SCHEMA_DEFAULT`` — never an ambient variable (O3R-B2) — is the
    one seam that writes v2 after D3; rolling the default back to v1 replaces
    the v2 receipt without corruption."""
    from dharma_swarm.operator_core.onboarding import cli
    from dharma_swarm.operator_core.onboarding.receipt import load_receipt

    receipt = ops_dir / "onboard_receipt.json"

    assert _run([], ops_dir).returncode == 0
    assert load_receipt(receipt).major == 1

    monkeypatch.setenv("DHARMA_OPS_DIR", str(ops_dir))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.delenv("DHARMA_ONBOARD_WRITER", raising=False)
    monkeypatch.setattr(cli, "WRITER_SCHEMA_DEFAULT", "v2")
    assert cli.assemble_and_run([]) == 0
    capsys.readouterr()
    v2 = load_receipt(receipt)
    assert v2.major == 2
    assert v2.payload["primary_verdict"] in {
        "READY", "BLOCKED", "NEEDS_HOST", "CONFIG_ERROR", "TOOLCHAIN_MISSING",
        "USAGE_ERROR",
    }

    monkeypatch.setattr(cli, "WRITER_SCHEMA_DEFAULT", "v1")
    assert cli.assemble_and_run([]) == 0
    capsys.readouterr()
    assert load_receipt(receipt).major == 1


def test_ambient_writer_override_is_denied_pre_d3(ops_dir: Path) -> None:
    """O3R-B2: an ambient ``DHARMA_ONBOARD_WRITER`` differing from the
    source-controlled default is denied — the on-disk receipt stays on
    ``WRITER_SCHEMA_DEFAULT`` and a typed condition records the denial."""
    from dharma_swarm.operator_core.onboarding.receipt import load_receipt

    denied = _run(["--json"], ops_dir, DHARMA_ONBOARD_WRITER="v2")
    assert denied.returncode == 0  # legacy pre-WP-O5 door still exits 0
    payload = json.loads(denied.stdout)
    assert payload["verdict"] == "CONFIG_ERROR"
    assert payload["exit_code"] == 3
    rows = {row["id"]: row for row in payload["conditions"]}
    assert rows["writer_override_denied"]["state"] == "fail"
    assert "denied" in rows["writer_override_denied"]["reason"]
    assert load_receipt(ops_dir / "onboard_receipt.json").major == 1

    strict = _run([], ops_dir, DHARMA_ONBOARD_WRITER="v2", DHARMA_ONBOARD_STRICT="1")
    assert strict.returncode == 3

    # An ambient value equal to the source-controlled default is a no-op,
    # not a denial.
    matching = _run(["--json"], ops_dir, DHARMA_ONBOARD_WRITER="v1")
    assert matching.returncode == 0
    matching_ids = {row["id"] for row in json.loads(matching.stdout)["conditions"]}
    assert "writer_override_denied" not in matching_ids
    assert load_receipt(ops_dir / "onboard_receipt.json").major == 1


def test_human_output_stays_inside_line_budget(ops_dir: Path) -> None:
    result = _run([], ops_dir)
    emitted = result.stdout.count("\n")  # every emitted line, blanks included
    assert 40 <= emitted <= 70, f"human output was {emitted} lines"
