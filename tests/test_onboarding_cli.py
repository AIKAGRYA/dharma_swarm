"""Truthful session-status behavior through the real CLI engine."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import contextmanager
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
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    assert first.returncode == payload["exit_code"]
    assert second.returncode == payload["exit_code"]
    assert payload["schema"] == "dharma_swarm.onboard_json.v1"
    # The deterministic projection excludes volatile fields by construction.
    assert "observed_at" not in first.stdout
    assert "age_minutes" not in first.stdout
    assert "input_manifest" not in first.stdout
    assert "packet" not in payload["stable_core"]
    assert "selected_track" not in payload["stable_core"]["portfolio"]


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
    truth = json.loads(_run(["--json"], ops_dir).stdout)
    assert result.returncode == truth["exit_code"], result.stderr
    assert _porcelain() == before


# --- external receipt behavior ------------------------------------------------

def test_explicit_unsafe_receipt_path_is_config_error(ops_dir: Path) -> None:
    """An explicitly unsafe ops dir is CONFIG_ERROR — never READY."""
    inside = REPO_ROOT / ".dharma-ops-test-escape"
    result = _run(["--json"], inside)
    try:
        payload = json.loads(result.stdout)
        assert result.returncode == payload["exit_code"] == 3
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
    receipt = ops_dir / "onboard_receipt.json"
    assert receipt.exists()
    from dharma_swarm.operator_core.onboarding.receipt import load_receipt

    loaded = load_receipt(receipt)
    assert result.returncode == loaded.payload["exit_code"]
    assert loaded.admission_eligible is False  # loader integrity is not admission


def test_unwritable_optional_receipt_does_not_block_session_status(
    ops_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Read-only environments retain a visible warning and truthful READY."""
    from dharma_swarm.operator_core.onboarding import cli, evidence

    @contextmanager
    def denied_transaction(*args, **kwargs):
        raise OSError("read-only test environment")
        yield  # pragma: no cover - makes this a context manager

    monkeypatch.setenv("DHARMA_OPS_DIR", str(ops_dir))
    monkeypatch.setattr(cli, "receipt_transaction", denied_transaction)
    monkeypatch.setattr(
        evidence,
        "observe_repo_live_state",
        lambda: ({"dirty": False, "conflicted": False, "ahead": 0, "behind": 0}, {}),
    )
    monkeypatch.setattr(
        evidence,
        "toolchain_versions",
        lambda: {"git": "git version test", "make": "GNU Make test"},
    )

    exit_code = cli.assemble_and_run(["--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == payload["exit_code"] == 0
    assert payload["verdict"] == "READY"
    warning = next(row for row in payload["conditions"] if row["id"] == "receipt_write_failed")
    assert warning["state"] == "warn"
    assert "optional cache/diagnostic receipt" in warning["reason"]


# --- truthful exits and strict-flag compatibility -----------------------------

def test_strict_blocked_fixture(ops_dir: Path, tmp_path: Path) -> None:
    """--strict surfaces the true nonzero exit; the fixture asserts exit 1
    exactly when session status reports BLOCKED (dirty tree forced via a temp file
    is NOT used — we assert consistency between JSON truth and strict exit)."""
    probe = _run(["--json"], ops_dir)
    truth = json.loads(probe.stdout)
    assert probe.returncode == truth["exit_code"]
    strict = _run(["--strict"], ops_dir, DHARMA_ONBOARD_STRICT="1")
    assert strict.returncode == truth["exit_code"]
    if truth["verdict"] == "BLOCKED":
        assert strict.returncode == 1


def test_strict_ready_fixture(ops_dir: Path) -> None:
    """Default and compatibility flag return the same receipt truth."""
    default = _run([], ops_dir)
    strict = _run(["--strict"], ops_dir)
    truth = json.loads(_run(["--json"], ops_dir).stdout)
    assert default.returncode == truth["exit_code"]
    assert strict.returncode == truth["exit_code"]
    if strict.returncode == 0:
        assert truth["verdict"] in {"READY", "NEEDS_HOST"}


def test_strict_compatibility_never_changes_v2_truth(ops_dir: Path) -> None:
    default = json.loads(_run(["--json"], ops_dir).stdout)
    strict = json.loads(_run(["--json", "--strict"], ops_dir).stdout)
    assert default["verdict"] == strict["verdict"]
    assert default["exit_code"] == strict["exit_code"]
    assert default["conditions"] == strict["conditions"]


# --- usage errors --------------------------------------------------------------

def test_unknown_flag_exits_two_and_retains_conditions(ops_dir: Path) -> None:
    result = _run(["--json", "--definitely-not-a-flag"], ops_dir)
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "USAGE_ERROR"
    ids = {row["id"] for row in payload["conditions"]}
    assert "usage_error" in ids
    assert len(ids) > 1  # safe state collection still ran after the usage error


def test_packet_binding_is_rejected_by_session_status(ops_dir: Path) -> None:
    result = _run(["--json", "--packet", "/tmp/not-an-onboard-concern.json"], ops_dir)
    payload = json.loads(result.stdout)

    assert result.returncode == payload["exit_code"] == 2
    assert payload["verdict"] == "USAGE_ERROR"
    usage = next(row for row in payload["conditions"] if row["id"] == "usage_error")
    assert "--packet" in usage["reason"]


def test_fast_maps_to_compact_with_deprecation_line(ops_dir: Path) -> None:
    result = _run(["--fast"], ops_dir)
    truth = json.loads(_run(["--json"], ops_dir).stdout)
    assert result.returncode == truth["exit_code"]
    assert "deprecated" in result.stderr


# --- pre-D3 writer doctrine ----------------------------------------------------

def test_writer_default_is_v2_after_d3() -> None:
    """The merged operator D3 record (PR #941) authorizes the one
    source-controlled flip; the sole writer default is now v2."""
    from dharma_swarm.operator_core.onboarding import cli

    assert cli.WRITER_SCHEMA_DEFAULT == "v2"


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

    first_result = _run([], ops_dir)
    v2 = load_receipt(receipt)
    assert first_result.returncode == v2.payload["exit_code"]
    assert v2.major == 2  # post-D3 default (PR #941)
    assert v2.payload["primary_verdict"] in {
        "READY", "BLOCKED", "NEEDS_HOST", "CONFIG_ERROR", "TOOLCHAIN_MISSING",
        "USAGE_ERROR",
    }

    monkeypatch.setenv("DHARMA_OPS_DIR", str(ops_dir))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.delenv("DHARMA_ONBOARD_WRITER", raising=False)
    monkeypatch.setattr(cli, "WRITER_SCHEMA_DEFAULT", "v1")
    rollback_exit = cli.assemble_and_run(["--json"])
    rollback_output = json.loads(capsys.readouterr().out)
    rollback_receipt = load_receipt(receipt)
    assert rollback_exit == rollback_output["exit_code"]
    assert rollback_receipt.major == 1  # rollback stays loader-valid

    monkeypatch.setattr(cli, "WRITER_SCHEMA_DEFAULT", "v2")
    roll_forward_exit = cli.assemble_and_run(["--json"])
    roll_forward_output = json.loads(capsys.readouterr().out)
    roll_forward_receipt = load_receipt(receipt)
    assert roll_forward_exit == roll_forward_output["exit_code"]
    assert roll_forward_receipt.major == 2  # roll-forward replaces cleanly


def test_ambient_writer_override_is_denied_pre_d3(ops_dir: Path) -> None:
    """O3R-B2 (default-relative): an ambient ``DHARMA_ONBOARD_WRITER``
    differing from the source-controlled default is denied — the on-disk
    receipt stays on ``WRITER_SCHEMA_DEFAULT`` and a typed condition records
    the denial. Post-D3 the default is v2, so ambient ``v1`` is the bypass."""
    from dharma_swarm.operator_core.onboarding import cli
    from dharma_swarm.operator_core.onboarding.receipt import load_receipt

    default_major = int(cli.WRITER_SCHEMA_DEFAULT.removeprefix("v"))
    other = "v1" if cli.WRITER_SCHEMA_DEFAULT == "v2" else "v2"

    denied = _run(["--json"], ops_dir, DHARMA_ONBOARD_WRITER=other)
    payload = json.loads(denied.stdout)
    assert denied.returncode == payload["exit_code"] == 3
    assert payload["verdict"] == "CONFIG_ERROR"
    assert payload["exit_code"] == 3
    rows = {row["id"]: row for row in payload["conditions"]}
    assert rows["writer_override_denied"]["state"] == "fail"
    assert "denied" in rows["writer_override_denied"]["reason"]
    assert load_receipt(ops_dir / "onboard_receipt.json").major == default_major

    compatibility = _run([], ops_dir, DHARMA_ONBOARD_WRITER=other, DHARMA_ONBOARD_STRICT="1")
    assert compatibility.returncode == 3

    # An ambient value equal to the source-controlled default is a no-op,
    # not a denial.
    matching = _run(["--json"], ops_dir, DHARMA_ONBOARD_WRITER=cli.WRITER_SCHEMA_DEFAULT)
    matching_payload = json.loads(matching.stdout)
    assert matching.returncode == matching_payload["exit_code"]
    matching_ids = {row["id"] for row in matching_payload["conditions"]}
    assert "writer_override_denied" not in matching_ids
    assert load_receipt(ops_dir / "onboard_receipt.json").major == default_major


def test_human_output_stays_inside_line_budget(ops_dir: Path) -> None:
    result = _run([], ops_dir)
    emitted = result.stdout.count("\n")  # every emitted line, blanks included
    assert 40 <= emitted <= 70, f"human output was {emitted} lines"
